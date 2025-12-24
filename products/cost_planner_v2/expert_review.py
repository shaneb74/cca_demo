"""
Expert Financial Review for Cost Planner v2

Clean, professional display of financial analysis with recommendations.
Communication through Navi panel, minimal UI clutter.
"""

import streamlit as st

from core.mcip import MCIP
from core.ui import render_navi_panel_v2
from products.cost_planner_v2.expert_formulas import calculate_expert_review
from products.cost_planner_v2.financial_profile import get_financial_profile, publish_to_mcip


def _ensure_financial_defaults():
    """
    Seed default asset selections once per session.
    
    DEFAULTS (first render only):
    - ✅ Monthly Income: Always included (built into base calculation)
    - ✅ Liquid Assets: Selected by default
    - ❌ All other assets: NOT selected (retirement, home equity, etc.)
    
    PROTECTION:
    - Only seeds once per uid/session
    - Never resets after user makes changes
    """
    ss = st.session_state
    
    # Protect against resetting after the user changes toggles
    if ss.get("_fin_defaults_seeded"):
        return
    
    uid = ss.get("uid") or "anon"
    
    # Seed only once per uid/session
    if ss.get(f"_fin_seeded_for_{uid}"):
        ss["_fin_defaults_seeded"] = True
        return
    
    # Initialize expert_review_selected_assets if not exists
    # Default: ONLY liquid_assets selected (income is always in base calc)
    if "expert_review_selected_assets" not in ss:
        ss["expert_review_selected_assets"] = {}
    
    # Set defaults for known asset categories (will be overridden by actual categories later)
    # Using setdefault ensures we don't overwrite existing user selections
    defaults = {
        "liquid_assets": True,           # ✅ Selected by default
        "retirement_accounts": False,    # ❌ Not selected
        "life_insurance": False,         # ❌ Not selected
        "annuities": False,              # ❌ Not selected
        "home_equity": False,            # ❌ Not selected
        "other_real_estate": False,      # ❌ Not selected
        "other_resources": False,        # ❌ Not selected
    }
    
    for key, default_value in defaults.items():
        ss["expert_review_selected_assets"].setdefault(key, default_value)
    
    # Mark as seeded
    ss[f"_fin_seeded_for_{uid}"] = True
    ss["_fin_defaults_seeded"] = True
    
    # Debug log (remove after verification)
    print("[FIN_DEFAULTS]", 
          "liquid_assets=", ss["expert_review_selected_assets"].get("liquid_assets"),
          "retirement_accounts=", ss["expert_review_selected_assets"].get("retirement_accounts"),
          "home_equity=", ss["expert_review_selected_assets"].get("home_equity"))


