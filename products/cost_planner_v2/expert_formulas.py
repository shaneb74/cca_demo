"""
Expert Review Formulas for Cost Planner v2

Implements financial analysis formulas that combine:
- Financial assessment data (FinancialProfile)
- Care recommendations from GCP (care type, intensity, flags)
- Regional cost data

Calculates:
- Coverage percentage (how much of care cost is covered by income/benefits)
- Monthly gap amount (shortfall between cost and income)
- Runway months (how long assets will last)
- Asset breakdown with liquidation strategies
"""

from dataclasses import dataclass, field

from core.mcip import CareRecommendation
from products.cost_planner_v2.financial_profile import FinancialProfile


@dataclass
class AssetCategory:
    """
    Individual asset category with actionability assessment.
    
    Represents a category of assets (liquid, retirement, home equity, etc.)
    with metadata about how it can be used to fund care.
    """

    name: str  # Internal key (e.g., "liquid_assets")
    display_name: str  # User-friendly name (e.g., "💵 Liquid Assets")
    current_balance: float  # Gross balance
    accessible_value: float  # After penalties/taxes/fees
    is_liquid: bool  # Can be accessed quickly
    liquidation_timeframe: str  # "immediate", "1-3_months", "3-6_months", "6-12_months"
    recommended: bool  # Smart exclusion logic - should user consider this?
    recommendation_reason: str  # Why recommended or excluded
    tax_implications: str  # "none", "ordinary_income", "capital_gains", "penalty"
    notes: str  # Additional context (e.g., "Reverse mortgage available")
    selected: bool = False  # User selection state


@dataclass
class ExpertReviewAnalysis:
    """
    Results of expert financial review analysis.
    """

    # Input data
    estimated_monthly_cost: float
    total_monthly_income: float
    total_monthly_benefits: float
    total_liquid_assets: float

    # Calculated metrics
    coverage_percentage: float  # 0-100+
    monthly_gap: float  # Can be negative (surplus) or positive (shortfall)
    runway_months: float | None  # None if gap <= 0 (covered indefinitely)

    # Categorization
    coverage_tier: str  # "excellent", "good", "moderate", "concerning", "critical"
    recommendation_level: str  # "low_priority", "medium_priority", "high_priority", "urgent"

    # Modifiers applied
    care_flags_modifier: (
        float  # Multiplier for care complexity (1.0 = no change, 1.2 = 20% increase)
    )
    regional_modifier: float  # Multiplier for regional costs

    # Recommendations
    primary_recommendation: str
    action_items: list
    resources: list

    # NEW: Asset breakdown and selection
    asset_categories: dict[str, AssetCategory] = field(default_factory=dict)
    selected_assets_value: float = 0.0  # Total value of user-selected assets
    extended_runway_months: float | None = None  # Runway with selected assets
    recommended_funding_order: list[str] = field(default_factory=list)  # Priority order
    funding_notes: dict[str, str] = field(default_factory=dict)  # Category-specific notes


