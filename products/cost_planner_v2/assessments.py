"""
Financial Assessment Hub for Cost Planner v2

JSON-driven assessment hub that loads and displays financial assessments
as a card grid, similar to Senior Trivia module hub pattern.

Pattern: Follows products/senior_trivia/product.py architecture
Configuration: Loads assessments from JSON files
State Management: Tracks completion status and progress
"""

import json
import time
from pathlib import Path
from typing import Any

import streamlit as st

from core.assessment_engine import run_assessment
from core.events import log_event
from core.session_store import safe_rerun
from products.cost_planner_v2.utils.financial_helpers import (
    calculate_total_asset_debt,
    calculate_total_asset_value,
    calculate_total_monthly_income,
    normalize_asset_data,
    normalize_income_data,
)
from products.cost_planner_v2.utils.home_equity_helpers import normalize_home_equity_data
from products.cost_planner_v2.utils.va_rates import get_monthly_va_disability

# Assessments that use the single-page progressive disclosure layout
_SINGLE_PAGE_ASSESSMENTS: set[str] = {
    "income",
    "assets",
    "va_benefits",
    "health_insurance",
    "life_insurance",
    "home_equity",
}


def render_assessment_hub(product_key: str = "cost_planner_v2") -> None:
    """
    Render the assessment selection hub.

    Displays available financial assessments as a card grid with:
    - Assessment title and description
    - Estimated completion time
    - Progress indicator
    - Conditional visibility based on flags

    Args:
        product_key: Product key for state management
    """

    # Check if a specific assessment is selected (either from query params or session state)
    assessment_from_query = st.query_params.get("assessment")
    current_assessment = st.session_state.get(f"{product_key}_current_assessment")
    
    # URL query param takes precedence
    if assessment_from_query and assessment_from_query != current_assessment:
        st.session_state[f"{product_key}_current_assessment"] = assessment_from_query
        current_assessment = assessment_from_query
        # Force rerun to render the assessment
        st.rerun()

    if current_assessment:
        # Run the selected assessment
        _render_assessment(current_assessment, product_key)
    else:
        # Show assessment hub
        _render_hub_view(product_key)


