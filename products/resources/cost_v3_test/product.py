"""
Cost Planner v3 Test Tool - Internal Testing Interface

Allows testing the complete Cost Planner v3 calculation engine:
- Tier assignment logic (AL Tier 0-4, MC Tier 0-4)
- Add-on calculations with capping
- Confidence ranges (±7%, ±12%, ±20%)
- v2 vs v3 side-by-side comparison
- Tier overflow logic (AL→MC→MC-HA)

Part of Phase 1 validation before GCP integration.
"""

import streamlit as st
from typing import Dict, Any, Set

from products.cost_planner_v3.calculator import calculate_care_costs
from products.cost_planner_v3.tier_assignment import (
    assign_assisted_living_tier,
    assign_memory_care_tier,
    should_recommend_memory_care_instead_of_al,
    should_recommend_high_acuity_mc,
    prepare_gcp_context
)
from products.cost_planner_v3.explanations import (
    generate_cost_explanation,
    generate_quick_summary
)
from ui.header_simple import render_header_simple
from ui.footer_simple import render_footer_simple
from core.ui import render_navi_panel_v2


def render(ctx=None) -> None:
    """Render Cost Planner v3 Test Tool."""
    
    # Render header
    render_header_simple(active_route="testing_tools")
    
    # Warning banner
    st.markdown(
        """
        <div style="background: #e3f2fd; border: 1px solid #2196f3; border-radius: 8px; padding: 16px; margin: 24px 0;">
            <strong>🧪 Cost Planner v3 Test Tool</strong><br>
            Test the new tier-based cost calculation engine. Input GCP flags and answers manually 
            to validate tier assignments, add-on logic, and confidence ranges.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Navi panel
    render_navi_panel_v2(
        title="Cost Planner v3 Testing",
        reason="Validate tier-based cost calculations before GCP integration.",
        encouragement={
            "icon": "💰",
            "text": "Test all care types and tier combinations",
            "status": "info"
        },
        context_chips=[
            {"label": "Phase 1 Validation"},
            {"label": "Tier-Based Model", "variant": "muted"},
        ],
        primary_action={"label": "", "route": ""},
        variant="product"
    )
    
    # Initialize session state
    if "cv3_care_type" not in st.session_state:
        st.session_state.cv3_care_type = "assisted_living"
    if "cv3_regional_multiplier" not in st.session_state:
        st.session_state.cv3_regional_multiplier = 1.0
    if "cv3_flags" not in st.session_state:
        st.session_state.cv3_flags = set()
    if "cv3_answers" not in st.session_state:
        st.session_state.cv3_answers = {}
    
    # Main layout
    st.markdown("## 🎯 Test Configuration")
    
    # Care type and regional multiplier
    col1, col2 = st.columns(2)
    
    with col1:
        care_type = st.selectbox(
            "Care Type",
            options=[
                "assisted_living",
                "memory_care",
                "memory_care_high_acuity",
                "in_home_care",
                "homemaker_care",
                "home_with_carry"
            ],
            format_func=lambda x: {
                "assisted_living": "Assisted Living",
                "memory_care": "Memory Care",
                "memory_care_high_acuity": "Memory Care (High Acuity)",
                "in_home_care": "In-Home Care",
                "homemaker_care": "Homemaker Services",
                "home_with_carry": "In-Home with Family Support"
            }[x],
            key="cv3_care_type_select"
        )
        st.session_state.cv3_care_type = care_type
    
    with col2:
        regional_multiplier = st.slider(
            "Regional Multiplier",
            min_value=0.8,
            max_value=1.5,
            value=1.0,
            step=0.1,
            help="0.8 = Low-cost area, 1.0 = National average, 1.3 = High-cost area",
            key="cv3_regional_slider"
        )
        st.session_state.cv3_regional_multiplier = regional_multiplier
    
    # Flags input
    st.markdown("### 🏴 GCP Flags")
    st.caption("Select care flags that would come from GCP assessment")
    
    _render_flags_input()
    
    # Answers input
    st.markdown("### 📝 GCP Answers")
    st.caption("Enter key values that affect tier assignment and add-ons")
    
    _render_answers_input()
    
    # Calculate button
    st.markdown("---")
    if st.button("🔬 Calculate Costs", type="primary", use_container_width=True):
        _calculate_and_display_results()
    
    # Render footer
    render_footer_simple()


def _render_flags_input() -> None:
    """Render flag selection interface."""
    
    # Define flag categories
    flag_categories = {
        "Cognitive & Memory": [
            "mild_cognitive_decline",
            "moderate_cognitive_decline",
            "severe_cognitive_decline",
            "diagnosed_dementia",
            "dementia_complexity"
        ],
        "ADLs & Mobility": [
            "high_mobility_dependence",
            "transfer_assistance_1person",
            "transfer_assistance_2person",
            "transfer_lift_required",
            "incontinence_management",
            "high_dependence"
        ],
        "Behaviors & Safety": [
            "behavioral_concerns",
            "wandering_elopement",
            "safety_concerns",
            "continuous_supervision"
        ],
        "Falls & Health": [
            "falls_multiple",
            "medication_moderate",
            "medication_complex"
        ]
    }
    
    # Display in columns
    cols = st.columns(2)
    
    for idx, (category, flags) in enumerate(flag_categories.items()):
        with cols[idx % 2]:
            st.markdown(f"**{category}**")
            for flag in flags:
                if st.checkbox(
                    flag.replace("_", " ").title(),
                    value=flag in st.session_state.cv3_flags,
                    key=f"flag_{flag}"
                ):
                    st.session_state.cv3_flags.add(flag)
                else:
                    st.session_state.cv3_flags.discard(flag)


def _render_answers_input() -> None:
    """Render answers input interface."""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        badls_count = st.number_input(
            "BADLs Count",
            min_value=0,
            max_value=6,
            value=st.session_state.cv3_answers.get("badls_count", 0),
            help="Basic Activities of Daily Living (0-6)",
            key="cv3_badls"
        )
        st.session_state.cv3_answers["badls_count"] = badls_count
        
        iadls_count = st.number_input(
            "IADLs Count",
            min_value=0,
            max_value=8,
            value=st.session_state.cv3_answers.get("iadls_count", 0),
            help="Instrumental Activities of Daily Living (0-8)",
            key="cv3_iadls"
        )
        st.session_state.cv3_answers["iadls_count"] = iadls_count
    
    with col2:
        behaviors_count = st.number_input(
            "Behaviors Count",
            min_value=0,
            max_value=6,
            value=st.session_state.cv3_answers.get("behaviors_count", 0),
            help="Number of behavioral concerns",
            key="cv3_behaviors"
        )
        st.session_state.cv3_answers["behaviors_count"] = behaviors_count
        
        chronic_conditions = st.multiselect(
            "Chronic Conditions",
            options=[
                "diabetes",
                "heart_disease",
                "copd",
                "parkinsons",
                "stroke",
                "arthritis",
                "osteoporosis",
                "cancer",
                "kidney_disease"
            ],
            default=st.session_state.cv3_answers.get("chronic_conditions", []),
            format_func=lambda x: x.replace("_", " ").title(),
            key="cv3_chronic"
        )
        st.session_state.cv3_answers["chronic_conditions"] = chronic_conditions
    
    with col3:
        if st.session_state.cv3_care_type in ["in_home_care", "homemaker_care", "home_with_carry"]:
            hours_per_week = st.number_input(
                "Hours per Week",
                min_value=5,
                max_value=168,
                value=st.session_state.cv3_answers.get("recommended_hours_per_week", 20),
                help="Recommended care hours per week",
                key="cv3_hours"
            )
            st.session_state.cv3_answers["recommended_hours_per_week"] = hours_per_week
        
        recommendation = st.selectbox(
            "GCP Recommendation",
            options=["assisted_living", "memory_care", "memory_care_high_acuity", "in_home_care"],
            format_func=lambda x: x.replace("_", " ").title(),
            index=["assisted_living", "memory_care", "memory_care_high_acuity", "in_home_care"].index(
                st.session_state.cv3_answers.get("recommendation", "assisted_living")
            ),
            key="cv3_recommendation"
        )
        st.session_state.cv3_answers["recommendation"] = recommendation


def _calculate_and_display_results() -> None:
    """Calculate costs and display results."""
    
    st.markdown("---")
    st.markdown("## 📊 Calculation Results")
    
    # Prepare GCP outcome
    gcp_outcome = {
        "flags": list(st.session_state.cv3_flags),
        "answers": st.session_state.cv3_answers,
        "recommendation": st.session_state.cv3_answers.get("recommendation", st.session_state.cv3_care_type)
    }
    
    # Calculate v3 costs
    try:
        v3_result = calculate_care_costs(
            gcp_outcome,
            regional_multiplier=st.session_state.cv3_regional_multiplier,
            care_type=st.session_state.cv3_care_type
        )
        
        # Display tier assignment (if applicable)
        if v3_result.get("tier_id") not in ["hourly", "hourly_with_carry", "high_acuity"]:
            _display_tier_assignment(v3_result, gcp_outcome)
        
        # Display v3 results
        _display_v3_results(v3_result)
        
        # Display v2 comparison note
        if st.session_state.cv3_care_type in ["assisted_living", "memory_care", "memory_care_high_acuity"]:
            st.markdown("---")
            st.info("💡 **v2 Comparison**: Run full GCP assessment to compare v2 vs v3 side-by-side")
        
        # Display full explanation
        with st.expander("📄 Full Cost Explanation", expanded=False):
            explanation = generate_cost_explanation(v3_result, include_sources=True, audience="advisor")
            st.markdown(explanation)
    
    except Exception as e:
        st.error(f"❌ Calculation failed: {str(e)}")
        st.exception(e)


def _display_tier_assignment(v3_result: Dict[str, Any], gcp_outcome: Dict[str, Any]) -> None:
    """Display tier assignment logic."""
    
    st.markdown("### 🎯 Tier Assignment")
    
    gcp_context = prepare_gcp_context(gcp_outcome)
    gcp_flags = gcp_context["flags"]
    gcp_answers = gcp_context["answers"]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        tier_id = v3_result["tier_id"]
        tier_label = v3_result["tier"]
        tier_desc = v3_result["tier_description"]
        tier_increment = v3_result["tier_increment"]
        
        st.markdown(
            f"""
            <div style="background: #f0f7ff; border-left: 4px solid #2196f3; padding: 16px; border-radius: 4px;">
                <h4 style="margin: 0; color: #1976d2;">{tier_label}</h4>
                <p style="margin: 8px 0; color: #555;">{tier_desc}</p>
                <p style="margin: 0; font-size: 20px; font-weight: bold; color: #1976d2;">
                    +${tier_increment:,.0f}/month
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        # Check tier overflow
        if st.session_state.cv3_care_type == "assisted_living":
            if should_recommend_memory_care_instead_of_al(gcp_flags, gcp_answers):
                st.warning("⚠️ **Tier Overflow**: Should recommend Memory Care instead")
        elif st.session_state.cv3_care_type == "memory_care":
            if should_recommend_high_acuity_mc(gcp_flags, gcp_answers):
                st.warning("⚠️ **High-Acuity**: Should escalate to MC-HA")


def _display_v3_results(v3_result: Dict[str, Any]) -> None:
    """Display v3 calculation results."""
    
    st.markdown("### 💰 Cost Planner v3 Results")
    
    # Main metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Low Estimate",
            f"${v3_result['low_estimate']:,.0f}",
            help="Lower bound of cost range"
        )
    
    with col2:
        st.metric(
            "Most Likely",
            f"${v3_result['likely_estimate']:,.0f}",
            help="Expected monthly cost"
        )
    
    with col3:
        st.metric(
            "High Estimate",
            f"${v3_result['high_estimate']:,.0f}",
            help="Upper bound of cost range"
        )
    
    # Confidence and range
    col1, col2 = st.columns(2)
    
    with col1:
        confidence = v3_result["confidence"].capitalize()
        range_pct = v3_result["range_pct"] * 100
        confidence_colors = {
            "High": "#4caf50",
            "Medium": "#ff9800",
            "Low": "#f44336"
        }
        color = confidence_colors.get(confidence, "#757575")
        
        st.markdown(
            f"""
            <div style="background: {color}15; border: 1px solid {color}; border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 14px; color: #666;">Confidence Level</div>
                <div style="font-size: 24px; font-weight: bold; color: {color}; margin: 4px 0;">
                    {confidence}
                </div>
                <div style="font-size: 14px; color: #666;">±{range_pct:.0f}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown("**Range Explanation:**")
        st.caption(v3_result["range_explanation"])
        
        if v3_result.get("widening_factors"):
            st.markdown("**Widening Factors:**")
            for factor in v3_result["widening_factors"]:
                st.caption(f"• {factor}")
    
    # Breakdown
    st.markdown("### 📋 Cost Breakdown")
    
    breakdown_df = []
    for item in v3_result["breakdown"]:
        breakdown_df.append({
            "Component": item["label"],
            "Amount": f"${item['amount']:,.2f}"
        })
    
    st.table(breakdown_df)
    
    # Add-ons
    if v3_result.get("addons"):
        st.markdown("### ➕ Additional Services")
        st.caption(f"*Capped at ${v3_result['addon_cap']:,.0f} or 15% of regional base*")
        
        for addon in v3_result["addons"]:
            with st.expander(f"{addon['label']} (+${addon['amount']:,.2f})"):
                st.write(addon["description"])
