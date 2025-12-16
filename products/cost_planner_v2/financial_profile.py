"""
Financial Profile Aggregator for Cost Planner v2

Collects and aggregates data from all financial assessments into a unified
FinancialProfile structure for expert review and cost analysis.

Pattern: Data aggregation layer between assessments and expert review
Input: Individual assessment states from session_state
Output: Unified FinancialProfile ready for MCIP publishing and analysis
"""

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from products.cost_planner_v2.utils.financial_helpers import (
    asset_breakdown,
    income_breakdown,
    normalize_asset_data,
    normalize_income_data,
)


@dataclass
class FinancialProfile:
    """
    Unified financial profile aggregating all assessment data.

    This structure represents the complete financial picture of a user,
    collected from 6 financial assessments, ready for expert review analysis.
    """

    # ==== INCOME SOURCES ====
    ss_monthly: float = 0.0
    pension_monthly: float = 0.0
    has_partner: str = "no_partner"
    shared_finance_notes: str = ""
    partner_income_monthly: float = 0.0
    annuity_monthly: float = 0.0
    retirement_distributions_monthly: float = 0.0
    dividends_interest_monthly: float = 0.0
    rental_income_monthly: float = 0.0
    alimony_support_monthly: float = 0.0
    ltc_insurance_monthly: float = 0.0
    family_support_monthly: float = 0.0
    total_monthly_income: float = 0.0
    income_breakdown: dict[str, float] = field(default_factory=dict)

    # ==== ASSETS & RESOURCES ====
    checking_savings: float = 0.0
    investment_accounts: float = 0.0
    retirement_accounts_total: float = 0.0  # NEW: Sum of traditional, Roth, pension value
    primary_residence_value: float = 0.0
    primary_residence_has_debt: bool = False
    primary_residence_mortgage_balance: float = 0.0
    primary_residence_liquidity_window: str = "under_6_months"
    home_sale_interest: bool = False
    other_real_estate: float = 0.0
    other_real_estate_has_debt: bool = False
    other_real_estate_debt_balance: float = 0.0
    other_resources: float = 0.0
    asset_has_partner: str = "no_partner"
    asset_legal_restrictions: str = ""
    liquid_assets_has_loan: bool = False
    liquid_assets_loan_balance: float = 0.0
    asset_secured_loans: float = 0.0
    asset_other_debts: float = 0.0
    asset_debt_notes: str = ""
    asset_liquidity_concerns: str = "no_concerns"
    asset_liquidity_notes: str = ""
    total_asset_value: float = 0.0
    total_asset_debt: float = 0.0
    net_asset_value: float = 0.0
    asset_breakdown: dict[str, float] = field(default_factory=dict)

    # ==== HEALTH INSURANCE ====
    has_medicare: bool = False
    medicare_parts: list = field(default_factory=list)
    has_medicare_advantage: bool = False  # NEW: Was checkbox in JSON, not captured
    has_medicare_supplement: bool = False  # NEW: Was checkbox in JSON, not captured
    medicare_premium_monthly: float = 0.0

    has_medicaid: bool = False
    medicaid_covers_ltc: bool = False

    has_ltc_insurance: bool = False
    ltc_daily_benefit: float = 0.0
    ltc_benefit_period_months: int = 0
    ltc_elimination_days: int = 0
    ltc_monthly_premium: float = 0.0  # NEW: Monthly LTC insurance premium cost

    has_private_insurance: bool = False
    private_insurance_premium_monthly: float = 0.0

    # ==== HOME EQUITY & HOUSING ====
    owns_home: str = "other"  # own, rent, other
    home_value: float = 0.0
    mortgage_balance: float = 0.0
    monthly_carry: float = 0.0
    home_plan: str = "not_sure"  # keep, sell, rent_out, reverse_mortgage, not_sure
    commission_rate: float = 6.0  # For sell option
    reverse_mortgage_monthly_draw: float = 0.0
    home_equity: float = 0.0  # Calculated: home_value - mortgage_balance
    home_equity_strategy_outputs: dict[str, Any] = field(default_factory=dict)  # From helpers
    
    # ==== LIFE INSURANCE ====
    has_life_insurance: str = "no"
    life_insurance_type: str | None = None
    life_insurance_face_value: float = 0.0
    life_insurance_cash_value: float = 0.0
    life_insurance_premium_monthly: float = 0.0

    has_annuities: str = "no"
    annuity_current_value: float = 0.0
    annuity_monthly_income: float = 0.0

    total_accessible_life_value: float = 0.0

    # ==== VA BENEFITS ====
    has_va_benefits: str = "no"
    va_disability_rating: int = 0
    va_disability_monthly: float = 0.0
    va_pension_monthly: float = 0.0

    has_aid_attendance: str = "no"
    aid_attendance_monthly: float = 0.0

    total_va_benefits_monthly: float = 0.0

    # ==== MEDICAID PLANNING ====
    medicaid_status: str = "not_enrolled"
    interested_in_spend_down: bool = False
    spend_down_timeline: str | None = None
    has_estate_plan: list = field(default_factory=list)
    aware_of_asset_limits: str = "no"  # NEW: "no", "somewhat", "yes" - affects recommendations
    current_asset_position: str = "unknown"  # NEW: "under_limit", "near_limit", "over_limit", "unknown" - CRITICAL for timeline
    aware_of_estate_recovery: bool = False  # NEW: User awareness of Medicaid estate recovery
    interested_in_elder_law: bool = False  # NEW: Referral intent for elder law attorney

    # ==== METADATA ====
    completeness_percentage: float = 0.0
    required_assessments_complete: bool = False
    optional_assessments_complete: dict = field(default_factory=dict)
    last_updated: str | None = None