def calculate_expert_review(
    profile: FinancialProfile,
    care_recommendation: CareRecommendation | None = None,
    zip_code: str | None = None,
    estimated_monthly_cost: float | None = None,
) -> ExpertReviewAnalysis:
    """
    Perform comprehensive expert financial review analysis.

    Args:
        profile: FinancialProfile from assessments
        care_recommendation: GCP care recommendation (tier, type, flags)
        zip_code: User's ZIP code for regional cost adjustment
        estimated_monthly_cost: Pre-calculated monthly cost from intro (if available)

    Returns:
        ExpertReviewAnalysis with all calculated metrics
    """

    # ==== STEP 1: Get estimated monthly cost ====
    if estimated_monthly_cost is not None:
        # Use the estimate from intro page (preferred - already has all modifiers applied)
        care_flags_modifier = 1.0  # Already included in intro estimate
        regional_modifier = 1.0  # Already included in intro estimate
        # [FA_DEBUG] Source: Quick Estimate (quieted - uncomment block below to see details)
        # print("\n[FA_DEBUG] ========== EXPERT FORMULAS: USING ESTIMATE ==========")
        # print("[FA_DEBUG] Source: Quick Estimate")
        # print(f"[FA_DEBUG] Estimated Monthly Cost: ${estimated_monthly_cost:,.0f}")
        # print("[FA_DEBUG] ===================================================\n")
    else:
        # Fallback: Calculate from scratch
        base_monthly_cost = _get_base_care_cost(care_recommendation)

        # Apply care flag modifiers
        care_flags_modifier = _calculate_care_flags_modifier(care_recommendation)
        adjusted_monthly_cost = base_monthly_cost * care_flags_modifier

        # Apply regional modifier
        regional_modifier = _get_regional_modifier(zip_code)
        estimated_monthly_cost = adjusted_monthly_cost * regional_modifier

        # [FA_DEBUG] Source: Fallback (quieted - uncomment block below to see details)
        # print("\n[FA_DEBUG] ========== EXPERT FORMULAS: USING FALLBACK ==========")
        # print("[FA_DEBUG] Source: GCP-based calculation (no Quick Estimate)")
        # print(f"[FA_DEBUG] Base Monthly Cost: ${base_monthly_cost:,.0f}")
        # print(f"[FA_DEBUG] After Care Flags (×{care_flags_modifier:.2f}): ${adjusted_monthly_cost:,.0f}")
        # print(f"[FA_DEBUG] After Regional (×{regional_modifier:.2f}): ${estimated_monthly_cost:,.0f}")
        # print("[FA_DEBUG] ====================================================\n")

    # ==== STEP 2: Apply LTC Insurance Benefits ====
    ltc_monthly_coverage = 0.0
    if profile.has_ltc_insurance and profile.ltc_daily_benefit > 0:
        # LTC insurance pays per day (convert to monthly)
        ltc_monthly_coverage = profile.ltc_daily_benefit * 30
        # Reduce estimated care cost by LTC coverage
        estimated_monthly_cost = max(0, estimated_monthly_cost - ltc_monthly_coverage)

    # ==== STEP 3: Calculate total monthly income + benefits ====
    total_monthly_income = profile.total_monthly_income
    total_monthly_benefits = profile.total_va_benefits_monthly + profile.annuity_monthly_income

    # Subtract LTC premium from disposable income (if applicable)
    ltc_premium_cost = profile.ltc_monthly_premium if profile.has_ltc_insurance else 0.0

    total_monthly_resources = total_monthly_income + total_monthly_benefits - ltc_premium_cost

    # ==== STEP 5: Calculate coverage percentage ====
    if estimated_monthly_cost > 0:
        coverage_percentage = (total_monthly_resources / estimated_monthly_cost) * 100
    else:
        coverage_percentage = 100.0  # No cost = fully covered

    # ==== STEP 6: Calculate monthly gap ====
    monthly_gap = estimated_monthly_cost - total_monthly_resources

    # ==== STEP 7: Calculate liquid assets (exclude home) ====
    total_liquid_assets = (
        profile.checking_savings
        + profile.investment_accounts
        + profile.other_real_estate
        + profile.other_resources
        + profile.total_accessible_life_value  # Cash value from life insurance
    )

    # ==== STEP 8: Calculate runway months ====
    if monthly_gap > 0 and total_liquid_assets > 0:
        runway_months = total_liquid_assets / monthly_gap
    elif monthly_gap <= 0:
        runway_months = None  # Indefinite - income covers costs
    else:
        runway_months = 0  # No assets, immediate shortfall

    # ==== NEW STEP 8b: Calculate asset breakdown ====
    asset_categories = calculate_asset_breakdown(profile, care_recommendation)

    # ==== NEW STEP 8c: Calculate recommended funding order ====
    recommended_funding_order, funding_notes = calculate_recommended_funding_order(
        asset_categories, care_recommendation, profile
    )

    # ==== STEP 9: Categorize coverage tier ====
    coverage_tier = _categorize_coverage(coverage_percentage, runway_months)

    # ==== STEP 10: Determine recommendation level ====
    recommendation_level = _determine_recommendation_level(
        coverage_percentage, runway_months, profile
    )

    # ==== STEP 11: Generate recommendations ====
    primary_recommendation, action_items, resources = _generate_recommendations(
        coverage_percentage=coverage_percentage,
        monthly_gap=monthly_gap,
        runway_months=runway_months,
        profile=profile,
        care_recommendation=care_recommendation,
    )

    return ExpertReviewAnalysis(
        estimated_monthly_cost=estimated_monthly_cost,
        total_monthly_income=total_monthly_income,
        total_monthly_benefits=total_monthly_benefits,
        total_liquid_assets=total_liquid_assets,
        coverage_percentage=coverage_percentage,
        monthly_gap=monthly_gap,
        runway_months=runway_months,
        coverage_tier=coverage_tier,
        recommendation_level=recommendation_level,
        care_flags_modifier=care_flags_modifier,
        regional_modifier=regional_modifier,
        primary_recommendation=primary_recommendation,
        action_items=action_items,
        resources=resources,
        # NEW: Asset breakdown
        asset_categories=asset_categories,
        selected_assets_value=0.0,  # Will be calculated based on user selection
        extended_runway_months=None,  # Will be calculated based on user selection
        recommended_funding_order=recommended_funding_order,
        funding_notes=funding_notes,
    )