def _render_hub_view(product_key: str) -> None:
    """Render the hub view with assessment cards."""

    # Bring back Navi panel
    from core.navi_module import render_module_navi_coach
    render_module_navi_coach(
        title_text="Let's work through these financial assessments together",
        body_text="Completing them will help us figure out how to pay for the care that was recommended.",
        tip_text="Each assessment takes just a few minutes and helps build your complete financial picture.",
    )

    # Load all assessment configs
    assessments = _load_all_assessments(product_key)

    if not assessments:
        st.error("⚠️ No assessments found. Please check configuration.")
        return

    # Clean header with progress bar
    st.markdown(
        """
        <div style='max-width: 900px; margin: 0 auto 40px auto;'>
            <h1 style='font-size: 32px; font-weight: 700; color: #0f172a; margin: 0 0 8px 0;'>
                FINANCIAL ASSESSMENTS
            </h1>
            <p style='font-size: 15px; color: #64748b; margin: 0 0 24px 0;'>
                Complete these assessments to build your financial profile for care planning.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Calculate overall progress
    total_assessments = len(assessments)
    completed_assessments = sum(
        1 for a in assessments if _is_assessment_complete(a["key"], product_key)
    )
    overall_progress = (
        int((completed_assessments / total_assessments) * 100) if total_assessments > 0 else 0
    )

    # Progress bar (similar to design)
    if total_assessments > 0:
        st.markdown(
            f"""
            <div style='max-width: 900px; margin: 0 auto 40px auto;'>
                <div style='display: flex; gap: 4px; height: 4px; background: #e5e7eb; border-radius: 4px; overflow: hidden;'>
                    {"".join([
                        f"<div style='flex: 1; background: #2563eb;'></div>" if i < completed_assessments 
                        else f"<div style='flex: 1; background: #e5e7eb;'></div>"
                        for i in range(total_assessments)
                    ])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Simple progress indicator (no bar, just text)
    if completed_assessments > 0:
        st.markdown(
            f"<div style='font-size:13px; color:#6b7280; margin-bottom:20px;'>"
            f"{completed_assessments} of {total_assessments} completed"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # Render assessment cards in grid
    _render_assessment_grid(assessments, product_key)


def _render_assessment_grid(assessments: list[dict[str, Any]], product_key: str) -> None:
    """Render assessment cards in a responsive grid."""

    # Get user flags for conditional visibility
    flags = st.session_state.get("flags", {})

    # Filter assessments based on visibility rules
    visible_assessments = []
    for assessment in assessments:
        if _is_assessment_visible(assessment, flags):
            visible_assessments.append(assessment)

    if not visible_assessments:
        st.info("No assessments available based on your profile.")
        return

    # Render in 2-column grid (max width like in design)
    st.markdown("<div style='max-width: 900px; margin: 0 auto;'>", unsafe_allow_html=True)
    num_cols = 2
    cols = st.columns(num_cols, gap="medium")

    for idx, assessment in enumerate(visible_assessments):
        col_index = idx % num_cols

        with cols[col_index]:
            _render_assessment_card(assessment, product_key)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Bottom navigation buttons
    st.markdown("<div style='margin: 48px 0 24px 0;'></div>", unsafe_allow_html=True)
    
    # Check if required assessments are complete
    required_assessments = [a for a in visible_assessments if a.get("required", False)]
    required_complete = all(
        _is_assessment_complete(a["key"], product_key) 
        for a in required_assessments
    )
    
    # Two buttons: Back to Quick Assessment and Expert Review
    col1, col2 = st.columns(2, gap="medium")
    
    with col1:
        if st.button(
            "← Back to Quick Assessment",
            use_container_width=True,
            type="secondary",
            key="back_to_quick_assessment",
        ):
            # Go back to GCP (care recommendation)
            st.query_params["page"] = "gcp"
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            if "step" in st.query_params:
                del st.query_params["step"]
            st.session_state.pop(f"{product_key}_current_assessment", None)
            st.rerun()
    
    with col2:
        if required_complete:
            if st.button(
                "Go to Expert Review →",
                type="primary",
                use_container_width=True,
                key="goto_expert_review",
            ):
                # Navigate to expert review
                st.query_params["page"] = "cost_v2"
                st.query_params["step"] = "expert_review"
                if "assessment" in st.query_params:
                    del st.query_params["assessment"]
                st.session_state.cost_v2_step = "expert_review"
                st.rerun()
        else:
            st.button(
                "Go to Expert Review →",
                type="primary",
                use_container_width=True,
                disabled=True,
                key="goto_expert_review_disabled",
            )
            st.markdown(
                "<div style='text-align: center; font-size: 12px; color: #9ca3af; margin-top: 4px;'>Complete required assessments first</div>",
                unsafe_allow_html=True
            )


def _render_assessment_card(assessment: dict[str, Any], product_key: str) -> None:
    """Render assessment card using pure HTML (like product tiles)."""
    
    from html import escape as html_escape
    from core.text import personalize_text

    key = assessment.get("key", "unknown")
    title = assessment.get("title", "Assessment")
    icon = assessment.get("icon", "📊")
    description = assessment.get("description", "")
    required = assessment.get("required", False)
    
    # Personalize description with user name
    description = personalize_text(description)

    # Get completion status
    is_complete = _is_assessment_complete(key, product_key)
    progress_pct = _get_assessment_progress(key, product_key)
    
    # Get summary value if assessment is complete
    summary_text = ""
    if is_complete:
        # Try tiles first (primary source), then cost_v2_modules (secondary)
        tiles = st.session_state.get("tiles", {})
        product_tiles = tiles.get(product_key, {})
        assessments_state = product_tiles.get("assessments", {})
        data = assessments_state.get(key, {})
        
        # Fall back to cost_v2_modules if not in tiles
        if not data:
            modules = st.session_state.get("cost_v2_modules", {})
            if key in modules:
                data = modules[key].get("data", {})
        
        # Extract summary based on assessment type
        if data:
            if key == "income":
                total = data.get("total_monthly_income", 0)
                if total > 0:
                    summary_text = f"${total:,.0f}/month"
            elif key == "assets":
                net_assets = data.get("net_asset_value", 0)
                if net_assets != 0:
                    summary_text = f"${net_assets:,.0f}"
            elif key == "va_benefits":
                va_disability = data.get("va_disability_monthly", 0)
                aid_attendance = data.get("aid_attendance_monthly", 0)
                total_va = va_disability + aid_attendance
                if total_va > 0:
                    summary_text = f"${total_va:,.0f}/month"
            elif key == "life_insurance":
                cash_value = data.get("life_insurance_cash_value", 0)
                if cash_value > 0:
                    summary_text = f"${cash_value:,.0f} cash value"
            elif key == "health_insurance":
                # Could show type of coverage or premium
                coverage_type = data.get("health_coverage_type", "")
                if coverage_type:
                    summary_text = coverage_type.replace("_", " ").title()
            elif key == "home_equity":
                owns_home = data.get("owns_home", "other")
                home_equity = data.get("home_equity", 0)
                strategies = data.get("strategies", {})
                num_strategies = len(strategies)
                
                if owns_home == "own":
                    if home_equity > 0:
                        summary_text = f"${home_equity:,.0f} equity"
                    else:
                        summary_text = "Homeowner"
                    if num_strategies > 0:
                        summary_text += f" • {num_strategies} strategies"
                elif owns_home == "rent":
                    monthly_carry = data.get("monthly_carry", 0)
                    if monthly_carry > 0:
                        summary_text = f"${monthly_carry:,.0f}/mo rent"
                    else:
                        summary_text = "Renter"

    # Status text and button label
    if is_complete:
        status_text = "Completed ✓"
        status_color = "#22c55e"
        button_label = "View"
    elif progress_pct > 0:
        status_text = f"{progress_pct}% complete"
        status_color = "#2563eb"
        button_label = "Continue"
    else:
        status_text = ""
        status_color = "#94a3b8"
        button_label = "Start"

    # Card styling
    bg_color = '#f8f9fb' if required else 'white'
    border_color = '#d1d5db' if required else '#e5e7eb'
    
    # Build href with uid preservation (like product tiles)
    def _add_uid_to_href(href: str) -> str:
        """Add current UID to href to preserve session across navigation."""
        if not href or href == "#":
            return href
        
        # Get current UID from session_state
        uid = None
        if "auth" in st.session_state and st.session_state["auth"].get("user_id"):
            uid = st.session_state["auth"]["user_id"]
        elif "anonymous_uid" in st.session_state:
            uid = st.session_state["anonymous_uid"]
        
        if not uid:
            return href
        
        # Add uid to query string
        separator = "&" if "?" in href else "?"
        return f"{href}{separator}uid={uid}"
    
    base_href = f"?page=cost_v2&step=assessments&assessment={key}"
    href = _add_uid_to_href(base_href)
    
    # Build card matching ProductTileHub design from core/product_tile.py
    card_html = []
    
    # Determine tile state class
    if is_complete:
        state_class = "done"
    elif progress_pct > 0:
        state_class = "doing"
    else:
        state_class = "new"
    
    # Build classes matching product tiles
    classes = ["ptile", "dashboard-card", f"tile--{state_class}"]
    if required:
        classes.append("tile--required")
    
    card_html.append(
        f'<div class="{" ".join(classes)}" style="background: {bg_color}; border: 1px solid {border_color}; '
        f'border-radius: 12px; padding: 24px; margin-bottom: 20px;">'
    )
    
    # Header section (matching ptile__head)
    card_html.append('<div class="ptile__head">')
    card_html.append('<div class="ptile__heading">')
    
    # Title row with status
    card_html.append('<div class="ptile__title-row">')
    title_html = html_escape(title)
    if required:
        title_html += '<span style="color: #dc2626; margin-left: 4px;">*</span>'
    card_html.append(f'<h3 class="tile-title">{title_html}</h3>')
    
    # Status badge (matching dashboard-status)
    if status_text:
        card_html.append(f'<div class="dashboard-status">{html_escape(status_text)}</div>')
    
    card_html.append('</div>')  # /title-row
    card_html.append('</div>')  # /heading
    card_html.append('</div>')  # /head
    
    # Description (matching tile-subtitle)
    card_html.append(f'<p class="tile-subtitle">{html_escape(description)}</p>')
    
    # Summary value display (if completed)
    if summary_text:
        card_html.append(
            f'<div class="tile-meta"><span style="font-size: 18px; font-weight: 700; color: #0f172a;">{html_escape(summary_text)}</span></div>'
        )
    
    # Actions (matching tile-actions)
    card_html.append('<div class="tile-actions">')
    card_html.append(
        f'<a class="dashboard-cta dashboard-cta--primary" href="{html_escape(href)}" target="_self">'
        f'{html_escape(button_label)}</a>'
    )
    card_html.append('</div>')
    
    card_html.append('</div>')  # /card
    
    # Render as pure HTML
    st.markdown("".join(card_html), unsafe_allow_html=True)
    
    # Log event
    try:
        log_event(
            "assessment.card_rendered",
            {"product": product_key, "assessment": key, "is_complete": is_complete},
        )
    except Exception:
        pass


def _render_assessment(assessment_key: str, product_key: str) -> None:
    """Render a specific assessment using the assessment engine."""

    # Load assessment config
    assessment_config = _load_assessment_config(assessment_key, product_key)

    if not assessment_config:
        st.error(f"⚠️ Assessment '{assessment_key}' not found.")
        if st.button("← Back to Lobby"):
            st.session_state[f"{product_key}_current_assessment"] = None
            st.rerun()
        return

    # Use new progressive disclosure layout for all designated assessments
    if assessment_key in _SINGLE_PAGE_ASSESSMENTS:
        render_assessment_page(assessment_key=assessment_key, product_key=product_key)
        return

    # Run assessment engine (original multi-step flow) for any other assessments
    run_assessment(
        assessment_key=assessment_key, assessment_config=assessment_config, product_key=product_key
    )


def _render_progressive_sections(
    sections: list[dict[str, Any]],
    state: dict[str, Any],
    assessment_key: str,
    product_key: str,
) -> None:
    """
    Render all sections with collapsible functionality.
    Sections can be collapsed to show just title + subtotal.
    """
    
    for idx, section in enumerate(sections):
        section_title = section.get("title", "")
        section_id = section.get("id", "")
        fields = section.get("fields", [])
        
        if not fields:
            continue
        
        # Calculate section subtotal first (needed for collapsed state)
        subtotal = 0.0
        has_currency_fields = False
        
        # Check if this is a debt section (debts should be negative)
        is_debt_section = "debt" in section_id.lower() or "obligation" in section_id.lower()
        
        for field in fields:
            if field.get("type") == "currency":
                has_currency_fields = True
                field_key = field.get("key")
                field_value = state.get(field_key, 0)
                if isinstance(field_value, (int, float)):
                    # Debts should be subtracted (shown as negative)
                    if is_debt_section:
                        subtotal -= field_value
                    else:
                        subtotal += field_value
        
        # Track collapse state per section
        collapse_key = f"{product_key}_{assessment_key}_{section_id}_collapsed"
        is_collapsed = st.session_state.get(collapse_key, False)
        
        # Render section header with collapse toggle
        if section_title:
            # Check if section has help text
            help_text = section.get("help_text", "")
            
            # If collapsed, show title + subtotal + edit button on same line
            if is_collapsed and subtotal != 0:
                # Build header with title and subtotal on same line
                st.markdown(
                    f"""
                    <div style='margin: 24px 0 0 0; padding: 12px 0; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center;'>
                        <h3 style='margin: 0; font-size: 18px; font-weight: 600; color: #111827;'>{section_title}</h3>
                        <div style='display: flex; align-items: center; gap: 12px;'>
                            <span style='font-size: 16px; font-weight: 600; color: #111827;'>Subtotal: ${subtotal:,.0f}/month</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Edit button on next line, but right-aligned to match subtotal
                st.markdown(
                    "<div style='margin: 8px 0; display: flex; justify-content: flex-start;'>",
                    unsafe_allow_html=True,
                )
                
                # Add CSS to style Edit button as blue link - target by button text content
                st.markdown(
                    """
                    <style>
                    /* Target Edit buttons by their content */
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) {
                        background: none !important;
                        background-color: transparent !important;
                        border: none !important;
                        padding: 0 !important;
                        color: #2563eb !important;
                        font-size: 14px !important;
                        font-weight: 500 !important;
                        cursor: pointer !important;
                        box-shadow: none !important;
                        text-decoration: none !important;
                        outline: none !important;
                        min-height: auto !important;
                        width: auto !important;
                    }
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):hover {
                        text-decoration: underline !important;
                        background: none !important;
                        background-color: transparent !important;
                        border: none !important;
                    }
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):focus,
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):active {
                        outline: none !important;
                        border: none !important;
                        box-shadow: none !important;
                        background: none !important;
                        background-color: transparent !important;
                    }
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) div {
                        background: none !important;
                        border: none !important;
                    }
                    button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) p {
                        color: #2563eb !important;
                        margin: 0 !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                
                if st.button(
                    "✏️ Edit",
                    key=f"{collapse_key}_expand",
                    type="secondary",
                    use_container_width=False,
                ):
                    st.session_state[collapse_key] = False
                    st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                # If help text exists, show help button too
                if help_text:
                    if st.button(
                        "?",
                        key=f"{collapse_key}_help_collapsed",
                        help="What should I include here?",
                        type="secondary",
                    ):
                        st.session_state["navi_dialogue"] = help_text
                        st.rerun()
            else:
                # Expanded state - show title with inline help icon
                if help_text:
                    title_col1, title_col2 = st.columns([20, 0.5])
                    with title_col1:
                        st.markdown(
                            f"""<div style='margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;'>
                            <h3 style='margin: 0; font-size: 18px; font-weight: 600; color: #111827;'>{section_title}</h3>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with title_col2:
                        if st.button(
                            "?",
                            key=f"{section_id}_help_btn",
                            help="What should I include here?",
                            use_container_width=True,
                        ):
                            st.session_state["navi_dialogue"] = help_text
                            st.rerun()
                else:
                    st.markdown(
                        f"""<div style='margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;'>
                        <h3 style='margin: 0; font-size: 18px; font-weight: 600; color: #111827;'>{section_title}</h3>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        
        # Render fields if not collapsed
        if not is_collapsed:
            _render_section_content(section, state, product_key, assessment_key)
            
            # Check if section has any visible currency fields
            # (Check visibility conditions to see if fields are actually rendered)
            has_visible_currency = False
            for field in fields:
                if field.get("type") == "currency":
                    # Check if field is visible
                    visible_if = field.get("visible_if")
                    if visible_if:
                        condition_field = visible_if.get("field")
                        condition_value = visible_if.get("equals")
                        actual_value = state.get(condition_field)
                        if actual_value == condition_value:
                            has_visible_currency = True
                            break
                    else:
                        # No visibility condition, field is always visible
                        has_visible_currency = True
                        break
            
            # Show subtotal + "Collapse this section" link if has visible currency fields
            if has_visible_currency:
                # Show subtotal if != 0 (can be positive assets or negative debts)
                if subtotal != 0:
                    st.markdown(
                        f"""
                        <div style='
                            margin: 12px 0 8px 0;
                            padding: 8px 0;
                            border-top: 1px solid #e5e7eb;
                            text-align: right;
                        '>
                            <span style='font-size: 14px; color: #6b7280; margin-right: 8px;'>Subtotal:</span>
                            <span style='font-size: 16px; font-weight: 600; color: #111827;'>${subtotal:,.0f}/month</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                
                # Show collapse link for ALL sections with titles and visible currency fields
                if section_title:
                    # Create a simple text-styled button with CSS override
                    collapse_key_id = f"{collapse_key}_collapse"
                    
                    # Add CSS to style Collapse button as blue link - target all secondary buttons in section
                    st.markdown(
                        """
                        <style>
                        /* Target Collapse buttons by their content */
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) {
                            background: none !important;
                            background-color: transparent !important;
                            border: none !important;
                            padding: 0 !important;
                            color: #2563eb !important;
                            font-size: 14px !important;
                            font-weight: 500 !important;
                            cursor: pointer !important;
                            box-shadow: none !important;
                            text-decoration: none !important;
                            outline: none !important;
                            min-height: auto !important;
                            width: auto !important;
                        }
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):hover {
                            text-decoration: underline !important;
                            background: none !important;
                            background-color: transparent !important;
                            border: none !important;
                        }
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):focus,
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child):active {
                            outline: none !important;
                            border: none !important;
                            box-shadow: none !important;
                            background: none !important;
                            background-color: transparent !important;
                        }
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) div {
                            background: none !important;
                            border: none !important;
                        }
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child) p {
                            color: #2563eb !important;
                            margin: 0 !important;
                        }
                        /* Remove pseudo-elements */
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child)::after,
                        button[kind="secondary"][data-testid="stBaseButton-secondary"]:has(p:first-child)::before {
                            display: none !important;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True,
                    )
                    
                    if st.button(
                        "✓ All Done — Collapse this section",
                        key=collapse_key_id,
                        type="secondary",
                        use_container_width=False,
                    ):
                        st.session_state[collapse_key] = True
                        st.rerun()