def build_financial_profile(product_key: str = "cost_planner_v2") -> FinancialProfile:
    """
    Aggregate all assessment data into a unified FinancialProfile.

    Args:
        product_key: Product key for state management

    Returns:
        FinancialProfile with all collected data
    """
    profile = FinancialProfile()

    # Get tiles state (persistent assessment storage)
    tiles = st.session_state.get("tiles", {})
    product_tiles = tiles.get(product_key, {})
    assessments_state = product_tiles.get("assessments", {})

    # ==== INCOME ASSESSMENT ====
    income_raw = assessments_state.get("income", {})
    if income_raw:
        income_data = normalize_income_data(income_raw)
        profile.ss_monthly = float(income_data.get("ss_monthly", 0.0))
        profile.pension_monthly = float(income_data.get("pension_monthly", 0.0))
        profile.has_partner = income_data.get("has_partner", "no_partner")
        profile.shared_finance_notes = income_data.get("shared_finance_notes", "")
        profile.partner_income_monthly = float(income_data.get("partner_income_monthly", 0.0))
        profile.annuity_monthly = float(income_data.get("annuity_monthly", 0.0))
        profile.retirement_distributions_monthly = float(
            income_data.get("retirement_distributions_monthly", 0.0)
        )
        profile.dividends_interest_monthly = float(income_data.get("dividends_interest_monthly", 0.0))
        profile.rental_income_monthly = float(income_data.get("rental_income_monthly", 0.0))
        profile.alimony_support_monthly = float(income_data.get("alimony_support_monthly", 0.0))
        profile.ltc_insurance_monthly = float(income_data.get("ltc_insurance_monthly", 0.0))
        profile.family_support_monthly = float(income_data.get("family_support_monthly", 0.0))
        profile.total_monthly_income = float(
            income_data.get("total_monthly_income", profile.total_monthly_income)
        )
        profile.income_breakdown = income_breakdown(income_data)

    # ==== ASSETS ASSESSMENT ====
    assets_raw = assessments_state.get("assets", {})
    if assets_raw:
        assets_data = normalize_asset_data(assets_raw)
        profile.asset_has_partner = assets_data.get("asset_has_partner", "no_partner")
        profile.asset_legal_restrictions = assets_data.get("asset_legal_restrictions", "")
        profile.checking_savings = float(assets_data.get("checking_savings", 0.0))
        profile.investment_accounts = float(assets_data.get("investment_accounts", 0.0))
        profile.retirement_accounts_total = float(assets_data.get("retirement_accounts_total", 0.0))  # NEW
        profile.liquid_assets_has_loan = bool(assets_data.get("liquid_assets_has_loan", False))
        profile.liquid_assets_loan_balance = float(
            assets_data.get("liquid_assets_loan_balance", 0.0)
        )
        profile.primary_residence_value = float(assets_data.get("primary_residence_value", 0.0))
        profile.primary_residence_has_debt = bool(
            assets_data.get("primary_residence_has_debt", False)
        )
        profile.primary_residence_mortgage_balance = float(
            assets_data.get("primary_residence_mortgage_balance", 0.0)
        )
        profile.primary_residence_liquidity_window = assets_data.get(
            "primary_residence_liquidity_window", "under_6_months"
        )
        profile.home_sale_interest = bool(assets_data.get("home_sale_interest", False))
        profile.other_real_estate = float(assets_data.get("other_real_estate", 0.0))
        profile.other_real_estate_has_debt = bool(
            assets_data.get("other_real_estate_has_debt", False)
        )
        profile.other_real_estate_debt_balance = float(
            assets_data.get("other_real_estate_debt_balance", 0.0)
        )
        profile.other_resources = float(assets_data.get("other_resources", 0.0))
        profile.asset_secured_loans = float(assets_data.get("asset_secured_loans", 0.0))
        profile.asset_other_debts = float(assets_data.get("asset_other_debts", 0.0))
        profile.asset_debt_notes = assets_data.get("asset_debt_notes", "")
        profile.asset_liquidity_concerns = assets_data.get(
            "asset_liquidity_concerns", "no_concerns"
        )
        profile.asset_liquidity_notes = assets_data.get("asset_liquidity_notes", "")
        profile.total_asset_value = float(
            assets_data.get("total_asset_value", profile.total_asset_value)
        )
        profile.total_asset_debt = float(assets_data.get("total_asset_debt", 0.0))
        profile.net_asset_value = float(
            assets_data.get(
                "net_asset_value", max(profile.total_asset_value - profile.total_asset_debt, 0.0)
            )
        )
        profile.asset_breakdown = asset_breakdown(assets_data)

    # ==== HEALTH INSURANCE ASSESSMENT ====
    health_data = assessments_state.get("health_insurance", {})
    if health_data:
        # Fix: JSON sends "yes"/"no" strings, not booleans
        has_medicare_val = health_data.get("has_medicare", "no")
        profile.has_medicare = has_medicare_val == "yes"
        profile.medicare_parts = health_data.get("medicare_parts", [])
        profile.has_medicare_advantage = bool(health_data.get("medicare_advantage", False))
        profile.has_medicare_supplement = bool(health_data.get("medicare_supplement", False))
        # Fix: JSON key is medicare_monthly_premium, not medicare_premium_monthly
        profile.medicare_premium_monthly = float(
            health_data.get("medicare_monthly_premium", health_data.get("medicare_premium_monthly", 0))
        )

        has_medicaid_val = health_data.get("has_medicaid", "no")
        profile.has_medicaid = has_medicaid_val == "yes"
        profile.medicaid_covers_ltc = bool(health_data.get("medicaid_covers_ltc", False))

        has_ltc_val = health_data.get("has_ltc_insurance", "no")
        profile.has_ltc_insurance = has_ltc_val == "yes"
        profile.ltc_daily_benefit = float(health_data.get("ltc_daily_benefit", 0))
        profile.ltc_benefit_period_months = int(health_data.get("ltc_benefit_period_months", 0))
        profile.ltc_elimination_days = int(health_data.get("ltc_elimination_days", 0))
        profile.ltc_monthly_premium = float(health_data.get("ltc_monthly_premium", 0))  # NEW

        has_private_val = health_data.get("has_private_insurance", "no")
        profile.has_private_insurance = has_private_val == "yes"
        profile.private_insurance_premium_monthly = float(
            health_data.get("private_insurance_premium_monthly", 0)
        )

    # ==== LIFE INSURANCE ASSESSMENT ====
    life_data = assessments_state.get("life_insurance", {})
    if life_data:
        profile.has_life_insurance = life_data.get("has_life_insurance", "no")
        profile.life_insurance_type = life_data.get("life_insurance_type")
        profile.life_insurance_face_value = float(life_data.get("life_insurance_face_value", 0))
        profile.life_insurance_cash_value = float(life_data.get("life_insurance_cash_value", 0))
        profile.life_insurance_premium_monthly = float(
            life_data.get("life_insurance_premium_monthly", 0)
        )

        profile.has_annuities = life_data.get("has_annuities", "no")
        profile.annuity_current_value = float(life_data.get("annuity_current_value", 0))
        profile.annuity_monthly_income = float(life_data.get("annuity_monthly_income", 0))

        profile.total_accessible_life_value = (
            profile.life_insurance_cash_value + profile.annuity_current_value
        )

    # ==== HOME EQUITY & HOUSING ASSESSMENT ====
    home_equity_data = assessments_state.get("home_equity", {})
    if home_equity_data:
        profile.owns_home = home_equity_data.get("owns_home", "other")
        profile.home_value = float(home_equity_data.get("home_value", 0.0))
        profile.mortgage_balance = float(home_equity_data.get("mortgage_balance", 0.0))
        profile.monthly_carry = float(home_equity_data.get("monthly_carry", 0.0))
        profile.home_plan = home_equity_data.get("home_plan", "not_sure")
        profile.commission_rate = float(home_equity_data.get("commission_rate", 6.0))
        profile.reverse_mortgage_monthly_draw = float(
            home_equity_data.get("reverse_mortgage_monthly_draw", 0.0)
        )
        # Calculate equity
        profile.home_equity = max(profile.home_value - profile.mortgage_balance, 0.0)
        # Get strategy outputs if available
        profile.home_equity_strategy_outputs = home_equity_data.get("strategy_outputs", {})

    # ==== VA BENEFITS ASSESSMENT (optional - flag-gated) ====
    va_data = assessments_state.get("va_benefits", {})
    if va_data:
        profile.has_va_benefits = va_data.get("has_va_benefits", "no")

        # Parse VA disability rating - JSON sends ranges like "10-30", "70-90", "100", "none"
        rating_str = va_data.get("va_disability_rating", "none")
        rating_map = {
            "none": 0,
            "10-30": 20,  # Use midpoint
            "40-60": 50,  # Use midpoint
            "70-90": 80,  # Use midpoint
            "100": 100,
        }
        profile.va_disability_rating = rating_map.get(rating_str, 0)

        profile.va_disability_monthly = float(va_data.get("va_disability_monthly", 0))
        profile.va_pension_monthly = float(va_data.get("va_pension_monthly", 0))

        profile.has_aid_attendance = va_data.get("has_aid_attendance", "no")
        profile.aid_attendance_monthly = float(va_data.get("aid_attendance_monthly", 0))

        profile.total_va_benefits_monthly = (
            profile.va_disability_monthly
            + profile.va_pension_monthly
            + profile.aid_attendance_monthly
        )

    # ==== MEDICAID PLANNING ASSESSMENT (removed - users routed to off-ramp) ====
    # Medicaid users are now routed to Medicaid.gov before reaching assessments
    # No need to collect this data as we cannot help with Medicaid placement

    # ==== CALCULATE METADATA ====
    profile.completeness_percentage = _calculate_completeness(assessments_state)
    profile.required_assessments_complete = _check_required_complete(assessments_state)
    profile.optional_assessments_complete = {
        "va_benefits": bool(va_data),
    }

    import datetime

    profile.last_updated = datetime.datetime.now().isoformat()

    return profile