def _get_base_care_cost(care_recommendation: CareRecommendation | None) -> float:
    """
    Get base monthly care cost based on GCP recommendation.

    Base costs (national average, 2024):
    - Independent Living: $2,500/month
    - Assisted Living: $4,500/month
    - Memory Care: $6,500/month
    - Skilled Nursing: $8,500/month
    - In-Home Care (part-time): $3,000/month
    - In-Home Care (full-time): $6,000/month
    """
    if not care_recommendation:
        return 4500  # Default to assisted living

    care_tier = getattr(care_recommendation, "tier", "moderate")
    care_type = getattr(care_recommendation, "care_type", None)

    # Map care types to base costs
    cost_map = {
        "independent_living": 2500,
        "assisted_living": 4500,
        "memory_care": 6500,
        "skilled_nursing": 8500,
        "in_home_part_time": 3000,
        "in_home_full_time": 6000,
    }

    # If care_type specified, use it
    if care_type in cost_map:
        return cost_map[care_type]

    # Otherwise, map tier to care type
    tier_to_cost = {
        "minimal": 2500,
        "low": 3000,
        "moderate": 4500,
        "substantial": 6500,
        "intensive": 8500,
    }

    return tier_to_cost.get(care_tier, 4500)


def _calculate_care_flags_modifier(care_recommendation: CareRecommendation | None) -> float:
    """
    Calculate cost modifier based on GCP care flags.

    Care flags indicate additional needs that increase cost:
    - fall_risk: +10% (additional monitoring, safety equipment)
    - cognitive_support: +15% (memory care programming, specialized staff)
    - emotional_followup: +5% (counseling, social work services)
    - medication_management: +10% (nursing oversight, pharmacy coordination)
    - mobility_assistance: +10% (physical therapy, adaptive equipment)
    """
    if not care_recommendation:
        return 1.0

    # Get flags - it's a List[Dict[str, Any]] per the dataclass
    flags_list = getattr(care_recommendation, "flags", [])

    # Convert list of flag dicts to a simple dict for easier checking
    flags = {}
    for flag_dict in flags_list:
        if isinstance(flag_dict, dict):
            flags.update(flag_dict)

    modifier = 1.0

    # Add modifiers for each active flag
    if flags.get("fall_risk"):
        modifier += 0.10
    if flags.get("cognitive_support"):
        modifier += 0.15
    if flags.get("emotional_followup"):
        modifier += 0.05
    if flags.get("medication_management"):
        modifier += 0.10
    if flags.get("mobility_assistance"):
        modifier += 0.10

    # Cap at 1.5x (50% increase max)
    return min(modifier, 1.5)


def _get_regional_modifier(zip_code: str | None) -> float:
    """
    Get regional cost modifier based on ZIP code.

    Regional modifiers (relative to national average = 1.0):
    - High cost areas (CA, NY, HI): 1.3-1.5x
    - Moderate cost areas (Urban): 1.1-1.2x
    - Average cost areas: 1.0x
    - Low cost areas (Rural, South): 0.8-0.9x

    For now, return 1.0 (national average). In production, this would
    query a regional cost database by ZIP code.
    """
    # Regional cost lookup not implemented
    # Returns national average (1.0) - would integrate with cost database/API in future
    return 1.0


