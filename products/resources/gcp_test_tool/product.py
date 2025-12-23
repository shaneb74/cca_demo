"""
GCP Test Tool - Internal Testing Tool

Allows advisors to test the complete Guided Care Plan logic with direct inputs.
Replicates all GCP v4 sections and scoring to validate tier recommendations,
cognitive gates, behavior gates, and LLM adjudication logic.

TODO: Remove this product by 2025-12-15 after validation phase complete.
"""

import json
import streamlit as st
from datetime import datetime
from pathlib import Path
from typing import Any

from products.gcp_v4.modules.care_recommendation.logic import (
    derive_outcome,
    cognitive_gate,
    cognition_band,
    support_band,
    mc_behavior_gate_enabled,
    cognitive_gate_behaviors_only,
    TIER_THRESHOLDS,
)
from ui.header_simple import render_header_simple
from ui.footer_simple import render_footer_simple
from core.ui import render_navi_panel_v2


# Path to validation cases JSON
VALIDATION_CASES_PATH = Path(__file__).parent / "gcp_validation_cases.json"


def _load_validation_cases() -> list[dict[str, Any]]:
    """Load saved GCP validation test cases.
    
    Returns:
        List of validation cases
    """
    if not VALIDATION_CASES_PATH.exists():
        return []
    
    try:
        with open(VALIDATION_CASES_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load validation cases: {e}")
        return []


def _save_validation_case(case: dict[str, Any]) -> None:
    """Save a GCP validation test case to JSON.
    
    Args:
        case: Test case data with inputs, results, and optional notes
    """
    cases = _load_validation_cases()
    cases.append(case)
    
    try:
        with open(VALIDATION_CASES_PATH, "w") as f:
            json.dump(cases, f, indent=2)
        st.success("✅ Test case saved successfully!")
    except Exception as e:
        st.error(f"Failed to save test case: {e}")


def _render_about_you_section() -> None:
    """Render About You section inputs."""
    with st.expander("📋 **About You**", expanded=True):
        st.caption("GCP Section: `about_you`")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.gcp_age_range = st.radio(
                "Age Range",
                options=["under_65", "65_74", "75_84", "85_plus"],
                format_func=lambda x: {
                    "under_65": "Under 65",
                    "65_74": "65–74",
                    "75_84": "75–84",
                    "85_plus": "85+"
                }[x],
                index=["under_65", "65_74", "75_84", "85_plus"].index(
                    st.session_state.get("gcp_age_range", "75_84")
                ),
                key="gcp_test_age"
            )
            
            st.session_state.gcp_living_situation = st.radio(
                "Living Situation",
                options=["alone", "with_spouse_or_partner", "with_family", "assisted_living"],
                format_func=lambda x: {
                    "alone": "Alone",
                    "with_spouse_or_partner": "With spouse/partner",
                    "with_family": "With family",
                    "assisted_living": "Assisted living"
                }[x],
                index=["alone", "with_spouse_or_partner", "with_family", "assisted_living"].index(
                    st.session_state.get("gcp_living_situation", "alone")
                ),
                key="gcp_test_living"
            )
        
        with col2:
            st.session_state.gcp_isolation = st.radio(
                "Geographic Isolation",
                options=["accessible", "somewhat", "very"],
                format_func=lambda x: {
                    "accessible": "Accessible",
                    "somewhat": "Somewhat isolated",
                    "very": "Very isolated"
                }[x],
                index=["accessible", "somewhat", "very"].index(
                    st.session_state.get("gcp_isolation", "accessible")
                ),
                key="gcp_test_isolation"
            )


def _render_medication_mobility_section() -> None:
    """Render Medication & Mobility section inputs."""
    with st.expander("💊 **Medication & Mobility**", expanded=True):
        st.caption("GCP Section: `medication_mobility`")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.gcp_meds_complexity = st.radio(
                "Medication Complexity",
                options=["none", "simple", "moderate", "complex"],
                format_func=lambda x: {
                    "none": "None",
                    "simple": "Simple",
                    "moderate": "Moderate",
                    "complex": "Complex"
                }[x],
                index=["none", "simple", "moderate", "complex"].index(
                    st.session_state.get("gcp_meds_complexity", "simple")
                ),
                key="gcp_test_meds"
            )
            
            st.session_state.gcp_mobility = st.radio(
                "Mobility Level",
                options=["independent", "walker", "wheelchair", "bedbound"],
                format_func=lambda x: {
                    "independent": "Walks independently",
                    "walker": "Uses cane/walker",
                    "wheelchair": "Uses wheelchair",
                    "bedbound": "Bed-bound"
                }[x],
                index=["independent", "walker", "wheelchair", "bedbound"].index(
                    st.session_state.get("gcp_mobility", "independent")
                ),
                key="gcp_test_mobility"
            )
            
            st.session_state.gcp_transfers = st.radio(
                "Transfer Assistance",
                options=["independent", "standby", "one_person", "two_person", "lift"],
                format_func=lambda x: {
                    "independent": "No assistance",
                    "standby": "Stand-by assist",
                    "one_person": "1-person assist",
                    "two_person": "2-person assist",
                    "lift": "Mechanical lift"
                }[x],
                index=["independent", "standby", "one_person", "two_person", "lift"].index(
                    st.session_state.get("gcp_transfers", "independent")
                ),
                key="gcp_test_transfers"
            )
        
        with col2:
            st.session_state.gcp_falls = st.radio(
                "Fall History",
                options=["none", "one", "multiple"],
                format_func=lambda x: {
                    "none": "No falls",
                    "one": "One fall",
                    "multiple": "Multiple falls"
                }[x],
                index=["none", "one", "multiple"].index(
                    st.session_state.get("gcp_falls", "none")
                ),
                key="gcp_test_falls"
            )
            
            st.markdown("**Chronic Conditions** (multi-select)")
            chronic_options = ["diabetes", "chf", "copd", "hypertension", "arthritis", "stroke", "parkinsons", "cancer", "other"]
            st.session_state.gcp_chronic = st.multiselect(
                "Select all that apply",
                options=chronic_options,
                default=st.session_state.get("gcp_chronic", []),
                key="gcp_test_chronic"
            )


def _render_cognition_section() -> None:
    """Render Cognition & Mental Health section inputs."""
    with st.expander("🧠 **Cognition & Mental Health**", expanded=True):
        st.caption("GCP Section: `cognition_mental_health`")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.gcp_memory_changes = st.radio(
                "Memory Changes",
                options=["no_concerns", "occasional", "moderate", "severe"],
                format_func=lambda x: {
                    "no_concerns": "No concerns",
                    "occasional": "Occasional forgetfulness",
                    "moderate": "Moderate issues",
                    "severe": "Severe (dementia/Alzheimer's)"
                }[x],
                index=["no_concerns", "occasional", "moderate", "severe"].index(
                    st.session_state.get("gcp_memory_changes", "no_concerns")
                ),
                key="gcp_test_memory"
            )
            
            st.session_state.gcp_mood = st.radio(
                "Mood",
                options=["great", "mostly_good", "okay", "low"],
                format_func=lambda x: {
                    "great": "Great",
                    "mostly_good": "Mostly good",
                    "okay": "Okay",
                    "low": "Low"
                }[x],
                index=["great", "mostly_good", "okay", "low"].index(
                    st.session_state.get("gcp_mood", "mostly_good")
                ),
                key="gcp_test_mood"
            )
        
        with col2:
            st.markdown("**Behaviors** (multi-select)")
            behavior_options = [
                "wandering", "aggression", "elopement", "confusion", 
                "sundowning", "repetitive", "judgment", "hoarding", "sleep"
            ]
            st.session_state.gcp_behaviors = st.multiselect(
                "Select all that apply",
                options=behavior_options,
                format_func=lambda x: x.replace("_", " ").title(),
                default=st.session_state.get("gcp_behaviors", []),
                key="gcp_test_behaviors"
            )
        
        # Cognitive diagnosis confirmation (show for moderate OR severe)
        memory_changes = st.session_state.get("gcp_memory_changes", "no_concerns")
        if memory_changes in ["moderate", "severe"]:
            st.markdown("---")
            st.markdown("**🏥 Formal Diagnosis** (CRITICAL for Memory Care gate)")
            st.caption("Memory Care requires formal dementia/Alzheimer's diagnosis")
            st.session_state.gcp_cognitive_dx = st.radio(
                "Has a doctor formally diagnosed dementia or Alzheimer's?",
                options=["dx_yes", "dx_no", "dx_unsure"],
                format_func=lambda x: {
                    "dx_yes": "✅ Yes, diagnosed",
                    "dx_no": "❌ No",
                    "dx_unsure": "❓ Not sure"
                }[x],
                index=["dx_yes", "dx_no", "dx_unsure"].index(
                    st.session_state.get("gcp_cognitive_dx", "dx_yes")
                ),
                key="gcp_test_dx",
                horizontal=True
            )
            
            # Show warning if no diagnosis
            if st.session_state.get("gcp_cognitive_dx") != "dx_yes":
                st.warning("⚠️ **Cognitive Gate:** Memory Care will be BLOCKED without formal diagnosis")


def _render_daily_living_section() -> None:
    """Render Daily Living section inputs."""
    with st.expander("🏠 **Daily Living**", expanded=True):
        st.caption("GCP Section: `daily_living`")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.gcp_help_overall = st.radio(
                "Overall Help Needed",
                options=["independent", "some_help", "daily_help", "full_support"],
                format_func=lambda x: {
                    "independent": "Independent",
                    "some_help": "Some help",
                    "daily_help": "Daily help",
                    "full_support": "Full support"
                }[x],
                index=["independent", "some_help", "daily_help", "full_support"].index(
                    st.session_state.get("gcp_help_overall", "some_help")
                ),
                key="gcp_test_help"
            )
            
            st.markdown("**BADLs** (multi-select)")
            badl_options = [
                "bathing", "dressing", "eating", "toileting", 
                "transferring", "hygiene", "mobility"
            ]
            st.session_state.gcp_badls = st.multiselect(
                "Basic ADLs needing help",
                options=badl_options,
                format_func=lambda x: x.replace("_", " ").title(),
                default=st.session_state.get("gcp_badls", []),
                key="gcp_test_badls"
            )
            
            st.session_state.gcp_incontinence = st.radio(
                "Incontinence Management",
                options=["none", "occasional", "frequent_reminders", "complete"],
                format_func=lambda x: {
                    "none": "No issues",
                    "occasional": "Occasional accidents",
                    "frequent_reminders": "Frequent - needs reminders",
                    "complete": "Complete assistance"
                }[x],
                index=["none", "occasional", "frequent_reminders", "complete"].index(
                    st.session_state.get("gcp_incontinence", "none")
                ),
                key="gcp_test_incontinence"
            )
        
        with col2:
            st.session_state.gcp_primary_support = st.radio(
                "Primary Support Provider",
                options=["family", "paid", "community", "none"],
                format_func=lambda x: {
                    "family": "Family/friends",
                    "paid": "Paid caregiver",
                    "community": "Community/agency",
                    "none": "No regular support"
                }[x],
                index=["family", "paid", "community", "none"].index(
                    st.session_state.get("gcp_primary_support", "family")
                ),
                key="gcp_test_support"
            )
            
            st.markdown("**IADLs** (multi-select)")
            iadl_options = [
                "meal_prep", "housekeeping", "finances", "med_management",
                "transportation", "shopping", "communication"
            ]
            st.session_state.gcp_iadls = st.multiselect(
                "Instrumental ADLs needing help",
                options=iadl_options,
                format_func=lambda x: x.replace("_", " ").title(),
                default=st.session_state.get("gcp_iadls", []),
                key="gcp_test_iadls"
            )
        
        # Hours per day
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.gcp_hours_per_day = st.radio(
                "Hours per Day of Assistance",
                options=["<1h", "1-3h", "4-8h", "12-16h", "24h"],
                index=["<1h", "1-3h", "4-8h", "12-16h", "24h"].index(
                    st.session_state.get("gcp_hours_per_day", "1-3h")
                ),
                key="gcp_test_hours"
            )
        
        with col2:
            st.session_state.gcp_days_per_week = st.radio(
                "Days per Week Care Needed",
                options=["1-2", "3-4", "5-6", "7"],
                format_func=lambda x: {
                    "1-2": "1-2 days (occasional)",
                    "3-4": "3-4 days (part-time)",
                    "5-6": "5-6 days (near-daily)",
                    "7": "7 days (every day)"
                }[x],
                index=["1-2", "3-4", "5-6", "7"].index(
                    st.session_state.get("gcp_days_per_week", "5-6")
                ),
                key="gcp_test_days"
            )


def _render_move_preferences_section() -> None:
    """Render Move Preferences section inputs."""
    with st.expander("🏡 **Move Preferences** (Optional)", expanded=False):
        st.caption("GCP Section: `move_preferences` (only shown for facility recommendations)")
        
        st.session_state.gcp_move_preference = st.radio(
            "Willingness to Move",
            options=["1", "2", "3", "4"],
            format_func=lambda x: {
                "1": "1 – Strong preference to stay home",
                "2": "2 – Uncertain",
                "3": "3 – Open if it improves care",
                "4": "4 – Comfortable moving"
            }[x],
            index=["1", "2", "3", "4"].index(
                st.session_state.get("gcp_move_preference", "2")
            ),
            key="gcp_test_move",
            horizontal=True
        )


def _render_input_form() -> None:
    """Render complete GCP input form."""
    st.markdown("### 📋 GCP Input Form")
    st.caption("All sections match GCP v4 module structure")
    
    # Render all sections
    _render_about_you_section()
    _render_medication_mobility_section()
    _render_cognition_section()
    _render_daily_living_section()
    _render_move_preferences_section()
    
    st.markdown("---")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧮 Calculate Recommendation", type="primary", use_container_width=True):
            _calculate_and_store()
    with col2:
        if st.button("🗑️ Clear Form", use_container_width=True):
            _clear_form()


def _clear_form() -> None:
    """Clear all form inputs."""
    # About You
    st.session_state.gcp_age_range = "75_84"
    st.session_state.gcp_living_situation = "alone"
    st.session_state.gcp_isolation = "accessible"
    
    # Medication & Mobility
    st.session_state.gcp_meds_complexity = "simple"
    st.session_state.gcp_mobility = "independent"
    st.session_state.gcp_falls = "none"
    st.session_state.gcp_chronic = []
    
    # Cognition & Mental Health
    st.session_state.gcp_memory_changes = "no_concerns"
    st.session_state.gcp_mood = "mostly_good"
    st.session_state.gcp_behaviors = []
    st.session_state.gcp_cognitive_dx = "dx_yes"
    
    # Daily Living
    st.session_state.gcp_help_overall = "some_help"
    st.session_state.gcp_badls = []
    st.session_state.gcp_iadls = []
    st.session_state.gcp_primary_support = "family"
    st.session_state.gcp_hours_per_day = "1-3h"
    
    # Move Preferences
    st.session_state.gcp_move_preference = "2"
    
    # Clear results
    if "gcp_test_results" in st.session_state:
        del st.session_state.gcp_test_results
    
    st.rerun()


def _calculate_and_store() -> None:
    """Calculate GCP recommendation using actual GCP logic, store results."""
    # Build answers dict (matches GCP v4 structure)
    answers = {
        # About You
        "age_range": st.session_state.get("gcp_age_range", "75_84"),
        "living_situation": st.session_state.get("gcp_living_situation", "alone"),
        "isolation": st.session_state.get("gcp_isolation", "accessible"),
        
        # Medication & Mobility
        "meds_complexity": st.session_state.get("gcp_meds_complexity", "simple"),
        "mobility": st.session_state.get("gcp_mobility", "independent"),
        "transfers": st.session_state.get("gcp_transfers", "independent"),
        "falls": st.session_state.get("gcp_falls", "none"),
        "chronic_conditions": st.session_state.get("gcp_chronic", []),
        
        # Cognition & Mental Health
        "memory_changes": st.session_state.get("gcp_memory_changes", "no_concerns"),
        "mood": st.session_state.get("gcp_mood", "mostly_good"),
        "behaviors": st.session_state.get("gcp_behaviors", []),
        "cognitive_dx_confirm": st.session_state.get("gcp_cognitive_dx", "dx_yes"),
        
        # Daily Living
        "help_overall": st.session_state.get("gcp_help_overall", "some_help"),
        "badls": st.session_state.get("gcp_badls", []),
        "incontinence": st.session_state.get("gcp_incontinence", "none"),
        "iadls": st.session_state.get("gcp_iadls", []),
        "primary_support": st.session_state.get("gcp_primary_support", "family"),
        "hours_per_day": st.session_state.get("gcp_hours_per_day", "1-3h"),
        "days_per_week": st.session_state.get("gcp_days_per_week", "5-6"),
        
        # Move Preferences
        "move_preference": st.session_state.get("gcp_move_preference", "2"),
    }
    
    # Build minimal context
    context = {
        "age_range": answers["age_range"],
    }
    
    # Call actual GCP derive_outcome function
    try:
        outcome = derive_outcome(answers, context=context)
        
        # Extract gate results for diagnostics
        flags = []
        passes_cognitive = cognitive_gate(answers, flags)
        cog_band = cognition_band(answers, flags)
        sup_band = support_band(answers, flags)
        gate_enabled = mc_behavior_gate_enabled()
        has_risky_behaviors = cognitive_gate_behaviors_only(answers, flags)
        
        # Check if interim advice flag was set (MC would be recommended but blocked by no diagnosis)
        show_interim = st.session_state.get("_show_mc_interim_advice", False)
        
        # Capture LLM advice if available (set by derive_outcome when mode is shadow/assist/replace)
        llm_advice = st.session_state.get("_gcp_llm_advice", None)
        
        # Debug: Check if LLM was called
        if llm_advice:
            print(f"[GCP_TEST] LLM advice captured: tier={llm_advice.get('tier')} conf={llm_advice.get('confidence')}")
        else:
            print(f"[GCP_TEST] No LLM advice in session state (mode may be off or LLM call failed)")
            # Check if there were any LLM errors
            llm_error = st.session_state.get("_gcp_llm_error", None)
            if llm_error:
                print(f"[GCP_TEST] LLM error: {llm_error}")
        
        # Store results
        st.session_state.gcp_test_results = {
            "tier": outcome["tier"],
            "tier_score": outcome["tier_score"],
            "confidence": outcome["confidence"],
            "flags": outcome["flags"],
            "rationale": outcome["rationale"],
            "tier_rankings": outcome["tier_rankings"],
            "allowed_tiers": outcome.get("allowed_tiers", []),
            "cognitive_gate_pass": passes_cognitive,
            "cognition_band": cog_band,
            "support_band": sup_band,
            "behavior_gate_enabled": gate_enabled,
            "has_risky_behaviors": has_risky_behaviors,
            "show_interim_advice": show_interim,
            "llm_advice": llm_advice,  # Include LLM recommendation if available
            "answers": answers,
            "success": True,
            "error": None,
        }
        
        # Clear interim flag for next calculation
        st.session_state.pop("_show_mc_interim_advice", None)
        
    except Exception as e:
        st.session_state.gcp_test_results = {
            "success": False,
            "error": str(e),
            "answers": answers,
        }
    
    st.rerun()


def _render_results() -> None:
    """Render calculation results."""
    if "gcp_test_results" not in st.session_state:
        st.info("👈 Enter GCP inputs and click **Calculate Recommendation** to see results")
        return
    
    results = st.session_state.gcp_test_results
    
    if not results.get("success", False):
        st.error(f"❌ Calculation failed: {results.get('error', 'Unknown error')}")
        return
    
    st.markdown("### 📊 GCP Recommendation Results")
    
    # Show LLM mode indicator (using correct flag: FEATURE_LLM_GCP)
    try:
        from ai.llm_client import get_feature_gcp_mode
        llm_mode = get_feature_gcp_mode()
        mode_colors = {
            "off": "🔴",
            "shadow": "🟡", 
            "assist": "🟢",
            "replace": "🔵"
        }
        mode_desc = {
            "off": "LLM disabled - deterministic only",
            "shadow": "LLM runs but doesn't affect result (logging only)",
            "assist": "LLM provides advice, deterministic decides",
            "replace": "LLM recommendation used if valid"
        }
        st.info(f"{mode_colors.get(llm_mode, '⚪')} **LLM Mode:** `{llm_mode}` - {mode_desc.get(llm_mode, 'Unknown mode')}")
    except Exception as e:
        st.warning(f"Could not read LLM mode: {e}")
    
    # Check for interim advice flag
    show_interim = results.get("show_interim_advice", False)
    
    # Interim Advice Banner (when MC would be recommended but no diagnosis)
    if show_interim:
        st.markdown(
            """
            <div style="background: #fff9e6; border-left: 4px solid #f59e0b; padding: 16px; margin: 16px 0; border-radius: 4px;">
                <div style="color: #92400e; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                    ⚠️ Interim Recommendation
                </div>
                <div style="color: #1f2937; font-weight: 600; margin-bottom: 8px;">
                    Assisted Living recommended while seeking formal diagnosis
                </div>
                <div style="color: #4b5563; font-size: 0.875rem; line-height: 1.5;">
                    Memory Care communities typically require a confirmed dementia/Alzheimer's diagnosis. 
                    While arranging an evaluation, <strong>Assisted Living with memory support</strong> can provide 
                    safety, structure, and continuity.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Primary Recommendation - Show both Deterministic and LLM
    st.markdown("#### 🎯 Recommendation Comparison")
    
    tier_display = {
        "no_care_needed": "No Care Needed",
        "in_home": "In-Home Care",
        "assisted_living": "Assisted Living",
        "memory_care": "Memory Care",
        "memory_care_high_acuity": "Memory Care (High Acuity)"
    }
    
    # Get LLM advice if available
    llm_advice = results.get("llm_advice")
    
    # Show side-by-side comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔢 Deterministic Engine**")
        st.markdown(f"**Tier:** {tier_display.get(results['tier'], results['tier'])}")
        st.markdown(f"**Score:** {results['tier_score']} pts")
        st.markdown(f"**Confidence:** {results['confidence']:.0%}")
        st.caption("Based on point scoring + gates + tier mapping")
    
    with col2:
        st.markdown("**🤖 LLM Recommendation**")
        if llm_advice:
            llm_tier = llm_advice.get("tier", "N/A")
            llm_conf = llm_advice.get("confidence", 0)
            st.markdown(f"**Tier:** {tier_display.get(llm_tier, llm_tier)}")
            st.markdown(f"**Confidence:** {llm_conf:.0%}")
            
            # Show agreement indicator
            if llm_tier == results["tier"]:
                st.success("✅ Agrees with deterministic")
            else:
                st.warning(f"⚠️ Disagrees (det: {tier_display.get(results['tier'], results['tier'])})")
        else:
            st.info("No LLM recommendation available\n\n(Mode may be 'off' or LLM call failed)")
    
    # Show detailed metrics below
    st.markdown("##### Detailed Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Final Tier", tier_display.get(results["tier"], results["tier"]))
    with col2:
        st.metric("Tier Score", f"{results['tier_score']} pts")
    with col3:
        st.metric("Confidence", f"{results['confidence']:.0%}")
    
    st.markdown("---")
    
    # Tier Rankings
    st.markdown("#### 📈 All Tier Rankings")
    for tier, score in results["tier_rankings"]:
        is_selected = (tier == results["tier"])
        display = tier_display.get(tier, tier)
        
        if is_selected:
            st.markdown(f"**✅ {display}**: `{score} pts` ← **Selected**")
        else:
            st.markdown(f"   {display}: `{score} pts`")
    
    st.markdown("---")
    
    # Gate Analysis
    st.markdown("#### 🚪 Gate Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Cognitive Gate** (Memory Care Access)")
        if results["cognitive_gate_pass"]:
            st.success("✅ PASSED - Memory care allowed")
        else:
            st.error("❌ FAILED - Memory care blocked")
        
        # Show diagnosis status
        dx_status = results["answers"].get("cognitive_dx_confirm", "not_provided")
        dx_display = {
            "dx_yes": "✅ Yes (formal diagnosis)",
            "dx_no": "❌ No diagnosis",
            "dx_unsure": "❓ Unsure",
            "not_provided": "➖ Not answered"
        }
        st.caption(f"Diagnosis: {dx_display.get(dx_status, dx_status)}")
        st.caption(f"Cognition Band: `{results['cognition_band']}`")
        st.caption(f"Support Band: `{results['support_band']}`")
        
        # Explain gate logic
        if not results["cognitive_gate_pass"]:
            st.info("💡 **Why blocked:** Memory Care requires BOTH:\n- Moderate/severe memory OR risky behaviors\n- Formal dementia/Alzheimer's diagnosis")
    
    with col2:
        st.markdown("**Behavior Gate** (Moderate×High Filter)")
        if results["behavior_gate_enabled"]:
            st.info(f"🔒 Enabled")
            if results['cognition_band'] == "moderate" and results['support_band'] == "high":
                if results['has_risky_behaviors']:
                    st.success(f"✅ Risky behaviors present → MC allowed")
                else:
                    st.warning(f"⚠️ No risky behaviors → MC blocked")
        else:
            st.info("🔓 Disabled (feature flag off)")
        
        st.caption(f"Risky behaviors: {results['has_risky_behaviors']}")
        st.caption(f"Allowed Tiers: {', '.join(results['allowed_tiers'])}")
    
    st.markdown("---")
    
    # Rationale
    st.markdown("#### 💡 Deterministic Rationale")
    for item in results["rationale"]:
        st.markdown(f"- {item}")
    
    st.markdown("---")
    
    # LLM Reasoning (if available)
    llm_advice = results.get("llm_advice")
    if llm_advice:
        st.markdown("#### 🤖 LLM Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📝 Reasons**")
            reasons = llm_advice.get("reasons", [])
            if reasons:
                for reason in reasons:
                    st.markdown(f"- {reason}")
            else:
                st.caption("No reasons provided")
        
        with col2:
            st.markdown("**⚠️ Identified Risks**")
            risks = llm_advice.get("risks", [])
            if risks:
                for risk in risks:
                    st.markdown(f"- {risk}")
            else:
                st.caption("No specific risks identified")
        
        # Navi messages (conversational advice)
        navi_messages = llm_advice.get("navi_messages", [])
        if navi_messages:
            st.markdown("**💬 Conversational Advice**")
            for msg in navi_messages:
                st.info(msg)
        
        # Suggested questions
        questions = llm_advice.get("questions_next", [])
        if questions:
            st.markdown("**❓ Suggested Follow-up Questions**")
            for q in questions:
                st.markdown(f"- {q}")
        
        st.markdown("---")
    
    # Flags
    if results["flags"]:
        st.markdown("#### 🚩 Flags (Risk Factors & Care Needs)")
        st.caption("Flags identify specific care needs, risks, and support requirements")
        for flag in results["flags"]:
            label = flag.get('label', flag['id'].replace('_', ' ').title())
            description = flag.get('description', 'No description')
            tone = flag.get('tone', 'info')
            
            # Format with tone-based emoji
            tone_emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'critical': '🚨'
            }.get(tone, 'ℹ️')
            
            st.markdown(f"{tone_emoji} **{label}** (`{flag['id']}`)")
            st.caption(f"   {description}")
    
    st.markdown("---")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Copy Results", use_container_width=True):
            st.session_state.show_copy_dialog = True
            st.rerun()
    with col2:
        if st.button("💾 Save Test Case", use_container_width=True):
            st.session_state.show_save_dialog = True
            st.rerun()
    
    # Show copy dialog if triggered
    if st.session_state.get("show_copy_dialog", False):
        _show_copy_dialog()
        if st.button("✖️ Close", key="close_copy_dialog"):
            st.session_state.show_copy_dialog = False
            st.rerun()


def _show_copy_dialog() -> None:
    """Show results in copyable text format."""
    results = st.session_state.gcp_test_results
    
    tier_display = {
        "no_care_needed": "No Care Needed",
        "in_home": "In-Home Care",
        "assisted_living": "Assisted Living",
        "memory_care": "Memory Care",
        "memory_care_high_acuity": "Memory Care (High Acuity)"
    }
    
    # Format as text
    text = f"""GCP Test Tool Results
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

RECOMMENDATION:
--------------
Tier: {tier_display.get(results['tier'], results['tier'])}
Score: {results['tier_score']} pts
Confidence: {results['confidence']:.0%}

TIER RANKINGS:
-------------
{chr(10).join(f"  {tier_display.get(tier, tier)}: {score} pts" for tier, score in results['tier_rankings'])}

GATE ANALYSIS:
-------------
Cognitive Gate: {'PASSED' if results['cognitive_gate_pass'] else 'FAILED'}
  - Cognition Band: {results['cognition_band']}
  - Support Band: {results['support_band']}

Behavior Gate: {'Enabled' if results['behavior_gate_enabled'] else 'Disabled'}
  - Risky Behaviors: {results['has_risky_behaviors']}
  - Allowed Tiers: {', '.join(results['allowed_tiers'])}

RATIONALE:
---------
{chr(10).join(f"  - {item}" for item in results['rationale'])}

FLAGS:
-----
{chr(10).join(f"  - {flag.get('label', flag['id'])}: {flag.get('description', 'No description')}" for flag in results['flags']) if results['flags'] else '  None'}

LLM RECOMMENDATION:
------------------
"""
    
    llm_advice = results.get('llm_advice')
    if llm_advice:
        text += f"""Tier: {tier_display.get(llm_advice.get('tier', 'N/A'), llm_advice.get('tier', 'N/A'))}
Confidence: {llm_advice.get('confidence', 0):.0%}
Reasons:
{chr(10).join(f"  - {reason}" for reason in llm_advice.get('reasons', []))}
"""
    else:
        text += "No LLM recommendation available\n"
    
    # Show in expandable text area with copy button
    st.text_area("📋 Copy Results", text, height=400, key="copy_results_text")
    st.caption("💡 Click inside the text area and press Ctrl+A (Cmd+A on Mac) to select all, then Ctrl+C (Cmd+C) to copy")


def render(ctx=None) -> None:
    """Render GCP Test Tool.
    
    Args:
        ctx: Optional context (unused, for product interface compatibility)
    """
    # Render header
    render_header_simple(active_route="gcp_test_tool")
    
    # Render Navi panel
    render_navi_panel_v2(
        title="GCP Test Tool",
        reason="Test the complete Guided Care Plan logic with direct inputs. Validate tier recommendations, cognitive gates, behavior gates, and LLM adjudication.",
        encouragement={
            "icon": "🧪",
            "text": "Internal testing tool for validation",
            "status": "info"
        },
        context_chips=[
            {"label": "Testing Tool"},
            {"label": "Phase 1 Validation", "variant": "muted"},
        ],
        primary_action={"label": "", "route": ""},
        variant="product"
    )
    
    # Warning banner
    st.markdown(
        """
        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px; margin: 16px 0;">
            <strong>⚠️ Internal Testing Tool</strong> — 
            This tool uses the EXACT logic from GCP v4 module for accurate validation.
            Compare results against real assessments to verify tier recommendations.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Two-column layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        _render_input_form()
    
    with col2:
        _render_results()
    
    # Save dialog (if open)
    if st.session_state.get("show_save_dialog", False):
        with st.container():
            st.markdown("### 💾 Save Test Case")
            notes = st.text_area(
                "Optional Notes:", 
                placeholder="e.g., 'Real case from advisor Sarah, moderate cognition + high support without risky behaviors'",
                key="gcp_save_notes"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save", type="primary", use_container_width=True, key="gcp_save_confirm"):
                    _save_test_case_with_notes(notes)
                    st.session_state.show_save_dialog = False
                    st.rerun()
            with col2:
                if st.button("Cancel", use_container_width=True, key="gcp_save_cancel"):
                    st.session_state.show_save_dialog = False
                    st.rerun()
    
    # Render footer
    render_footer_simple()


def _save_test_case_with_notes(notes: str) -> None:
    """Save test case with optional notes.
    
    Args:
        notes: Optional notes about the test case
    """
    results = st.session_state.gcp_test_results
    
    case = {
        "timestamp": datetime.now().isoformat(),
        "inputs": results["answers"],
        "results": {
            "tier": results["tier"],
            "tier_score": results["tier_score"],
            "confidence": results["confidence"],
            "tier_rankings": results["tier_rankings"],
            "allowed_tiers": results["allowed_tiers"],
            "cognitive_gate_pass": results["cognitive_gate_pass"],
            "cognition_band": results["cognition_band"],
            "support_band": results["support_band"],
            "behavior_gate_enabled": results["behavior_gate_enabled"],
            "has_risky_behaviors": results["has_risky_behaviors"],
            "flags": [flag["id"] for flag in results["flags"]],
        },
        "notes": notes.strip() if notes else "",
    }
    
    _save_validation_case(case)