def _calculate_completeness(assessments_state: dict[str, Any]) -> float:
    """
    Calculate overall completeness percentage based on completed assessments.

    Required assessments (Income, Assets) count more heavily.
    """
    # Required assessments (50% weight each = 100% total)
    required_complete = 0
    if assessments_state.get("income"):
        required_complete += 50
    if assessments_state.get("assets"):
        required_complete += 50

    # Optional assessments (split remaining weight)
    optional_complete = 0
    optional_assessments = [
        "health_insurance",
        "life_insurance",
        "va_benefits",
    ]
    completed_optional = sum(1 for key in optional_assessments if assessments_state.get(key))

    # If any optional completed, they don't add to base score but show engagement
    # Keep it simple: required = 100%, optional enhances but doesn't count toward completion

    return float(required_complete)


def _check_required_complete(assessments_state: dict[str, Any]) -> bool:
    """Check if both required assessments (Income, Assets) are complete."""
    return bool(assessments_state.get("income") and assessments_state.get("assets"))


def get_financial_profile(product_key: str = "cost_planner_v2") -> FinancialProfile | None:
    """
    Get cached financial profile or build new one.

    This is the primary entry point for accessing financial data.
    """
    # Check if we have a cached profile
    cache_key = f"{product_key}_financial_profile"

    # For now, always rebuild (later we can add caching logic)
    profile = build_financial_profile(product_key)

    # Cache it
    st.session_state[cache_key] = profile

    return profile