def _categorize_coverage(coverage_percentage: float, runway_months: float | None) -> str:
    """
    Categorize coverage into tiers for user-friendly display.

    Tiers:
    - excellent: 100%+ coverage, or 60+ months runway
    - good: 80-99% coverage, or 36-59 months runway
    - moderate: 60-79% coverage, or 18-35 months runway
    - concerning: 40-59% coverage, or 6-17 months runway
    - critical: <40% coverage, or <6 months runway
    """
    # If fully covered by income
    if coverage_percentage >= 100:
        return "excellent"

    # If have runway, use that for categorization
    if runway_months is not None:
        if runway_months >= 60:
            return "excellent"
        elif runway_months >= 36:
            return "good"
        elif runway_months >= 18:
            return "moderate"
        elif runway_months >= 6:
            return "concerning"
        else:
            return "critical"

    # Otherwise use coverage percentage
    if coverage_percentage >= 80:
        return "good"
    elif coverage_percentage >= 60:
        return "moderate"
    elif coverage_percentage >= 40:
        return "concerning"
    else:
        return "critical"


def _determine_recommendation_level(
    coverage_percentage: float, runway_months: float | None, profile: FinancialProfile
) -> str:
    """
    Determine recommendation priority level.

    Levels:
    - low_priority: Well covered, no immediate action needed
    - medium_priority: Some gaps, should explore options
    - high_priority: Significant gaps, action needed soon
    - urgent: Critical gaps, immediate action required
    """
    # Fully covered = low priority
    if coverage_percentage >= 100:
        return "low_priority"

    # Check runway
    if runway_months is not None:
        if runway_months >= 36:
            return "low_priority"
        elif runway_months >= 12:
            return "medium_priority"
        elif runway_months >= 6:
            return "high_priority"
        else:
            return "urgent"

    # No assets but coverage above 80%
    if coverage_percentage >= 80:
        return "medium_priority"

    # Low coverage, no assets
    return "urgent"


def _generate_recommendations(
    coverage_percentage: float,
    monthly_gap: float,
    runway_months: float | None,
    profile: FinancialProfile,
    care_recommendation: CareRecommendation | None,
) -> tuple[str, list, list]:
    """
    Generate personalized recommendations based on financial analysis.

    Returns:
        (primary_recommendation, action_items, resources)
    """
    action_items = []
    resources = []

    # ==== DETERMINE PRIMARY RECOMMENDATION ====
    if coverage_percentage >= 100:
        primary_recommendation = (
            "Great news! Your income and benefits fully cover your estimated care costs."
        )
        action_items = [
            "Review your financial plan annually",
            "Consider setting aside savings for unexpected expenses",
            "Explore supplemental care options if needed",
        ]
        resources = ["Financial planning for seniors", "Estate planning resources"]

    elif coverage_percentage >= 80:
        primary_recommendation = f"Your income covers {coverage_percentage:.0f}% of estimated care costs. You have a solid foundation with a small gap to address."
        action_items = [
            f"Plan for ${abs(monthly_gap):,.0f}/month shortfall",
            "Explore supplemental income sources",
            "Review asset liquidation timeline",
        ]
        if runway_months and runway_months < 36:
            action_items.append("Consider long-term care insurance or Medicaid planning")
        resources = ["Income optimization strategies", "Asset management for seniors"]

    elif coverage_percentage >= 50:
        primary_recommendation = f"Your income covers {coverage_percentage:.0f}% of estimated costs. Strategic planning is recommended to address the gap."
        action_items = [
            f"Develop strategy for ${abs(monthly_gap):,.0f}/month gap",
            "Explore home equity options" if profile.primary_residence_value > 100000 else None,
            "Consider Medicaid planning",
            "Review VA benefits eligibility" if not profile.has_va_benefits else None,
            "Investigate community resources and programs",
        ]
        action_items = [item for item in action_items if item]  # Remove None values
        resources = [
            "Medicaid planning guide",
            "Reverse mortgage information",
            "VA benefits application",
            "Community senior services",
        ]

    else:  # < 50%
        primary_recommendation = f"Your income covers {coverage_percentage:.0f}% of estimated costs. Immediate planning is essential to secure sustainable care."
        action_items = [
            f"Address ${abs(monthly_gap):,.0f}/month shortfall urgently",
            "Apply for Medicaid immediately",
            "Explore all benefit programs (VA, SSI, state assistance)",
            "Contact local Area Agency on Aging for resources",
            "Consider care alternatives (family care, adult day programs)",
        ]
        resources = [
            "Medicaid application assistance",
            "Financial aid for seniors",
            "Area Agency on Aging locator",
            "Community care options",
            "Family caregiver support",
        ]

    # ==== ENHANCE WITH PROFILE-SPECIFIC INSIGHTS ====

    # LTC Insurance elimination period alert
    if profile.has_ltc_insurance and profile.ltc_elimination_days > 0:
        action_items.append(
            f"⏱️ Note: LTC insurance has {profile.ltc_elimination_days}-day waiting period before benefits begin"
        )

    # LTC Insurance benefit period alert
    if profile.has_ltc_insurance and profile.ltc_benefit_period_months > 0:
        years = profile.ltc_benefit_period_months / 12
        action_items.append(
            f"📅 LTC insurance coverage limited to {years:.1f} years - plan for care beyond this period"
        )

    # Medicaid asset position insights
    if profile.current_asset_position == "near_limit":
        action_items.insert(
            0, "🎯 You're near Medicaid asset limits - consider expedited Medicaid planning"
        )
    elif profile.current_asset_position == "under_limit":
        action_items.insert(0, "✅ Asset position qualifies for Medicaid - consider applying soon")

    # Medicaid education priority
    if profile.interested_in_spend_down and profile.aware_of_asset_limits == "no":
        action_items.insert(
            0, "📚 HIGH PRIORITY: Schedule Medicaid eligibility consultation to understand options"
        )

    # Elder law referral
    if profile.interested_in_elder_law:
        resources.insert(0, "🏛️ Elder Law Attorney Referral - specialized Medicaid planning")

    # Asset liquidity concerns
    if profile.asset_liquidity_concerns not in ["no_concerns", ""]:
        action_items.append("⚠️ Review asset liquidity constraints before relying on reserves")

    return primary_recommendation, action_items, resources