def render():
    """
    Render expert financial review page.

    Shows financial analysis with clean, professional design.
    Navi handles all communication, UI stays minimal.
    """

    # Render compact Navi panel at top
    from core.navi_module import render_module_navi_coach
    render_module_navi_coach(
        title_text="Planning Opportunity",
        body_text="We'll show coverage from income and assets and highlight next steps.",
        tip_text="Your income provides partial coverage. Adding more resources will help extend your plan.",
    )

    # Apply width constraints like other clean pages
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Seed default selections once per session (income + liquid assets only)
    _ensure_financial_defaults()

    # Get financial profile
    profile = get_financial_profile()

    # Check if required assessments complete
    if not profile.required_assessments_complete:
        _render_incomplete_state()
        return

    # Get GCP recommendation for cost estimation
    care_recommendation = MCIP.get_care_recommendation()

    # Get ZIP code from intro
    zip_code = st.session_state.get("cost_v2_zip")

    # Check if we have an estimate from the intro page
    intro_estimate = st.session_state.get("cost_v2_quick_estimate")
    estimated_monthly_cost = None
    if intro_estimate and "estimate" in intro_estimate:
        estimate_data = intro_estimate["estimate"]
        # Handle both dict (persisted) and CostEstimate object (legacy)
        if isinstance(estimate_data, dict):
            # FIX: Use monthly_total instead of monthly_adjusted to match what user saw in Quick Estimate
            # monthly_adjusted = care-only, monthly_total = care + home carry (what was displayed)
            estimated_monthly_cost = estimate_data.get("monthly_total", estimate_data["monthly_adjusted"])
            # [FA_DEBUG] Log what FA received
            print("\n[FA_DEBUG] ========== FA RECEIVED FROM QUICK ESTIMATE ==========")
            print(f"[FA_DEBUG] Selected Plan: {estimate_data.get('selected_plan', 'N/A')}")
            print(f"[FA_DEBUG] Care Type: {estimate_data.get('care_type', 'N/A')}")
            print(f"[FA_DEBUG] Monthly Total Used (care+home): ${estimated_monthly_cost:,.0f}")
            print(f"[FA_DEBUG] Care-Only Would Be: ${estimate_data.get('monthly_adjusted', 0):,.0f}")
            print("[FA_DEBUG] ====================================================\n")
        else:
            estimated_monthly_cost = estimate_data.monthly_adjusted

    # Calculate expert review
    analysis = calculate_expert_review(
        profile=profile,
        care_recommendation=care_recommendation,
        zip_code=zip_code,
        estimated_monthly_cost=estimated_monthly_cost,
    )

    # Publish summary to MCIP
    publish_to_mcip(analysis, profile)

    # Navi guidance removed - now using compact panel at page top (line 83)
    # Old _render_navi_guidance() created duplicate "Planning Opportunity" panel

    # Main content container
    st.markdown('<div class="sn-app module-container">', unsafe_allow_html=True)

    # Page header
    st.markdown(
        '<div class="mod-head"><div class="mod-head-row"><h2 class="h2">Financial Review</h2></div></div>',
        unsafe_allow_html=True,
    )

    # 1. Financial Summary Banner (consolidated metrics)
    _render_financial_summary_banner(analysis, profile)

    st.markdown('<div style="margin: 32px 0;"></div>', unsafe_allow_html=True)

    # 2. Available Resources (expandable cards per category)
    if analysis.asset_categories:
        _render_available_resources_cards(analysis, profile)
        st.markdown('<div style="margin: 32px 0;"></div>', unsafe_allow_html=True)

    st.markdown('<div style="margin: 48px 0;"></div>', unsafe_allow_html=True)

    # Navigation
    _render_navigation()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_incomplete_state():
    """Show state when required assessments not complete."""

    # Navi panel removed - compact Navi at page top handles all messaging

    # Minimal content
    st.markdown('<div class="sn-app module-container">', unsafe_allow_html=True)
    st.markdown(
        '<div class="mod-head"><div class="mod-head-row"><h2 class="h2">Financial Review</h2></div></div>',
        unsafe_allow_html=True,
    )

    st.info("Complete Income and Assets assessments to unlock your personalized financial review.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("← Back to Assessments", use_container_width=True, type="primary"):
            # Update URL query params for browser navigation
            st.query_params["page"] = "cost_v2"
            st.query_params["step"] = "assessments"
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            
            st.session_state.cost_v2_step = "assessments"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _get_dynamic_coverage_label(selected_assets, asset_categories):
    """
    Generate dynamic coverage label based on selected resources.
    
    Examples:
    - No assets: "Coverage from Income"
    - Liquid only: "Coverage from Income and Liquid Assets"
    - Retirement only: "Coverage from Income and Retirement Accounts"
    - Both: "Coverage from Income, Liquid Assets, and Retirement Accounts"
    """
    # Asset name to friendly label mapping
    friendly_names = {
        "liquid_assets": "Liquid Assets",
        "retirement_accounts": "Retirement Accounts",
        "life_insurance": "Life Insurance",
        "annuities": "Annuities",
        "home_equity": "Home Equity",
        "other_real_estate": "Real Estate"
    }

    # Get selected asset names
    selected_names = [
        friendly_names.get(name, name.replace("_", " ").title())
        for name, selected in selected_assets.items()
        if selected and name in asset_categories
    ]

    # Build label
    if not selected_names:
        return "Coverage from Income"
    elif len(selected_names) == 1:
        return f"Coverage from Income and {selected_names[0]}"
    else:
        # Join with commas and "and" before last item
        all_but_last = ", ".join(selected_names[:-1])
        return f"Coverage from Income, {all_but_last}, and {selected_names[-1]}"


def _render_navi_guidance(analysis, profile):
    """
    Render Navi panel with contextual guidance based on analysis.
    
    Dynamic messaging based on:
    - Current coverage percentage from income
    - Selected assets and resulting coverage duration
    - Coverage adequacy tiers
    """

    from products.cost_planner_v2.expert_formulas import calculate_extended_runway

    # Get current selections
    selected_assets = st.session_state.get("expert_review_selected_assets", {})

    # Calculate extended runway with selections
    extended_runway = calculate_extended_runway(
        analysis.monthly_gap if analysis.monthly_gap > 0 else 0,
        selected_assets,
        analysis.asset_categories,
    )

    # Calculate coverage duration in human-friendly format
    display_months = extended_runway if extended_runway and extended_runway > 0 else 0

    if analysis.monthly_gap <= 0:
        coverage_duration = "Indefinite"
        coverage_years = 999  # Treat as excellent
    elif display_months > 0:
        years = int(display_months / 12)
        months = int(display_months % 12)
        if years > 0:
            coverage_duration = f"{years} year{'s' if years != 1 else ''}"
            if months > 0:
                coverage_duration += f", {months} month{'s' if months != 1 else ''}"
        else:
            coverage_duration = f"{int(display_months)} month{'s' if display_months != 1 else ''}"
        coverage_years = display_months / 12
    else:
        coverage_duration = "Immediate action needed"
        coverage_years = 0

    # Count selected assets
    selected_count = sum(1 for selected in selected_assets.values() if selected)

    # DYNAMIC MESSAGING based on coverage adequacy and selections
    income_coverage_pct = analysis.coverage_percentage

    # Fully funded (30+ years OR income alone ≥90%)
    if coverage_years >= 30 or income_coverage_pct >= 90:
        title = "Excellent Financial Position"
        reason = f"**Coverage Duration:** {coverage_duration}  \n\nYour income and resources cover your estimated care costs for the long term."
        encouragement = {
            "icon": "",
            "text": "Excellent. Your income and resources cover your care for 30 years or more.",
            "status": "complete",
        }

    # Very strong coverage (15-29 years)
    elif 15 <= coverage_years < 30:
        title = "Strong Financial Security"
        reason = f"**Coverage Duration:** {coverage_duration}  \n\nYou have substantial coverage that funds care well into the future."

        if selected_count > 0:
            encouragement = {
                "icon": "",
                "text": "You're in good shape. Your resources fund care for nearly two decades.",
                "status": "complete",
            }
        else:
            encouragement = {
                "icon": "",
                "text": "Strong foundation. Your income provides excellent long-term coverage.",
                "status": "active",
            }

    # Moderate coverage (5-14 years)
    elif 5 <= coverage_years < 15:
        title = "Solid Financial Foundation"
        reason = f"**Coverage Duration:** {coverage_duration}  \n\nYour resources provide meaningful coverage. Let's review options to extend your plan."

        if selected_count > 0 and coverage_years >= 10:
            encouragement = {
                "icon": "",
                "text": "You're building a sustainable plan. Your combined resources provide strong coverage.",
                "status": "active",
            }
        elif selected_count > 0:
            encouragement = {
                "icon": "�",
                "text": "Good progress. Adding resources extends your coverage meaningfully.",
                "status": "active",
            }
        else:
            encouragement = {
                "icon": "",
                "text": "Your income provides a strong foundation. Adding available resources can extend your plan.",
                "status": "active",
            }

    # Limited coverage (under 5 years)
    else:
        title = "Planning Opportunity"
        reason = f"**Coverage Duration:** {coverage_duration}  \n\nLet's work together to build a sustainable care funding strategy."

        if selected_count > 0 and coverage_years >= 2:
            encouragement = {
                "icon": "�",
                "text": "Excellent progress! Your combined resources create a sustainable plan.",
                "status": "active",
            }
        elif selected_count > 0:
            encouragement = {
                "icon": "📋",
                "text": "Your income provides partial coverage. Adding more resources will help extend your plan.",
                "status": "active",
            }
        else:
            encouragement = {
                "icon": "📋",
                "text": "Your income provides a foundation. Adding available resources can extend your coverage.",
                "status": "warning",
            }

    # Context chips - removed (info now in reason text)
    context_chips = []

    # DEPRECATED: Hero Navi panel removed - using compact panel at page top instead
    # render_navi_panel_v2(
    #     title=title,
    #     reason=reason,
    #     encouragement=encouragement,
    #     context_chips=context_chips,
    #     primary_action={"label": "", "route": ""},
    #     variant="module",
    # )


def _calculate_timeline_segments(analysis, selected_assets):
    """
    Calculate timeline segments for Genworth-style visualization.
    
    Returns:
    - income_years: Years covered by income alone
    - asset_years: Additional years covered by assets
    - total_years: Total coverage years
    - timeline_max: Fixed horizon (30 years)
    """
    from products.cost_planner_v2.expert_formulas import calculate_extended_runway

    timeline_max = 30  # Fixed 30-year horizon

    # Calculate income-only coverage
    if analysis.monthly_gap <= 0:
        # Income covers everything
        income_years = timeline_max
        asset_years = 0
        total_years = timeline_max
    elif analysis.monthly_gap > 0:
        # Calculate how long income alone would last (infinite if no gap)
        # Since there's a gap, income alone provides 0 additional runway
        # The coverage_percentage tells us what portion of costs income covers
        income_coverage_ratio = analysis.coverage_percentage / 100.0

        # If monthly_gap > 0, income alone doesn't sustain care
        # But we need to show the partial coverage it provides
        # Use the total extended runway and back out the asset contribution

        total_months = calculate_extended_runway(
            analysis.monthly_gap,
            selected_assets,
            analysis.asset_categories,
        ) or 0

        # Calculate with no assets to get income-only baseline
        no_assets = dict.fromkeys(selected_assets.keys(), False)
        income_only_months = calculate_extended_runway(
            analysis.monthly_gap,
            no_assets,
            analysis.asset_categories,
        ) or 0

        income_years = min(income_only_months / 12.0, timeline_max)
        total_years = min(total_months / 12.0, timeline_max)
        asset_years = max(total_years - income_years, 0)

    return {
        "income_years": income_years,
        "asset_years": asset_years,
        "total_years": total_years,
        "timeline_max": timeline_max,
        "exceeds_timeline": total_years >= timeline_max
    }


def _render_financial_summary_banner(analysis, profile):
    """
    Render unified Financial Summary banner with all key metrics.
    
    Displays:
    - Coverage Duration (prominent)
    - Estimated Care Cost
    - Monthly Income
    - Monthly Shortfall
    - Total Assets / Debts / Net Available (if debt exists)
    - Years of Coverage Timeline (Genworth-style visualization)
    """

    from products.cost_planner_v2.expert_formulas import calculate_extended_runway

    # Calculate coverage duration (with selected assets if any)
    selected_assets = st.session_state.get("expert_review_selected_assets", {})
    extended_runway = calculate_extended_runway(
        analysis.monthly_gap if analysis.monthly_gap > 0 else 0,
        selected_assets,
        analysis.asset_categories,
    )

    # Calculate total gross and net assets
    total_gross_assets = sum(
        cat.current_balance
        for cat in analysis.asset_categories.values()
    )
    total_debt = profile.total_asset_debt if hasattr(profile, 'total_asset_debt') else 0.0
    net_assets = max(total_gross_assets - total_debt, 0.0)

    # ALWAYS use extended_runway with current selections (don't fall back to analysis.runway_months)
    # This ensures consistency: duration reflects ONLY what user has checked
    extended_runway = calculate_extended_runway(
        analysis.monthly_gap if analysis.monthly_gap > 0 else 0,
        selected_assets,
        analysis.asset_categories,
    )

    # Determine which coverage duration to show
    if analysis.monthly_gap <= 0:
        # No gap - indefinite coverage
        display_months = None
        duration_label = "Coverage Duration"
    elif extended_runway and extended_runway > 0:
        # User has assets selected
        display_months = extended_runway
        duration_label = "Coverage Duration"
    else:
        # No assets selected or gap too large
        display_months = 0
        duration_label = "Coverage Duration"

    # Format coverage duration
    if display_months is None:
        coverage_duration = "Indefinite"
    elif display_months > 0:
        years = int(display_months / 12)
        months = int(display_months % 12)
        if years > 0:
            coverage_duration = f"{years} year{'s' if years != 1 else ''}"
            if months > 0:
                coverage_duration += f", {months} month{'s' if months != 1 else ''}"
        else:
            coverage_duration = f"{int(display_months)} month{'s' if display_months != 1 else ''}"
    else:
        coverage_duration = "Immediate action needed"

    # Calculate total selected assets value
    total_selected = sum(
        analysis.asset_categories.get(name, type('obj', (), {'accessible_value': 0})).accessible_value
        for name, selected in selected_assets.items()
        if selected and name in analysis.asset_categories
    )

    # Determine surplus/shortfall label and color
    surplus_label = "Monthly Surplus" if analysis.monthly_gap < 0 else "Monthly Shortfall"
    surplus_color = "var(--success-fg)" if analysis.monthly_gap < 0 else "var(--error-fg)"

    # Calculate timeline segments for Genworth-style visualization
    timeline = _calculate_timeline_segments(analysis, selected_assets)

    # Get dynamic coverage label based on selected resources
    coverage_label = _get_dynamic_coverage_label(selected_assets, analysis.asset_categories)

    # Format timeline display text
    total_years_int = int(timeline["total_years"])
    total_months_remainder = int((timeline["total_years"] - total_years_int) * 12)

    if timeline["exceeds_timeline"]:
        timeline_headline = "Your resources fully fund care for 30+ years"
    elif total_years_int > 0:
        if total_months_remainder > 0:
            timeline_headline = f"Your {coverage_label.lower().replace('coverage from ', '')} funds care for {total_years_int} year{'s' if total_years_int != 1 else ''}, {total_months_remainder} month{'s' if total_months_remainder != 1 else ''}"
        else:
            timeline_headline = f"Your {coverage_label.lower().replace('coverage from ', '')} funds care for {total_years_int} year{'s' if total_years_int != 1 else ''}"
    else:
        timeline_headline = "Your current income provides partial coverage"

    # Calculate percentages for timeline bar segments
    income_pct = (timeline["income_years"] / timeline["timeline_max"]) * 100
    asset_pct = (timeline["asset_years"] / timeline["timeline_max"]) * 100
    total_pct = min((timeline["total_years"] / timeline["timeline_max"]) * 100, 100)
    gap_pct = max(100 - total_pct, 0)

    # Build asset contribution line if applicable
    asset_line = f'<div style="font-size: 13px; color: var(--success-fg); margin-top: 8px; font-weight: 600;">+ Assets: ${total_selected:,.0f}</div>' if total_selected > 0 else ''

    # Build debt section if applicable
    debt_section = ""
    if total_debt > 0:
        debt_section = f"""
<div style="background: rgba(255,245,235,0.7); padding: 16px 20px; border-radius: 12px; border: 1px solid #ffc107; margin-bottom: 24px;">
<div style="font-size: 12px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px;">Asset Debt Considerations</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
<span style="font-size: 14px; color: var(--text-primary);">Total Assets (Gross)</span>
<span style="font-size: 16px; font-weight: 600; color: var(--text-primary);">${total_gross_assets:,.0f}</span>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
<span style="font-size: 14px; color: var(--error-fg);">Less: Debts Against Assets</span>
<span style="font-size: 16px; font-weight: 600; color: var(--error-fg);">-${total_debt:,.0f}</span>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 2px solid var(--border-secondary);">
<span style="font-size: 14px; font-weight: 700; color: var(--text-primary);">Net Available Assets</span>
<span style="font-size: 18px; font-weight: 700; color: var(--primary-fg);">${net_assets:,.0f}</span>
</div>
<div style="font-size: 12px; color: var(--text-secondary); margin-top: 8px; font-style: italic;">Calculations use net values after debt obligations</div>
</div>
"""

    # Build unified banner HTML (NO leading whitespace)
    banner_html = f"""<div style="background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 16px; padding: 32px; border: 2px solid var(--border-primary); box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 8px;">
<div style="display: flex; align-items: center; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 2px solid var(--border-secondary);">
<div style="font-size: 18px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 1px;">Financial Summary</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 28px;">
<div style="background: rgba(255,255,255,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--border-secondary);">
<div style="font-size: 12px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;">{duration_label}</div>
<div style="font-size: 36px; font-weight: 700; color: var(--primary-fg); line-height: 1.1;">{coverage_duration}</div>
{asset_line}
</div>
<div style="background: rgba(255,255,255,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--border-secondary);">
<div style="font-size: 12px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;">Estimated Care Cost</div>
<div style="font-size: 36px; font-weight: 700; color: var(--text-primary); line-height: 1.1;">${analysis.estimated_monthly_cost:,.0f}</div>
<div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; font-weight: 500;">per month</div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 28px;">
<div style="background: rgba(255,255,255,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--border-secondary);">
<div style="font-size: 12px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;">Monthly Income</div>
<div style="font-size: 32px; font-weight: 700; color: var(--text-primary); line-height: 1.1;">${analysis.total_monthly_income + analysis.total_monthly_benefits:,.0f}</div>
<div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; font-weight: 500;">per month</div>
</div>
<div style="background: rgba(255,255,255,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--border-secondary);">
<div style="font-size: 12px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;">{surplus_label}</div>
<div style="font-size: 32px; font-weight: 700; color: {surplus_color}; line-height: 1.1;">${abs(analysis.monthly_gap):,.0f}</div>
<div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; font-weight: 500;">per month</div>
</div>
</div>
{debt_section}
<div style="padding: 24px; background: rgba(255,255,255,0.7); border-radius: 12px; border: 1px solid var(--border-secondary);">
<div style="margin-bottom: 20px;">
<div style="font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; line-height: 1.4;">{timeline_headline}</div>
<div style="font-size: 13px; color: var(--text-secondary); font-weight: 500;">{coverage_label}</div>
</div>
<div style="position: relative; width: 100%; height: 50px; background: #f5f5f5; border-radius: 8px; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.08);">
<div style="position: absolute; left: 0; top: 0; width: {income_pct}%; height: 100%; background: linear-gradient(90deg, #fbbf24 0%, #f59e0b 100%); transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);"></div>
<div style="position: absolute; left: {income_pct}%; top: 0; width: {asset_pct}%; height: 100%; background: linear-gradient(90deg, #34d399 0%, #10b981 100%); transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1), left 0.6s cubic-bezier(0.4, 0, 0.2, 1);"></div>
<div style="position: absolute; left: {total_pct}%; top: 0; width: {gap_pct}%; height: 100%; background: #e5e7eb;"></div>
<div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; justify-content: space-between; align-items: center; padding: 0 12px; pointer-events: none;">
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">0y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">5y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">10y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">15y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">20y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">25y</span>
<span style="font-size: 11px; font-weight: 600; color: #6b7280;">30y</span>
</div>
</div>
<div style="display: flex; gap: 20px; margin-top: 16px; flex-wrap: wrap;">
<div style="display: flex; align-items: center; gap: 8px;">
<div style="width: 16px; height: 16px; background: linear-gradient(90deg, #fbbf24 0%, #f59e0b 100%); border-radius: 3px;"></div>
<span style="font-size: 12px; color: var(--text-secondary); font-weight: 500;">Income Coverage ({timeline["income_years"]:.1f} years)</span>
</div>
<div style="display: flex; align-items: center; gap: 8px;">
<div style="width: 16px; height: 16px; background: linear-gradient(90deg, #34d399 0%, #10b981 100%); border-radius: 3px;"></div>
<span style="font-size: 12px; color: var(--text-secondary); font-weight: 500;">Assets Coverage ({timeline["asset_years"]:.1f} years)</span>
</div>
{'<div style="display: flex; align-items: center; gap: 8px;"><div style="width: 16px; height: 16px; background: #e5e7eb; border-radius: 3px;"></div><span style="font-size: 12px; color: var(--text-secondary); font-weight: 500;">Funding Gap</span></div>' if gap_pct > 0 else ''}
</div>
</div>
</div>"""

    st.markdown(banner_html, unsafe_allow_html=True)


def _render_income_cost_snapshot(analysis):
    """
    Render Income vs Cost Snapshot with progress bar.
    
    Simplified card showing: cost, income, shortfall, and visual progress bar.
    """

    # Create clean card with background and subtle shadow
    st.markdown('<div style="background: var(--surface-primary); border-radius: 12px; padding: 32px; border: 1px solid var(--border-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.05);">', unsafe_allow_html=True)

    # Three-column layout with visual dividers
    surplus_label = "Surplus" if analysis.monthly_gap < 0 else "Monthly Shortfall"
    surplus_color = "var(--success-fg)" if analysis.monthly_gap < 0 else "var(--error-fg)"

    html_content = f"""
<div style="display: flex; justify-content: space-between; align-items: stretch; gap: 24px; margin-bottom: 32px;">
    <div style="flex: 1; text-align: center; padding: 20px; background: rgba(255,255,255,0.5); border-radius: 10px; border: 1px solid var(--border-secondary);">
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Estimated Care Cost</div>
        <div style="font-size: 32px; font-weight: 700; color: var(--text-primary); line-height: 1.2;">${analysis.estimated_monthly_cost:,.0f}</div>
        <div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px; font-weight: 500;">/month</div>
    </div>
    <div style="flex: 1; text-align: center; padding: 20px; background: rgba(255,255,255,0.5); border-radius: 10px; border: 1px solid var(--border-secondary);">
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Monthly Income</div>
        <div style="font-size: 32px; font-weight: 700; color: var(--text-primary); line-height: 1.2;">${analysis.total_monthly_income + analysis.total_monthly_benefits:,.0f}</div>
        <div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px; font-weight: 500;">/month</div>
    </div>
    <div style="flex: 1; text-align: center; padding: 20px; background: rgba(255,255,255,0.5); border-radius: 10px; border: 1px solid var(--border-secondary);">
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">{surplus_label}</div>
        <div style="font-size: 32px; font-weight: 700; color: {surplus_color}; line-height: 1.2;">${abs(analysis.monthly_gap):,.0f}</div>
        <div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px; font-weight: 500;">/month</div>
    </div>
</div>
"""

    st.markdown(html_content, unsafe_allow_html=True)

    # Enhanced progress bar with bold label - using solid colors for visibility
    coverage_pct = min(analysis.coverage_percentage, 100)  # Cap at 100% for display
    progress_color = "#16a34a" if coverage_pct >= 80 else "#f59e0b" if coverage_pct >= 50 else "#dc2626"

    progress_html = f"""
<div style="margin-top: 8px;">
    <div style="font-size: 15px; color: var(--text-primary); margin-bottom: 12px; font-weight: 700; display: flex; justify-content: space-between; align-items: center;">
        <span>Coverage From Income</span>
        <span style="color: {progress_color};">{analysis.coverage_percentage:.0f}%</span>
    </div>
    <div style="width: 100%; background: var(--surface-secondary); border-radius: 10px; height: 40px; position: relative; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
        <div style="width: {coverage_pct}%; background: {progress_color}; height: 100%; border-radius: 10px; transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); position: relative;">
            <div style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font-size: 14px; font-weight: 700; color: white; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">
                {analysis.coverage_percentage:.0f}%
            </div>
        </div>
    </div>
</div>
"""

    st.markdown(progress_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_coverage_summary(analysis):
    """Render clean coverage summary - no banners, just facts."""

    # Coverage percentage (large, clean display)
    coverage_display = (
        f"{min(analysis.coverage_percentage, 999):.0f}%"
        if analysis.coverage_percentage < 1000
        else "999%+"
    )

    st.markdown(
        f"""
    <div style="text-align: center; padding: 24px 0;">
        <div style="font-size: 48px; font-weight: 700; color: var(--text-primary);">
            {coverage_display}
        </div>
        <div style="font-size: 14px; color: var(--text-secondary); margin-top: 8px;">
            Income Coverage of Estimated Care Costs
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Monthly breakdown (simple 4-column - added Runway!)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
        <div style="text-align: center; padding: 16px; background: var(--surface-primary); border-radius: 8px;">
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Estimated Cost</div>
            <div style="font-size: 20px; font-weight: 600; color: var(--text-primary);">
                ${analysis.estimated_monthly_cost:,.0f}<span style="font-size: 14px; font-weight: 400;">/mo</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
        <div style="text-align: center; padding: 16px; background: var(--surface-primary); border-radius: 8px;">
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Total Income</div>
            <div style="font-size: 20px; font-weight: 600; color: var(--text-primary);">
                ${analysis.total_monthly_income + analysis.total_monthly_benefits:,.0f}<span style="font-size: 14px; font-weight: 400;">/mo</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        gap_label = "Surplus" if analysis.monthly_gap < 0 else "Gap"
        gap_color = "var(--success-fg)" if analysis.monthly_gap < 0 else "var(--error-fg)"
        st.markdown(
            f"""
        <div style="text-align: center; padding: 16px; background: var(--surface-primary); border-radius: 8px;">
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">{gap_label}</div>
            <div style="font-size: 20px; font-weight: 600; color: {gap_color};">
                ${abs(analysis.monthly_gap):,.0f}<span style="font-size: 14px; font-weight: 400;">/mo</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col4:
        # Runway display - CRITICAL METRIC!
        if analysis.runway_months is not None and analysis.runway_months > 0:
            years = int(analysis.runway_months / 12)
            months = int(analysis.runway_months % 12)

            # Format display
            if years > 0:
                runway_value = f"{years}.{months // 3}" if months >= 3 else str(years)
                runway_unit = "yrs" if years > 1 else "yr"
            else:
                runway_value = str(int(analysis.runway_months))
                runway_unit = "mos"

            # Color based on runway length
            if analysis.runway_months >= 36:
                runway_color = "var(--success-fg)"
            elif analysis.runway_months >= 12:
                runway_color = "var(--warning-fg)"
            else:
                runway_color = "var(--error-fg)"

            st.markdown(
                f"""
            <div style="text-align: center; padding: 16px; background: var(--surface-primary); border-radius: 8px;">
                <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Coverage Runway</div>
                <div style="font-size: 20px; font-weight: 600; color: {runway_color};">
                    {runway_value}<span style="font-size: 14px; font-weight: 400;"> {runway_unit}</span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            # No gap or infinite coverage
            runway_label = "Indefinite" if analysis.monthly_gap <= 0 else "Immediate"
            runway_color = "var(--success-fg)" if analysis.monthly_gap <= 0 else "var(--error-fg)"

            st.markdown(
                f"""
            <div style="text-align: center; padding: 16px; background: var(--surface-primary); border-radius: 8px;">
                <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Coverage Runway</div>
                <div style="font-size: 20px; font-weight: 600; color: {runway_color};">
                    {runway_label}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def _render_financial_details(analysis, profile):
    """Render financial details as clean, simple list."""

    st.markdown("### Financial Details")

    # Income breakdown
    if analysis.total_monthly_income > 0:
        st.markdown(f"**Monthly Income:** ${analysis.total_monthly_income:,.0f}")

        # Show breakdown if helpful
        details = []
        if profile.ss_monthly > 0:
            details.append(f"Social Security ${profile.ss_monthly:,.0f}")
        if profile.pension_monthly > 0:
            details.append(f"Pension ${profile.pension_monthly:,.0f}")
        if profile.annuity_monthly > 0:
            details.append(f"Annuity ${profile.annuity_monthly:,.0f}")
        if profile.retirement_distributions_monthly > 0:
            details.append(f"Retirement Distributions ${profile.retirement_distributions_monthly:,.0f}")
        if profile.rental_income_monthly > 0:
            details.append(f"Rental Income ${profile.rental_income_monthly:,.0f}")

        if details:
            st.markdown(
                f"<div style='color: var(--text-secondary); font-size: 14px; margin-left: 16px;'>{', '.join(details)}</div>",
                unsafe_allow_html=True,
            )

    # Benefits
    if analysis.total_monthly_benefits > 0:
        st.markdown(f"**Monthly Benefits:** ${analysis.total_monthly_benefits:,.0f}")

    # Assets
    if analysis.total_liquid_assets > 0:
        st.markdown(f"**Liquid Assets:** ${analysis.total_liquid_assets:,.0f}")

        # Runway if applicable
        if analysis.runway_months is not None and analysis.runway_months > 0:
            years = int(analysis.runway_months / 12)
            months = int(analysis.runway_months % 12)

            if years > 0:
                runway_text = f"{years} year{'s' if years != 1 else ''}"
                if months > 0:
                    runway_text += f", {months} month{'s' if months != 1 else ''}"
            else:
                runway_text = f"{months} month{'s' if months != 1 else ''}"

            st.markdown(
                f"<div style='color: var(--text-secondary); font-size: 14px; margin-left: 16px;'>Coverage runway: {runway_text}</div>",
                unsafe_allow_html=True,
            )


def _render_available_resources_cards(analysis, profile):
    """
    Render available resources as clean, selectable cards.
    
    CLEAN APPROACH: Each asset is a card with:
    - Checkbox to include in funding plan
    - Key details visible without dropdowns
    - Clean, professional styling
    - All original functionality preserved
    """

    st.markdown("### Available Resources")

    # Only show if there are assets
    if not analysis.asset_categories:
        st.info("Complete additional financial assessments to see available resources.")
        return

    # Initialize selection state if not exists
    if "expert_review_selected_assets" not in st.session_state:
        st.session_state.expert_review_selected_assets = {}
    
    # Add any new categories that weren't seeded yet (default to False = not selected)
    for name in analysis.asset_categories.keys():
        if name not in st.session_state.expert_review_selected_assets:
            st.session_state.expert_review_selected_assets[name] = False

    # Guidance text based on context
    if analysis.monthly_gap > 0:
        st.markdown(
            f"Your income provides partial coverage. These assets can help bridge the ${abs(analysis.monthly_gap):,.0f}/month gap."
        )
    else:
        st.markdown(
            "Your income fully covers estimated care costs. These assets are available as reserves if needed."
        )

    # Show inline summary of selected assets
    selected_count = sum(1 for selected in st.session_state.expert_review_selected_assets.values() if selected)
    selected_total = sum(
        analysis.asset_categories[name].accessible_value
        for name, selected in st.session_state.expert_review_selected_assets.items()
        if selected and name in analysis.asset_categories
    )

    if selected_count > 0:
        st.markdown(
            f"""
            <div style="background: #e7f3ff; border-left: 4px solid #0066cc; padding: 12px 16px; border-radius: 8px; margin: 20px 0;">
                <span style="font-size: 14px; font-weight: 600; color: #003d7a;">
                    {selected_count} resource{'s' if selected_count != 1 else ''} selected — contributing ${selected_total:,.0f} toward care
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Real-time coverage impact calculation
        if analysis.monthly_gap > 0:
            months_covered = selected_total / analysis.monthly_gap
            years_covered = months_covered / 12
            
            if years_covered >= 1:
                coverage_display = f"{years_covered:.1f} years"
                coverage_detail = f"({months_covered:.0f} months)"
            else:
                coverage_display = f"{months_covered:.0f} months"
                coverage_detail = ""
                
            st.markdown(
                f"""
                <div style="background: #f0f9ff; border: 1px solid #0066cc; border-radius: 8px; padding: 16px; margin: 10px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: #333;">Coverage Duration:</span>
                        <span style="font-weight: 700; font-size: 18px; color: #0066cc;">{coverage_display} {coverage_detail}</span>
                    </div>
                    <div style="font-size: 13px; color: #666; margin-top: 4px;">
                        Selected assets cover the ${analysis.monthly_gap:,.0f}/month gap
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background: #f0f9ff; border: 1px solid #0066cc; border-radius: 8px; padding: 16px; margin: 10px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: #333;">Additional Security:</span>
                        <span style="font-weight: 700; font-size: 18px; color: #0066cc;">${selected_total:,.0f}</span>
                    </div>
                    <div style="font-size: 13px; color: #666; margin-top: 4px;">
                        Income covers costs - these assets provide reserves
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)

    # Track if any selection changed
    selection_changed = False

    # Render each asset as a clean, detailed card
    for cat_name in analysis.recommended_funding_order:
        if cat_name not in analysis.asset_categories:
            continue

        category = analysis.asset_categories[cat_name]
        
        # Icon mapping - clean text labels instead of emojis
        icon_map = {
            "Liquid Assets": "Liquid Assets",
            "Retirement Accounts": "Retirement Accounts", 
            "Home Equity": "Home Equity",
            "Investment Accounts": "Investment Accounts",
            "Life Insurance": "Life Insurance"
        }
        
        icon = icon_map.get(category.display_name, category.display_name)

        # Simple asset display - no containers or custom styling
        # Header with checkbox
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"**{icon}**")
        
        with col2:
            # Checkbox for selection
            current_selection = st.session_state.expert_review_selected_assets.get(cat_name, False)
            new_selection = st.checkbox(
                "Include",
                value=current_selection,
                key=f"asset_select_{cat_name}",
                disabled=not category.recommended,
                help="Include in Care Funding Plan"
            )

            if new_selection != current_selection:
                st.session_state.expert_review_selected_assets[cat_name] = new_selection
                selection_changed = True

        # Key details in clean layout
        detail_col1, detail_col2 = st.columns([1, 1])
        
        with detail_col1:
            st.markdown(f"**Current Balance:** ${category.current_balance:,.0f}")
            
            # Availability status
            timeframe_map = {
                "immediate": "Ready to Use",
                "1-3_months": "Available in 1-3 Months", 
                "3-6_months": "Available in 3-6 Months",
                "6-12_months": "Available in 6-12 Months",
            }
            timeframe_text = timeframe_map.get(category.liquidation_timeframe, category.liquidation_timeframe)
            st.markdown(f"**Availability:** {timeframe_text}")
            
        with detail_col2:
            # Available amount if different
            if category.accessible_value != category.current_balance:
                diff_pct = (category.accessible_value / category.current_balance) * 100
                st.markdown(f"**Available Now:** ${category.accessible_value:,.0f} ({diff_pct:.0f}% accessible)")
            else:
                st.markdown(f"**Available Now:** ${category.accessible_value:,.0f}")
                
            # Tax implications
            if category.tax_implications == "ordinary_income":
                st.caption("Withdrawals may incur income tax")
            elif category.tax_implications == "capital_gains":
                st.caption("Sale proceeds subject to capital gains tax")

        # Recommendation note
        if cat_name in analysis.funding_notes:
            note = analysis.funding_notes[cat_name]
            st.markdown(f"<div style='background: #f8f9fa; border-left: 3px solid #0066cc; padding: 8px 12px; border-radius: 4px; margin: 8px 0; font-size: 13px; color: #333;'>{note}</div>", unsafe_allow_html=True)

        # Additional notes
        if category.notes:
            st.caption(f"_{category.notes}_")
            
        # Add separator
        st.markdown("---")

    # Total summary
    total_available = sum(
        category.accessible_value 
        for category in analysis.asset_categories.values()
    )
    
    st.markdown(
        f"""
        <div style="background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-top: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 16px;">Total Available Resources</span>
                <span style="font-weight: 600; font-size: 18px; color: #0066cc;">${total_available:,.0f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Rerun if selection changed (to update calculations)
    if selection_changed:
        st.rerun()


def _render_coverage_impact_visualization(analysis, profile):
    """
    Render Coverage Impact - Simple summary showing selected asset impact.
    
    Clean, clear summary without confusing visualizations.
    """

    # Get current selections
    selected_assets = st.session_state.get("expert_review_selected_assets", {})
    
    # Calculate total selected value
    total_selected = sum(
        analysis.asset_categories[name].accessible_value
        for name, selected in selected_assets.items()
        if selected and name in analysis.asset_categories
    )
    
    # Only show if assets are selected
    if total_selected > 0:
        st.markdown("### Selected Assets Impact")
        
        # Show impact in clean card
        st.markdown(
            f"""
            <div style="background: #f0f9ff; border: 1px solid #0066cc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <span style="font-weight: 600; font-size: 16px;">Total Selected Assets</span>
                    <span style="font-weight: 600; font-size: 18px; color: #0066cc;">${total_selected:,.0f}</span>
                </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Show coverage impact based on monthly gap
        if analysis.monthly_gap > 0:
            months_covered = total_selected / analysis.monthly_gap
            years_covered = months_covered / 12
            
            if years_covered >= 1:
                coverage_text = f"Covers the ${analysis.monthly_gap:,.0f}/month gap for {years_covered:.1f} years"
            else:
                coverage_text = f"Covers the ${analysis.monthly_gap:,.0f}/month gap for {months_covered:.0f} months"
                
            st.markdown(
                f"""
                <div style="color: #0066cc; font-size: 14px; font-weight: 500;">
                    {coverage_text}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="color: #0066cc; font-size: 14px; font-weight: 500;">
                    These assets provide additional security since your income covers monthly costs
                </div>
                """,
                unsafe_allow_html=True,
            )
            
        st.markdown("</div>", unsafe_allow_html=True)


def _render_recommended_actions(analysis):
    """
    Render Recommended Actions & Helpful Resources section.
    
    Clear, numbered list of 3-5 key actions with supporting resources below.
    """

    st.markdown("### 🪄 Recommended Actions")

    # Primary recommendation in a highlighted box
    st.markdown('<div style="background: var(--surface-primary); border-left: 4px solid var(--primary-bg); padding: 16px; border-radius: 8px; margin-bottom: 20px;">', unsafe_allow_html=True)
    st.markdown(f"**{analysis.primary_recommendation}**")
    st.markdown('</div>', unsafe_allow_html=True)

    # Action items as numbered list
    if analysis.action_items:
        for i, action in enumerate(analysis.action_items, 1):
            st.markdown(f"**{i}.** {action}")

    # Resources section (if any)
    if analysis.resources:
        st.markdown('<div style="margin-top: 32px;"></div>', unsafe_allow_html=True)
        st.markdown("### 📚 Helpful Resources")

        # Display as clean bullet list
        for resource in analysis.resources:
            st.markdown(f"• {resource}")


def _render_navigation():
    """Render simple navigation buttons."""

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("← Back to Assessments", use_container_width=True):
            # Update URL query params for browser navigation
            st.query_params["page"] = "cost_v2"
            st.query_params["step"] = "assessments"
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            
            st.session_state.cost_v2_step = "assessments"
            st.rerun()

    with col3:
        if st.button("Exit Cost Planner →", use_container_width=True):
            # Update URL query params for browser navigation
            st.query_params["page"] = "cost_v2"
            st.query_params["step"] = "exit"
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            
            st.session_state.cost_v2_step = "exit"
            st.rerun()