def publish_to_mcip(analysis, profile: FinancialProfile) -> bool:
    """
    Publish financial analysis summary to MCIP contracts.

    Creates MCIP FinancialProfile contract with summary data from expert analysis.

    Args:
        analysis: ExpertReviewAnalysis with calculated metrics
        profile: FinancialProfile with assessment data (for metadata)

    Returns:
        True if publish succeeded, False otherwise
    """
    try:
        from datetime import datetime

        from core.mcip import MCIP
        from core.mcip import FinancialProfile as MCIPFinancialProfile

        # Create MCIP contract with summary metrics
        mcip_profile = MCIPFinancialProfile(
            estimated_monthly_cost=analysis.estimated_monthly_cost,
            coverage_percentage=analysis.coverage_percentage,
            gap_amount=analysis.monthly_gap,
            runway_months=int(analysis.runway_months) if analysis.runway_months else 0,
            confidence=profile.completeness_percentage / 100.0,  # Convert to 0.0-1.0
            generated_at=datetime.now().isoformat(),
            status="complete" if profile.required_assessments_complete else "in_progress",
        )

        # Publish to MCIP
        MCIP.publish_financial_profile(mcip_profile)

        return True

    except Exception as e:
        st.error(f"Failed to publish financial profile to MCIP: {e}")
        return False