def calculate_asset_breakdown(
    profile: FinancialProfile,
    care_recommendation: CareRecommendation | None = None,
) -> dict[str, AssetCategory]:
    """
    Calculate detailed asset breakdown with accessibility analysis.
    
    Creates AssetCategory objects for each major asset type with:
    - Current balance
    - Accessible value (after taxes/penalties)
    - Liquidation timeframe
    - Smart exclusions based on care type
    
    Args:
        profile: FinancialProfile from assessments
        care_recommendation: GCP care recommendation for smart exclusions
        
    Returns:
        dict[str, AssetCategory] - Keyed by asset category name
    """

    categories = {}

    # Determine care type for smart exclusions
    care_tier = getattr(care_recommendation, "tier", "moderate") if care_recommendation else "moderate"
    is_in_home_care = care_tier in ["minimal", "low"] or (
        hasattr(care_recommendation, "care_type") and
        "in_home" in getattr(care_recommendation, "care_type", "")
    )

    # ==== 1. LIQUID ASSETS ====
    liquid_balance = profile.checking_savings + profile.investment_accounts
    if liquid_balance > 0:
        categories["liquid_assets"] = AssetCategory(
            name="liquid_assets",
            display_name="💵 Liquid Assets",
            current_balance=liquid_balance,
            accessible_value=liquid_balance * 0.98,  # 2% for transaction fees/timing
            is_liquid=True,
            liquidation_timeframe="immediate",
            recommended=True,
            recommendation_reason="Ready to use - lowest cost option",
            tax_implications="none",
            notes="Checking, savings, CDs, brokerage accounts",
        )

    # ==== 2. RETIREMENT ACCOUNTS ====
    retirement_balance = profile.retirement_accounts_total
    if retirement_balance > 0:
        # Retirement accounts face taxes + potential early withdrawal penalty (if under 59.5)
        # Assume age 62+ (no penalty), but still face ordinary income tax (~32% avg effective)
        # Accessible value: 68% (32% tax withholding)
        accessible = retirement_balance * 0.68

        categories["retirement_accounts"] = AssetCategory(
            name="retirement_accounts",
            display_name="🏦 Retirement Accounts",
            current_balance=retirement_balance,
            accessible_value=accessible,
            is_liquid=False,
            liquidation_timeframe="1-3_months",
            recommended=True,
            recommendation_reason="Taxable as income, but accessible for care costs",
            tax_implications="ordinary_income",
            notes="Traditional IRA, 401(k), Roth IRA (after age 59.5)",
        )

    # ==== 3. LIFE INSURANCE CASH VALUE ====
    if profile.life_insurance_cash_value > 0:
        # Cash value can be borrowed against (no tax up to basis)
        accessible = profile.life_insurance_cash_value * 0.95  # 5% for loan fees

        categories["life_insurance"] = AssetCategory(
            name="life_insurance",
            display_name="📜 Life Insurance Cash Value",
            current_balance=profile.life_insurance_cash_value,
            accessible_value=accessible,
            is_liquid=False,
            liquidation_timeframe="1-3_months",
            recommended=True,
            recommendation_reason="Can borrow against cash value (tax-free loan)",
            tax_implications="none",
            notes="Policy loans available up to cash value",
        )

    # ==== 4. ANNUITIES ====
    if profile.annuity_current_value > 0:
        # Annuities have surrender charges (assume 7% avg) + tax on gains
        accessible = profile.annuity_current_value * 0.85  # 15% haircut for surrender + tax

        categories["annuities"] = AssetCategory(
            name="annuities",
            display_name="💼 Annuities",
            current_balance=profile.annuity_current_value,
            accessible_value=accessible,
            is_liquid=False,
            liquidation_timeframe="1-3_months",
            recommended=False,  # Usually better to keep annuity income stream
            recommendation_reason="Surrender charges apply - consider keeping for income",
            tax_implications="ordinary_income",
            notes="Provides monthly income stream if not surrendered",
        )

    # ==== 5. HOME EQUITY ====
    # Use Home & Housing module data (preferred) or fall back to old assets data
    home_equity = profile.home_equity if profile.home_equity > 0 else (
        profile.primary_residence_value - profile.primary_residence_mortgage_balance
    )
    
    if home_equity > 0 and profile.owns_home == "own":  # Show if any equity and owns home
        # Calculate accessible value based on selected strategy
        home_plan = profile.home_plan
        strategy_outputs = profile.home_equity_strategy_outputs
        
        if home_plan == "sell" and strategy_outputs:
            # Use actual net proceeds from sale calculation
            accessible = strategy_outputs.get("net_proceeds", home_equity * 0.90)
            timeframe = "3-6_months"
            notes = f"Net after {profile.commission_rate:.1f}% commission and closing costs"
        elif home_plan == "reverse_mortgage" and strategy_outputs:
            # Use lump sum from reverse mortgage calculation
            accessible = strategy_outputs.get("lump_sum_available", home_equity * 0.60)
            timeframe = "1-3_months"
            notes = "Reverse mortgage lump sum (or monthly draw available)"
        elif home_plan == "rent_out" and strategy_outputs:
            # Rental income provides monthly flow, not lump sum - show equity value
            accessible = home_equity * 0.80  # HELOC potential
            timeframe = "3-6_months"
            notes = "HELOC against equity while renting (rental income not included here)"
        else:
            # Keep or not sure - default to reverse mortgage potential
            accessible = home_equity * 0.60
            timeframe = "3-6_months"
            notes = "Reverse mortgage, HELOC, or sale potential"

        # Smart recommendation based on care type and strategy
        if is_in_home_care and home_plan == "sell":
            recommended = False
            reason = "Not recommended - home needed for in-home care"
        elif is_in_home_care and home_plan in ("keep", "not_sure"):
            recommended = False
            reason = "Consider reverse mortgage or HELOC to access equity while staying home"
        elif home_plan == "sell" and not is_in_home_care:
            recommended = True
            reason = "Planned sale provides substantial funds for care"
        elif home_plan == "reverse_mortgage":
            recommended = True
            reason = "Reverse mortgage allows aging in place while accessing equity"
        elif home_equity > 200000:
            recommended = True
            reason = "Substantial equity available through sale, reverse mortgage, or HELOC"
        else:
            recommended = True
            reason = "Multiple options to access equity"

        categories["home_equity"] = AssetCategory(
            name="home_equity",
            display_name="Home Equity",
            current_balance=home_equity,
            accessible_value=accessible,
            is_liquid=False,
            liquidation_timeframe=timeframe,
            recommended=recommended,
            recommendation_reason=reason,
            tax_implications="none",
            notes=notes,
        )

    # ==== 6. OTHER REAL ESTATE ====
    other_re_equity = profile.other_real_estate - profile.other_real_estate_debt_balance
    if other_re_equity > 0:
        # Assume 10% transaction costs + capital gains
        accessible = other_re_equity * 0.80

        categories["other_real_estate"] = AssetCategory(
            name="other_real_estate",
            display_name="🏘️ Other Real Estate",
            current_balance=other_re_equity,
            accessible_value=accessible,
            is_liquid=False,
            liquidation_timeframe="3-6_months",
            recommended=True,
            recommendation_reason="Can be sold or used as collateral",
            tax_implications="capital_gains",
            notes="Rental property, land, vacation homes",
        )

    # ==== 7. OTHER RESOURCES ====
    if profile.other_resources > 0:
        categories["other_resources"] = AssetCategory(
            name="other_resources",
            display_name="💎 Other Resources",
            current_balance=profile.other_resources,
            accessible_value=profile.other_resources * 0.90,
            is_liquid=False,
            liquidation_timeframe="1-3_months",
            recommended=True,
            recommendation_reason="Additional resources available",
            tax_implications="none",
            notes="Trusts, collectibles, other assets",
        )

    return categories