def _render_single_page_sections(
    sections: list[dict[str, Any]],
    state: dict[str, Any],
    assessment_key: str,
    product_key: str,
) -> None:
    """
    Render all field sections in a single vertical stack with visual state indicators.
    
    Each section shows:
    - ✓ Complete (green checkmark, fields visible but satisfied)
    - ⏸️ In Progress (highlighted, active fields)
    - ⭕ Not Started (dimmed, minimal display)
    
    Args:
        sections: List of section configs from assessment JSON
        state: Current assessment state
        assessment_key: Assessment key for state management
        product_key: Product key for state management
    """
    
    # Add CSS for section states
    st.markdown(
        """
        <style>
        .assessment-section {
            margin-bottom: 24px;
            padding: 20px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        
        .section-complete {
            background: #f0fdf4;
            border: 2px solid #86efac;
        }
        
        .section-active {
            background: #fefce8;
            border: 2px solid #fbbf24;
            box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.1);
        }
        
        .section-pending {
            background: #f8fafc;
            border: 2px dashed #cbd5e1;
            opacity: 0.7;
        }
        
        .section-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }
        
        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #1e293b;
            margin: 0;
        }
        
        .section-status {
            font-size: 14px;
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 500;
        }
        
        .status-complete {
            background: #86efac;
            color: #166534;
        }
        
        .status-active {
            background: #fbbf24;
            color: #92400e;
        }
        
        .status-pending {
            background: #e2e8f0;
            color: #64748b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # Determine section states based on field completion
    for idx, section in enumerate(sections):
        section_id = section.get("id", f"section_{idx}")
        section_title = section.get("title", f"Section {idx + 1}")
        section_icon = section.get("icon", "📝")
        
        # Calculate section state
        fields = section.get("fields", [])
        required_fields = [f for f in fields if f.get("required", False)]
        
        if not fields:
            # No fields = always complete
            section_state = "complete"
            status_label = "✓ Complete"
            status_class = "status-complete"
        else:
            # Check if section has any data
            section_keys = [f["key"] for f in fields]
            has_data = any(state.get(key) for key in section_keys)
            
            if has_data:
                # Check if all required fields are filled
                all_required_filled = all(state.get(f["key"]) for f in required_fields)
                if all_required_filled or not required_fields:
                    section_state = "complete"
                    status_label = "✓ Complete"
                    status_class = "status-complete"
                else:
                    section_state = "active"
                    filled = sum(1 for f in required_fields if state.get(f["key"]))
                    status_label = f"⏸️ In Progress ({filled} of {len(required_fields)})"
                    status_class = "status-active"
            else:
                section_state = "pending"
                status_label = "⭕ Not Started"
                status_class = "status-pending"
        
        # Render section container
        st.markdown(
            f"""
            <div class="assessment-section section-{section_state}">
                <div class="section-header">
                    <span style="font-size: 24px;">{section_icon}</span>
                    <h3 class="section-title">{section_title}</h3>
                    <span class="section-status {status_class}">{status_label}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Render section content
        _render_section_content(section, state, product_key, assessment_key)
        
        # Close the section div
        st.markdown("</div>", unsafe_allow_html=True)


def _render_home_equity_results(state: dict[str, Any]) -> None:
    """Render comparison table for home equity strategies."""
    
    # Only render if user owns a home and opted into analysis
    owns_home = state.get("owns_home")
    analyze_strategies = state.get("analyze_strategies")
    
    if owns_home != "own" or analyze_strategies != "yes":
        return
    
    # Get strategies from augmented state
    strategies = state.get("strategies", {})
    
    if not strategies:
        return
    
    # Render results header
    st.markdown(
        """
        <div style='margin: 40px 0 24px 0; padding-top: 24px; border-top: 2px solid #e5e7eb;'>
            <h2 style='font-size: 24px; font-weight: 700; color: #111827; margin: 0 0 8px 0;'>
                Strategy Comparison
            </h2>
            <p style='font-size: 14px; color: #64748b; margin: 0 0 24px 0;'>
                Here's how each selected strategy compares for funding care
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Render each strategy as a card
    for strategy_key, result in strategies.items():
        strategy_name = result.get("strategy", strategy_key.title())
        net_proceeds = result.get("net_proceeds", 0)
        monthly_cash_flow = result.get("monthly_cash_flow", 0)
        months_funded = result.get("months_of_care_funded", 0)
        considerations = result.get("considerations", [])
        
        # Determine card color based on strategy
        if strategy_key == "keep":
            accent_color = "#6b7280"  # Gray
        elif strategy_key == "rent":
            accent_color = "#2563eb"  # Blue
        elif strategy_key == "sell":
            accent_color = "#10b981"  # Green
        elif strategy_key == "reverse_mortgage":
            accent_color = "#8b5cf6"  # Purple
        else:
            accent_color = "#64748b"  # Default gray
        
        # Build metrics row
        metrics_html = []
        
        if net_proceeds > 0:
            metrics_html.append(
                f"""
                <div style='flex: 1; min-width: 150px;'>
                    <div style='font-size: 12px; font-weight: 500; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>
                        NET PROCEEDS
                    </div>
                    <div style='font-size: 24px; font-weight: 700; color: #111827;'>
                        ${net_proceeds:,.0f}
                    </div>
                </div>
                """
            )
        
        if monthly_cash_flow != 0:
            flow_label = "MONTHLY CASH FLOW" if monthly_cash_flow > 0 else "MONTHLY COST"
            flow_value = abs(monthly_cash_flow)
            metrics_html.append(
                f"""
                <div style='flex: 1; min-width: 150px;'>
                    <div style='font-size: 12px; font-weight: 500; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>
                        {flow_label}
                    </div>
                    <div style='font-size: 24px; font-weight: 700; color: #111827;'>
                        ${flow_value:,.0f}
                    </div>
                </div>
                """
            )
        
        if months_funded > 0:
            years = months_funded / 12
            time_label = f"{months_funded:.0f} months" if months_funded < 24 else f"{years:.1f} years"
            metrics_html.append(
                f"""
                <div style='flex: 1; min-width: 150px;'>
                    <div style='font-size: 12px; font-weight: 500; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>
                        CARE FUNDED
                    </div>
                    <div style='font-size: 24px; font-weight: 700; color: #111827;'>
                        {time_label}
                    </div>
                </div>
                """
            )
        
        metrics_row = "".join(metrics_html) if metrics_html else "<div style='font-size: 14px; color: #64748b;'>No funding generated</div>"
        
        # Build considerations list
        considerations_html = "".join(
            [f"<li style='margin-bottom: 8px;'>{item}</li>" for item in considerations]
        )
        
        # Render strategy card
        st.markdown(
            f"""
            <div style='
                margin-bottom: 24px;
                padding: 24px;
                background: white;
                border: 1px solid #e5e7eb;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            '>
                <h3 style='font-size: 20px; font-weight: 600; color: #111827; margin: 0 0 16px 0;'>
                    {strategy_name}
                </h3>
                
                <div style='display: flex; flex-wrap: wrap; gap: 32px; margin-bottom: 24px;'>
                    {metrics_row}
                </div>
                
                <div style='padding-top: 16px; border-top: 1px solid #e5e7eb;'>
                    <div style='font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;'>
                        Key Considerations
                    </div>
                    <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #374151; line-height: 1.6;'>
                        {considerations_html}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_assessment_page(assessment_key: str, product_key: str = "cost_planner_v2") -> None:
    """
    Render a full assessment page with all sections visible at once.

    This replaces the hub-based multi-step pattern with a single scrollable page
    showing intro, all field sections, and calculated results together.

    Args:
        assessment_key: Assessment to render (e.g., 'income', 'assets')
        product_key: Product key for state management
    """

    # Load assessment config
    assessment_config = _load_assessment_config(assessment_key, product_key)

    if not assessment_config:
        st.error(f"⚠️ Assessment '{assessment_key}' not found.")
        return

    # Initialize state - load from persistent storage if available
    state_key = f"{product_key}_{assessment_key}"

    # Only initialize if not already in session_state (preserve active editing session)
    if state_key not in st.session_state:
        # Try loading from tiles first (primary source of truth)
        # CRITICAL: Use setdefault to get the ACTUAL reference, not a copy
        tiles = st.session_state.setdefault("tiles", {})
        product_tiles = tiles.setdefault(product_key, {})
        assessments_state = product_tiles.setdefault("assessments", {})
        saved_data = assessments_state.get(assessment_key)

        # Fall back to cost_v2_modules if not in tiles (legacy/demo users)
        if not saved_data:
            modules = st.session_state.get("cost_v2_modules", {})
            if assessment_key in modules:
                saved_data = modules[assessment_key].get("data", {})

        # Initialize with saved data if found, otherwise empty dict
        if saved_data:
            st.session_state[state_key] = saved_data.copy()
        else:
            st.session_state[state_key] = {}

    state = st.session_state[state_key]

    # Render Navi guidance at top - clean panel like the hub
    from core.navi_module import render_module_navi_coach
    
    # Get assessment title for personalized message
    assessment_title = assessment_config.get("title", "Assessment")
    
    render_module_navi_coach(
        title_text=f"Let's complete your {assessment_title}",
        body_text="Fill in the information below. All fields are optional - skip any that don't apply.",
        tip_text="Use the navigation buttons at the bottom to save your progress and move to the next assessment.",
    )

    # Get sections
    sections = assessment_config.get("sections", [])

    # Separate sections by type
    intro_sections = [s for s in sections if s.get("type") == "intro"]
    results_sections = [s for s in sections if s.get("type") == "results"]
    # Field sections are those that have fields but aren't intro/results
    field_sections = [
        s for s in sections if s.get("fields") and s.get("type") not in ["intro", "results"]
    ]

    # Progressive disclosure: render sections one at a time based on completion
    _render_progressive_sections(field_sections, state, assessment_key, product_key)

    # Special rendering for home equity analysis results
    if assessment_key == "home_equity":
        _render_home_equity_results(state)

    # Calculate and show total at bottom using summary config from assessment
    summary_config = assessment_config.get("summary", {})
    
    if summary_config:
        # Calculate total using proper formula from config (handles assets - debts correctly)
        total = _calculate_summary_total(summary_config, state)

        # Show total if calculated
        if total is not None and total != 0:
            summary_label = summary_config.get("label", "Total")
            display_format = summary_config.get("display_format", "${:,.0f}")
            
            try:
                formatted_total = display_format.format(total)
            except Exception:
                formatted_total = f"${total:,.0f}"
            
            st.markdown(
                f"""
                <div style="
                    margin: 32px 0 16px 0;
                    padding: 16px 0;
                    border-top: 2px solid #111827;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div style="font-size: 18px; font-weight: 600; color: #111827;">
                        {summary_label}
                    </div>
                    <div style="font-size: 28px; font-weight: 700; color: #111827;">
                        {formatted_total}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Mark as complete
    state["status"] = "done"

    # Compact navigation at bottom
    st.markdown("<div style='margin: 16px 0;'></div>", unsafe_allow_html=True)
    _render_page_navigation(assessment_key, product_key, assessment_config)


def _render_single_page_assessment(
    assessment_key: str,
    assessment_config: dict[str, Any],
    product_key: str,
    settings: dict[str, Any],
) -> None:
    """Render designated assessments on a single page with streamlined styling."""

    state_key = f"{product_key}_{assessment_key}"

    # Only initialize if not already in session_state (preserve active editing session)
    if state_key not in st.session_state:
        # Try loading from tiles first (primary source of truth)
        # CRITICAL: Use setdefault to get the ACTUAL reference, not a copy
        tiles = st.session_state.setdefault("tiles", {})
        product_tiles = tiles.setdefault(product_key, {})
        assessments_state = product_tiles.setdefault("assessments", {})
        saved_data = assessments_state.get(assessment_key)

        # Fall back to cost_v2_modules if not in tiles (legacy/demo users)
        if not saved_data:
            modules = st.session_state.get("cost_v2_modules", {})
            if assessment_key in modules:
                saved_data = modules[assessment_key].get("data", {})

        # Initialize with saved data if found, otherwise empty dict
        if saved_data:
            st.session_state[state_key] = saved_data.copy()
        else:
            st.session_state[state_key] = {}

    state = st.session_state[state_key]

    success_flash_key = f"{state_key}._flash_success"
    error_flash_key = f"{state_key}._flash_error"

    success_flash = st.session_state.pop(success_flash_key, None)
    error_flash = st.session_state.pop(error_flash_key, None)

    # NOTE: Do NOT call _persist_assessment_state here on initial load
    # It will overwrite saved data with an empty dict
    # Persistence happens when user interacts with fields

    # Render compact Navi panel at top (content varies by assessment type)
    from core.navi_module import render_module_navi_coach
    
    if assessment_key == "income_sources":
        render_module_navi_coach(
            title_text="Enter monthly income from all sources",
            body_text="Use Basic for a quick total or Advanced if you want to break it down.",
            tip_text=None,
        )
    elif assessment_key == "assets_resources":
        render_module_navi_coach(
            title_text="Enter available assets and resources",
            body_text="Include only assets that can realistically support care costs.",
            tip_text=None,
        )
    else:
        # Default for other assessments
        render_module_navi_coach(
            title_text="Complete this assessment",
            body_text="This information helps us build your complete financial picture.",
            tip_text=None,
        )

    st.markdown('<div class="sn-app module-container">', unsafe_allow_html=True)

    title = assessment_config.get("title", "Assessment")
    icon = assessment_config.get("icon", "📋")
    description = assessment_config.get("description", "")

    st.markdown(
        f"""
        <div style="display:flex; flex-direction:column; gap:10px; text-align:left;">
            <div style="font-size:30px; font-weight:700; color:#0f172a;">{icon} {title}</div>
            <div style="font-size:15px; color:#475569; line-height:1.6;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if success_flash:
        st.success(success_flash)
    if error_flash:
        st.warning(error_flash)

    sections = assessment_config.get("sections", [])
    field_sections = [
        s for s in sections if s.get("fields") and s.get("type") not in ["intro", "results"]
    ]

    intro_section = next((s for s in sections if s.get("type") == "intro"), None)
    if intro_section and intro_section.get("help_text"):
        st.markdown(
            f"<div style='font-size:14px; color:#475569; margin: 12px 0 24px 0;'>{intro_section.get('help_text')}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='margin: 12px 0 24px 0;'></div>", unsafe_allow_html=True)

    if field_sections:
        # Render sections vertically for mobile-friendly single-column layout
        for section in field_sections:
            # Use expander for collapsible sections
            section_title = section.get("title", "Section")
            section_icon = section.get("icon", "📋")

            # Determine if section should be expanded by default
            # First section expanded, others collapsed
            is_first = field_sections.index(section) == 0

            with st.expander(f"{section_icon} {section_title}", expanded=is_first):
                _render_section_content(section, state, product_key, assessment_key)
    else:
        st.write("No sections configured.")

    summary_config = assessment_config.get("summary", {})
    summary_value = _calculate_summary_total(summary_config, state)

    if summary_config and summary_value is not None:
        label = summary_config.get("label", "Summary")
        display_format = summary_config.get("display_format", "${:,.0f}")
        try:
            formatted_total = display_format.format(summary_value)
        except Exception:
            formatted_total = f"${summary_value:,.0f}"

        st.markdown(
            f"""
            <div style="
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px 18px;
                margin: 24px 0 8px 0;
                background: #fafafa;
            ">
                <div style="font-size:11px; font-weight:600; color:#6b7280; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:4px;">
                    {label}
                </div>
                <div style="font-size:26px; font-weight:700; color:#111827; margin-top:2px;">
                    {formatted_total}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='margin:24px 0 8px 0;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin: 24px 0 12px 0;'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])

    back_label = settings.get("back_label", "← Back to Assessments")
    save_label = settings.get("save_label", "Save")
    success_message = settings.get("success_message", "Details saved.")
    expert_requires = settings.get("expert_requires", [])
    expert_disabled_text = settings.get("expert_disabled_text")
    expert_button_label = settings.get("expert_button_label", "🚀 Expert Review →")

    with col1:
        if st.button(
            back_label, type="secondary", use_container_width=True, key=f"{assessment_key}_back"
        ):
            st.session_state.pop(f"{product_key}_current_assessment", None)
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            st.session_state.cost_v2_step = "assessments"
            safe_rerun()

    with col2:
        if st.button(
            save_label, type="primary", use_container_width=True, key=f"{assessment_key}_save"
        ):
            missing_fields = _get_missing_required_fields(field_sections, state)
            if missing_fields:
                st.session_state[error_flash_key] = "Please complete required fields: " + ", ".join(
                    missing_fields
                )
            else:
                previously_done = state.get("status") == "done"
                state["status"] = "done"
                state["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _persist_assessment_state(product_key, assessment_key, state)
                st.session_state[success_flash_key] = success_message

                event_payload = {
                    "product": product_key,
                    "assessment": assessment_key,
                    "mode": "single_page",
                }
                summary_value_for_event = _calculate_summary_total(summary_config, state)
                if summary_config and summary_value_for_event is not None:
                    event_payload["calculated_summary"] = summary_value_for_event

                if previously_done:
                    log_event("assessment.updated", event_payload)
                else:
                    log_event("assessment.completed", event_payload)

                # Navigate back to Financial Assessment Hub
                st.session_state.cost_v2_step = "assessments"
                st.session_state.pop(f"{product_key}_current_assessment", None)
            safe_rerun()

    with col3:

        def _is_complete(target_key: str) -> bool:
            if target_key == assessment_key:
                return state.get("status") == "done"
            return _is_assessment_complete(target_key, product_key)

        expert_ready = (
            all(_is_complete(target) for target in expert_requires) if expert_requires else True
        )

        if expert_ready:
            if st.button(
                expert_button_label,
                type="secondary",
                use_container_width=True,
                key=f"{assessment_key}_expert",
            ):
                # Clear step query param to prevent override
                if "step" in st.query_params:
                    del st.query_params["step"]
                st.session_state.cost_v2_step = "expert_review"
                st.session_state.pop(f"{product_key}_current_assessment", None)
                safe_rerun()
        else:
            if expert_disabled_text:
                st.markdown(
                    f"""
                    <div style="
                        background:#f8fafc;
                        border:1px dashed #cbd5f5;
                        border-radius:8px;
                        padding:12px;
                        font-size:13px;
                        color:#64748b;
                        text-align:center;
                    ">
                        {expert_disabled_text}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_section_content(
    section: dict[str, Any], state: dict[str, Any], product_key: str, assessment_key: str
) -> None:
    """Render a section's content with clean, minimal styling."""

    help_text = section.get("help_text")

    # Show help text if provided - more subtle styling
    if help_text:
        st.markdown(
            f"<div style='font-size:13px; color:#6b7280; margin-bottom:20px; line-height:1.5;'>{help_text}</div>",
            unsafe_allow_html=True,
        )

    # No mode toggle - all fields visible
    current_mode = "all"

    # Auto-calculate VA disability BEFORE rendering if relevant section
    # This ensures display_currency fields show the correct calculated value
    if assessment_key == "va_benefits" and section.get("id") == "va_disability":
        _auto_populate_va_disability(state)

    # Render fields
    new_values = _render_fields_for_page(section, state, current_mode)
    if new_values:
        # Check if VA-related fields changed before updating
        va_fields_changed = False
        va_dependents_changed = False
        if assessment_key == "va_benefits" and section.get("id") == "va_disability":
            va_fields_changed = any(
                key in new_values 
                for key in ["has_va_disability", "va_disability_rating", "va_dependents"]
            )
            # Only rerun when dependents changes (not rating)
            va_dependents_changed = (
                "va_dependents" in new_values 
                and state.get("va_dependents") != new_values["va_dependents"]
            )
        
        # Update both local state AND session_state immediately
        state.update(new_values)
        
        # CRITICAL: Also update the session_state dict directly so rerun picks up new values
        state_key = f"{product_key}_{assessment_key}"
        if state_key in st.session_state:
            st.session_state[state_key].update(new_values)

        # Re-calculate VA disability if relevant fields changed
        if va_fields_changed:
            _auto_populate_va_disability(state)
            # Also update session_state with calculated value
            if state_key in st.session_state:
                st.session_state[state_key]["va_disability_monthly"] = state.get("va_disability_monthly")
            
            # Persist first so the calculated value is saved
            _persist_assessment_state(product_key, assessment_key, state)
            
            # Force immediate rerun ONLY when dependents status changes
            if va_dependents_changed:
                st.rerun()
                return  # Exit after rerun to prevent double persistence

        _persist_assessment_state(product_key, assessment_key, state)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


def _persist_assessment_state(product_key: str, assessment_key: str, state: dict[str, Any]) -> None:
    """Persist assessment state into session tiles and module registry."""
    augmented_state = _augment_assessment_state(assessment_key, state)

    # Persist to tiles (used by financial profile builder)
    tiles = st.session_state.setdefault("tiles", {})
    product_tiles = tiles.setdefault(product_key, {})
    assessments_state = product_tiles.setdefault("assessments", {})
    assessments_state[assessment_key] = augmented_state.copy()

    # Update module registry for backward compatibility with hub metrics
    modules = st.session_state.setdefault("cost_v2_modules", {})
    module_entry = modules.setdefault(
        assessment_key, {"status": "in_progress", "progress": 0, "data": {}}
    )
    module_entry["data"] = augmented_state.copy()

    if augmented_state.get("status") == "done":
        module_entry["status"] = "completed"
        module_entry["progress"] = 100
    else:
        if module_entry.get("status") != "completed":
            module_entry["status"] = module_entry.get("status", "in_progress") or "in_progress"
            module_entry.setdefault("progress", 0)


def _augment_assessment_state(assessment_key: str, state: dict[str, Any]) -> dict[str, Any]:
    """Augment raw assessment state with normalized values and summaries."""
    base_state = dict(state or {})

    if assessment_key == "income":
        normalized = normalize_income_data(base_state)
        # Ensure total is up to date (normalize already calculates but recalc for certainty)
        normalized["total_monthly_income"] = calculate_total_monthly_income(normalized)
        return normalized

    if assessment_key == "assets":
        normalized = normalize_asset_data(base_state)
        normalized["total_asset_value"] = calculate_total_asset_value(normalized)
        normalized["total_asset_debt"] = calculate_total_asset_debt(normalized)
        normalized["net_asset_value"] = max(
            normalized["total_asset_value"] - normalized["total_asset_debt"], 0.0
        )
        return normalized

    if assessment_key == "home_equity":
        normalized = normalize_home_equity_data(base_state)
        return normalized

    return base_state


def _auto_populate_va_disability(state: dict[str, Any]) -> None:
    """
    Auto-populate VA disability monthly amount based on rating and dependents.
    
    This function calculates the monthly VA disability compensation using official
    2025 rates from the VA and updates the state with the calculated amount.
    
    Handles all cases:
    - has_va_disability is "no" → sets amount to 0
    - has_va_disability is "yes" + rating + dependents set → calculates amount
    - Missing data → does nothing
    """
    import streamlit as st

    has_disability = state.get("has_va_disability")

    # If no disability, set amount to 0
    if has_disability == "no":
        state["va_disability_monthly"] = 0.0
        # Also update in session state if this is a reference
        if "cost_planner_v2_va_benefits" in st.session_state:
            st.session_state["cost_planner_v2_va_benefits"]["va_disability_monthly"] = 0.0
        return

    # Only calculate if veteran has VA disability
    if has_disability != "yes":
        return

    rating = state.get("va_disability_rating")
    dependents = state.get("va_dependents")

    # Need both rating and dependents to calculate
    if rating is None or dependents is None:
        return

    try:
        # Calculate monthly amount using official rates
        monthly_amount = get_monthly_va_disability(rating, dependents)

        if monthly_amount is not None:
            # Update state dict with calculated amount
            state["va_disability_monthly"] = monthly_amount
            
            # Also ensure session state is updated directly
            if "cost_planner_v2_va_benefits" in st.session_state:
                st.session_state["cost_planner_v2_va_benefits"]["va_disability_monthly"] = monthly_amount

            # Show toast notification on calculation
            st.toast(f"✅ Calculated VA benefit: ${monthly_amount:,.2f}/month", icon="💰")
        else:
            st.toast("⚠️ Could not calculate VA benefit - please verify rating and dependents", icon="⚠️")
    except Exception as e:
        st.error(f"Error calculating VA disability: {e}")


def _calculate_summary_total(summary_config: dict[str, Any], state: dict[str, Any]) -> float | None:
    """
    Calculate summary total using the formula defined in config.
    
    Special handling for "calculated_by_engine" which uses helper functions
    to avoid double-counting in basic/advanced field modes.
    """
    if not summary_config:
        return None

    formula = summary_config.get("formula")
    if not formula:
        return None

    try:
        # Special case: Use calculation helpers for complex logic
        if formula == "calculated_by_engine":
            # Determine assessment type from state or config
            # For assets: use calculate_total_asset_value and subtract debts
            if "cash_liquid_total" in state or "checking_balance" in state:
                # This is the assets assessment
                from products.cost_planner_v2.utils.financial_helpers import (
                    calculate_total_asset_debt,
                    calculate_total_asset_value,
                )
                gross_assets = calculate_total_asset_value(state)
                total_debt = calculate_total_asset_debt(state)
                return max(gross_assets - total_debt, 0.0)
            return None

        # Standard sum() formula
        if formula.startswith("sum(") and formula.endswith(")"):
            field_names = [f.strip() for f in formula[4:-1].split(",") if f.strip()]
            total = 0.0
            for field_name in field_names:
                value = state.get(field_name)
                if isinstance(value, (int, float)):
                    total += float(value)
                elif isinstance(value, str) and value.strip():
                    try:
                        total += float(value)
                    except ValueError:
                        continue
            return total

        return float(eval(formula, {"__builtins__": {}}, state))
    except Exception:
        return None


def _get_missing_required_fields(
    sections: list[dict[str, Any]], state: dict[str, Any]
) -> list[str]:
    """Return labels for required fields that have not been completed."""
    from core.assessment_engine import _is_field_visible  # Local import to avoid circularity

    missing: list[str] = []
    for section in sections:
        for field in section.get("fields", []):
            if not field.get("required"):
                continue
            if not _is_field_visible(field, state):
                continue

            key = field.get("key")
            value = state.get(key)
            if value in (None, "", []):
                missing.append(field.get("label", key))

    return missing


def _load_all_assessments(product_key: str) -> list[dict[str, Any]]:
    """Load all assessment configurations."""

    # Load from modules/assessments/ directory (colocation with product code)
    assessments_dir = Path(__file__).parent / "modules" / "assessments"

    if not assessments_dir.exists():
        return []

    assessments = []

    # Load each JSON file
    for json_file in sorted(assessments_dir.glob("*.json")):
        try:
            with open(json_file) as f:
                config = json.load(f)
                assessments.append(config)
        except Exception as e:
            st.error(f"Error loading {json_file.name}: {e}")

    # Sort by sort_order if specified
    assessments.sort(key=lambda a: a.get("sort_order", 999))

    return assessments


def _load_assessment_config(assessment_key: str, product_key: str) -> dict[str, Any] | None:
    """Load a specific assessment configuration."""

    # Load from modules/assessments/ directory (colocation with product code)
    config_path = Path(__file__).parent / "modules" / "assessments" / f"{assessment_key}.json"

    if not config_path.exists():
        return None

    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading assessment config: {e}")
        return None


def _is_assessment_visible(assessment: dict[str, Any], flags: dict[str, Any]) -> bool:
    """Check if assessment should be visible based on flags."""

    visible_if = assessment.get("visible_if")
    if not visible_if:
        return True

    # Check flag condition
    flag_key = visible_if.get("flag")
    if not flag_key:
        return True

    flag_value = flags.get(flag_key, False)
    expected = visible_if.get("equals", True)

    return flag_value == expected


def _is_assessment_complete(assessment_key: str, product_key: str) -> bool:
    """Check if an assessment is complete by checking persistent storage."""

    # Check persistent storage (tiles first, then cost_v2_modules)
    # Don't rely on temporary working state which may not exist
    tiles = st.session_state.get("tiles", {})
    product_tiles = tiles.get(product_key, {})
    assessments_state = product_tiles.get("assessments", {})
    saved_data = assessments_state.get(assessment_key)
    
    if saved_data and saved_data.get("status") == "done":
        return True
    
    # Fall back to cost_v2_modules
    modules = st.session_state.get("cost_v2_modules", {})
    if assessment_key in modules:
        module_status = modules[assessment_key].get("status")
        return module_status == "completed"
    
    return False


def _get_assessment_progress(assessment_key: str, product_key: str) -> int:
    """Get assessment progress percentage."""

    state_key = f"{product_key}_{assessment_key}"
    state = st.session_state.get(state_key, {})

    # Load config to count sections
    config = _load_assessment_config(assessment_key, product_key)
    if not config:
        return 0

    sections = config.get("sections", [])
    current_section = st.session_state.get(f"{state_key}._section", 0)

    # Calculate progress
    if len(sections) == 0:
        return 0

    progress = int((current_section / len(sections)) * 100)
    return min(progress, 100)


def _render_fields_for_page(section: dict[str, Any], state: dict[str, Any], mode: str = "all") -> dict[str, Any]:
    """
    Render fields for a section in page mode (all fields visible at once).
    Returns dict of updated field values.
    
    Args:
        section: Section configuration dict
        state: Current assessment state
        mode: Current mode (always "all" - no mode toggle)
    """
    from core.assessment_engine import _render_fields

    # Render all visible fields
    return _render_fields(section, state, mode)


def _render_single_info_box(info_box: dict[str, Any]) -> None:
    """Render a single info box."""
    variant = info_box.get("variant", "info")
    message = info_box.get("message", "")

    # Map variants to Streamlit methods
    if variant == "success":
        st.success(message)
    elif variant == "warning":
        st.warning(message)
    elif variant == "error":
        st.error(message)
    else:
        st.info(message)


def _render_page_navigation(
    assessment_key: str, product_key: str, assessment_config: dict[str, Any]
) -> None:
    """Render navigation buttons at bottom of assessment page."""

    # Load all assessments to determine next assessment based on sort_order
    from core.paths import get_config_path
    
    config_path = get_config_path("cost_planner_v2_modules.json")
    with open(config_path, "r") as f:
        all_config = json.load(f)
    
    all_assessments = all_config.get("modules", [])
    # Sort by sort_order
    all_assessments.sort(key=lambda a: a.get("sort_order", 999))
    
    # Find current assessment index
    current_idx = next(
        (i for i, a in enumerate(all_assessments) if a.get("key") == assessment_key),
        -1
    )
    
    # Determine next assessment
    next_assessment = None
    next_assessment_title = None
    if current_idx >= 0 and current_idx < len(all_assessments) - 1:
        # Get next assessment (income → assets → etc.)
        next_assessment_obj = all_assessments[current_idx + 1]
        next_assessment = next_assessment_obj.get("key")
        next_assessment_title = next_assessment_obj.get("title", "Next Assessment")
    
    # Two button layout: "Save & Back" and "Go to Next"
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        pass  # Empty for spacing
    
    with col2:
        # Save & Back to Hub
        if st.button("← Back to Assessments", use_container_width=True, type="secondary", key=f"{assessment_key}_save_back"):
            # Mark assessment as complete and PERSIST to storage
            state_key = f"{product_key}_{assessment_key}"
            if state_key in st.session_state:
                st.session_state[state_key]["status"] = "done"
                # CRITICAL: Persist to tiles/cost_v2_modules before navigating
                _persist_assessment_state(product_key, assessment_key, st.session_state[state_key])
            
            # Clear current assessment and return to hub
            st.session_state.pop(f"{product_key}_current_assessment", None)
            
            # Update URL to show hub (remove assessment param)
            if "assessment" in st.query_params:
                del st.query_params["assessment"]
            
            # Ensure we're on assessments step
            st.query_params["page"] = "cost_v2"
            st.query_params["step"] = "assessments"
            
            st.session_state.cost_v2_step = "assessments"
            st.rerun()
    
    with col3:
        # Go to next assessment or finish
        if next_assessment:
            button_label = f"Go to {next_assessment_title} →"
        else:
            button_label = "Finish & Review →"
        
        if st.button(button_label, use_container_width=True, type="primary", key=f"{assessment_key}_save_continue"):
            # Mark assessment as complete and PERSIST to storage
            state_key = f"{product_key}_{assessment_key}"
            if state_key in st.session_state:
                st.session_state[state_key]["status"] = "done"
                # CRITICAL: Persist to tiles/cost_v2_modules before navigating
                _persist_assessment_state(product_key, assessment_key, st.session_state[state_key])
            
            if next_assessment:
                # Go to next assessment
                st.session_state[f"{product_key}_current_assessment"] = next_assessment
                
                # Update URL to show next assessment
                st.query_params["page"] = "cost_v2"
                st.query_params["step"] = "assessments"
                st.query_params["assessment"] = next_assessment
                
                st.session_state.cost_v2_step = "assessments"
            else:
                # All assessments complete - go to expert review
                st.session_state.pop(f"{product_key}_current_assessment", None)
                
                # Update URL for expert review
                st.query_params["page"] = "cost_v2"
                st.query_params["step"] = "expert_review"
                if "assessment" in st.query_params:
                    del st.query_params["assessment"]
                
                st.session_state.cost_v2_step = "expert_review"
            
            st.rerun()


__all__ = ["render_assessment_hub", "render_assessment_page"]