def calculate_recommended_funding_order(
    asset_categories: dict[str, AssetCategory],
    care_recommendation: CareRecommendation | None = None,
    profile: FinancialProfile | None = None,
) -> tuple[list[str], dict[str, str]]:
    """
    Determine recommended order for using assets based on:
    - Liquidity (liquid first)
    - Tax efficiency (tax-free before taxable)
    - Cost (lowest cost first)
    - Care type (smart exclusions)
    
    Returns:
        (funding_order, funding_notes)
        - funding_order: List of asset category names in recommended order
        - funding_notes: Dict of category name -> explanation
    """

    # Default conservative order (liquidity first, tax-efficient, then less liquid)
    default_order = [
        "liquid_assets",          # 1. Most liquid, no tax
        "life_insurance",         # 2. Tax-free loans, relatively quick
        "retirement_accounts",    # 3. Taxable, but accessible
        "other_real_estate",      # 4. Illiquid, capital gains
        "annuities",              # 5. Surrender charges, keep for income
        "other_resources",        # 6. Varies by type
        "home_equity",            # 7. Last for in-home care (needed), earlier for facility
    ]

    # Filter to only categories that exist
    funding_order = [cat for cat in default_order if cat in asset_categories]

    # Adjust for Medicaid planning context
    if profile and profile.interested_in_spend_down:
        # Medicaid planning: Liquidate non-exempt assets ASAP
        funding_order = [
            "liquid_assets",
            "life_insurance",
            "retirement_accounts",  # Countable for Medicaid
            "annuities",
            "other_real_estate",
            "other_resources",
            # Note: Primary residence often exempt (up to certain value)
        ]

    # Generate notes for each category
    funding_notes = {}
    for i, cat_name in enumerate(funding_order, 1):
        category = asset_categories[cat_name]

        if i == 1:
            funding_notes[cat_name] = f"⭐ Start here - {category.recommendation_reason}"
        elif category.recommended:
            funding_notes[cat_name] = f"#{i} - {category.recommendation_reason}"
        else:
            funding_notes[cat_name] = f"Consider later - {category.recommendation_reason}"

    return funding_order, funding_notes


def calculate_extended_runway(
    monthly_gap: float,
    selected_assets: dict[str, bool],
    asset_categories: dict[str, AssetCategory],
) -> float | None:
    """
    Calculate how long care can be funded with selected assets.
    
    Args:
        monthly_gap: Monthly shortfall (positive number)
        selected_assets: Dict of asset_name -> bool (selected)
        asset_categories: Asset category details
        
    Returns:
        Extended runway in months, or None if no gap/indefinite coverage
    """

    if monthly_gap <= 0:
        return None  # No gap = indefinite coverage

    # Sum accessible value of selected assets
    total_selected = sum(
        asset_categories[name].accessible_value
        for name, selected in selected_assets.items()
        if selected and name in asset_categories
    )

    if total_selected == 0:
        return 0.0  # No assets selected

    # Calculate months of coverage
    extended_runway = total_selected / monthly_gap

    return extended_runway
