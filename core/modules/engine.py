from __future__ import annotations

import importlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from html import escape as H
from typing import Any

import streamlit as st

from core.events import log_event
from core.nav import PRODUCTS
from core.session_store import safe_rerun

from . import components as components
from .layout import actions
from .schema import FieldDef, ModuleConfig, OutcomeContract, StepDef

import logging
from typing import Any, Dict, Iterable


def inject_module_css_once(css_text: str) -> None:
    """Inject module CSS once per session to avoid repeated injection.
    
    Args:
        css_text: CSS string to inject
    """
    ss = st.session_state
    if ss.get("_module_css_loaded"):
        return
    st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)
    ss["_module_css_loaded"] = True


# Memory Care diagnosis flag constants
_MC_DX_FLAG_IDS = {"memory_care_dx", "dementia_dx", "alzheimers_dx", "has_dementia_dx"}
_MC_NO_DX_FLAG_IDS = {"likely_mc_no_dx", "mc_no_dx", "no_dx_memory_care"}
_MC_TEXT_TOKENS = (
    "dementia", "alzheimer", "alzheimers", "alzheimer's", "alzheimer's",
    "lewy", "parkinson", "frontotemporal", "ftd", "vascular dementia"
)


def _get_outcome_flags() -> set[str]:
    """
    Extract flag ids from st.session_state["gcp_care_recommendation"]["_outcomes"]["flags"],
    which is a list of dicts.
    """
    ss = st.session_state
    try:
        flags: Iterable[Dict[str, Any]] = (
            ss.get("gcp_care_recommendation", {})
              .get("_outcomes", {})
              .get("flags", [])
        )
        return {f.get("id", "").lower() for f in flags if isinstance(f, dict) and f.get("id")}
    except Exception as e:
        logging.warning("MC_ELIG: Failed to parse outcome flags: %s", e)
        return set()


def _is_mc_recommended() -> bool:
    """Check if Memory Care is the recommended tier."""
    ss = st.session_state
    tier = (
        ss.get("gcp", {}).get("published_tier")
        or ss.get("gcp_care_recommendation", {}).get("tier")
        or ss.get("gcp_care_recommendation", {}).get("_outcomes", {}).get("tier")
        or ""
    )
    return "memory" in str(tier).lower()


def _has_dx_present() -> bool:
    """Check if a formal diagnosis is present in flags or profile."""
    ss = st.session_state
    outcome_ids = _get_outcome_flags()
    if outcome_ids & _MC_DX_FLAG_IDS:
        return True

    flags = ss.get("flags", {})
    if any(flags.get(k) for k in _MC_DX_FLAG_IDS):
        return True

    dx_list = ss.get("profile", {}).get("diagnoses") or []
    dx_text = " ".join(map(str, dx_list)).lower()
    return any(tok in dx_text for tok in _MC_TEXT_TOKENS)


def _mc_requires_eligibility_advice() -> bool:
    """
    True if Memory Care is recommended and:
    - we have a likely_mc_no_dx flag, or
    - no diagnosis present in flags/profile.
    """
    if not _is_mc_recommended():
        return False

    outcome_ids = _get_outcome_flags()
    has_no_dx_flag = bool(outcome_ids & _MC_NO_DX_FLAG_IDS)
    has_dx = _has_dx_present()
    show = has_no_dx_flag or not has_dx

    logging.info(
        "MC_ELIG: memory_care recommended=%s, no_dx_flag=%s, has_dx=%s → show=%s",
        _is_mc_recommended(), has_no_dx_flag, has_dx, show
    )
    return show


def _get_cached_mc_advice() -> bool:
    """
    Get cached MC eligibility advice decision. Computes once per results view,
    then caches to prevent flashing during reruns.
    """
    cache_key = "_mc_advice_cached"
    if cache_key not in st.session_state:
        decision = _mc_requires_eligibility_advice()
        st.session_state[cache_key] = decision
        logging.info("MC_ELIG: cached decision=%s", decision)
    return st.session_state[cache_key]


def is_interim_al_recommended() -> bool:
    """
    Presentational helper: true when MC is recommended but a formal dementia DX
    is not present and the flow flagged likely_mc_no_dx. Used to:
      - override subtitle under the results header
      - render the interim callout card
    Does not alter the computed recommendation.
    
    Also checks for _show_mc_interim_advice flag set by adjudication clamp.
    """
    # Check if adjudication clamp set the interim advice flag
    if st.session_state.get("_show_mc_interim_advice", False):
        return True
    
    # Fallback to original logic for non-clamped cases
    if not _is_mc_recommended():
        return False
    if _has_dx_present():
        return False
    outcome_ids = _get_outcome_flags()
    return bool(outcome_ids & _MC_NO_DX_FLAG_IDS)


def get_cached_interim_al() -> bool:
    """
    Get cached interim AL decision. Computes once per results view,
    then caches to prevent flashing during reruns.
    """
    cache_key = "_interim_al_cached"
    if cache_key not in st.session_state:
        decision = is_interim_al_recommended()
        st.session_state[cache_key] = decision
        logging.info("INTERIM_AL: cached decision=%s", decision)
    return st.session_state[cache_key]


def get_final_recommendation_tier(state=None) -> str:
    """
    Single source of truth for final recommendation tier (post-adjudication).
    
    Returns the clamped tier, respecting interim AL flag when set.
    Use this everywhere instead of reading gcp.published_tier directly.
    """
    if state is None:
        state = st.session_state
    
    g = state.get("gcp", {})
    final_tier = g.get("published_tier") or g.get("recommended_tier") or g.get("deterministic_tier") or ""
    
    # Safety check: if interim flag is set but tier is still MC, force to AL
    if state.get("_show_mc_interim_advice") and final_tier not in ("assisted_living",):
        logging.warning(
            "TIER_INCONSISTENCY: interim=True but tier=%s, forcing to assisted_living",
            final_tier
        )
        final_tier = "assisted_living"
    
    return final_tier


def is_results_view(state=None) -> bool:
    """
    Check if user is on GCP Summary/Results screen.
    
    Used to suppress hours hints and buttons on final results,
    while keeping them active in Cost Planner In-Home.
    
    Returns:
        True if on GCP results/summary screen
    """
    if state is None:
        state = st.session_state
    
    # Check route
    route = (state.get("route") or state.get("current_route") or "").lower()
    if "result" in route:
        try:
            print(f"[HOURS_GUARD] is_results_view=True (route={route})")
        except Exception:
            pass
        return True
    
    # Check step ID (multiple possible keys)
    step = (
        state.get("gcp_current_step_id") or
        state.get("gcp_care_recommendation._step") or
        state.get("step_id") or
        state.get("current_step") or
        ""
    ).lower()
    
    result = step == "results"
    try:
        print(f"[HOURS_GUARD] is_results_view={result} (step={step or 'None'})")
    except Exception:
        pass
    return result


def is_cost_planner_inhome(state=None) -> bool:
    """
    Check if Cost Planner is showing In-Home assessment.
    
    Hours hints should ONLY show in CP In-Home context,
    not on GCP Summary or other CP tabs (AL/MC).
    
    Returns:
        True if Cost Planner In-Home tab is selected
    """
    if state is None:
        state = st.session_state
    
    # Check selected assessment/tab
    selected = (state.get("cp_selected_assessment") or "").lower()
    
    # Also check if we're actually in CP (not GCP)
    route = (state.get("route") or "").lower()
    in_cp = "cost" in route or "planner" in route or state.get("cp_intro", False)
    
    result = in_cp and selected in ("home", "in_home", "in_home_care", "inhome")
    try:
        print(f"[HOURS_GUARD] is_cost_planner_inhome={result} (in_cp={in_cp} selected={selected or 'None'})")
    except Exception:
        pass
    return result


def get_results_subtitle(state=None) -> str:
    """
    Returns the subtitle under 'Your Guided Care Plan' based on final tier.
    If clamped (no DX), show Assisted Living with enhanced cognitive support.
    
    This ensures the subtitle always reflects the POST-ADJUDICATION tier,
    not the pre-clamp tier from the scoring engine.
    """
    if state is None:
        state = st.session_state
    
    # Check if we're in interim AL case (MC clamped due to no DX)
    if state.get("_show_mc_interim_advice"):
        return "Assisted Living with enhanced cognitive support"
    
    # Get final tier from canonical source
    tier = get_final_recommendation_tier(state)
    
    # Map tier to subtitle
    if tier in ("memory_care", "memory_care_high_acuity"):
        person = state.get("person_name") or state.get("person_a_name") or "your loved one"
        return f"Memory care is recommended for {person}."
    elif tier == "assisted_living":
        person = state.get("person_name") or state.get("person_a_name") or "your loved one"
        return f"Assisted Living is recommended for {person}."
    elif tier in ("in_home", "in_home_care"):
        person = state.get("person_name") or state.get("person_a_name") or "your loved one"
        return f"In-home care is recommended for {person}."
    else:
        person = state.get("person_name") or state.get("person_a_name") or "your loved one"
        return f"Here's the best next step for {person}."


def assert_nav_consistency(state=None, *, where: str = "UNKNOWN"):
    """
    Assert navigation consistency: verify interim flag matches published tier.
    Logs warnings if state is inconsistent (interim=True but tier≠AL).
    
    Args:
        state: Session state dict (defaults to st.session_state)
        where: Location identifier for logging (e.g., "RESULTS", "CP")
    """
    if state is None:
        state = st.session_state
    
    final_tier = get_final_recommendation_tier(state)
    pub = state.get("gcp", {}).get("published_tier")
    interim = bool(state.get("_show_mc_interim_advice"))
    
    if interim and pub != "assisted_living":
        logging.error(
            "NAV_ASSERT[%s]: interim=True but published_tier=%s (expected assisted_living)",
            where, pub
        )
    
    logging.info(
        "NAV_ASSERT[%s]: final=%s published=%s interim=%s",
        where, final_tier, pub, interim
    )


def adjudicate_final_tier(base_tier: str, llm_tier: str | None = None) -> tuple[str, dict[str, Any]]:
    """
    Adjudicate final tier recommendation with non-negotiable safety gates.
    
    CLAMP RULE: No Memory Care without formal diagnosis.
    If MC is suggested without DX, downshift to Assisted Living with advisory.
    
    Args:
        base_tier: Deterministic tier from scoring engine
        llm_tier: Optional LLM-suggested tier (if LLM mode enabled)
    
    Returns:
        tuple: (final_tier, meta_dict)
            - final_tier: The adjudicated tier to publish
            - meta_dict: Advisory metadata (e.g., {"advisory": {"id": "mc_interim_advice", "reason": "no_dx"}})
    """
    # Prefer LLM tier if available, otherwise use deterministic
    suggested_tier = llm_tier or base_tier
    
    # Check for formal diagnosis
    has_dx = _has_dx_present()
    
    # SAFETY GATE: Clamp Memory Care to Assisted Living if no diagnosis
    if suggested_tier in ("memory_care", "memory_care_high_acuity") and not has_dx:
        final_tier = "assisted_living"
        meta = {
            "advisory": {
                "id": "mc_interim_advice",
                "reason": "no_dx",
                "suggested_tier": suggested_tier,
                "clamped": True
            }
        }
        logging.warning(
            "MC_CLAMP: suggested=%s, has_dx=%s → clamped to %s",
            suggested_tier, has_dx, final_tier
        )
        
        # Set UI flag for interim advisory display
        st.session_state["_show_mc_interim_advice"] = True
        
        # Ensure likely_mc_no_dx flag is present for downstream logic
        outcome_ids = _get_outcome_flags()
        if not (outcome_ids & _MC_NO_DX_FLAG_IDS):
            logging.info("MC_CLAMP: adding likely_mc_no_dx flag")
            # Add flag to outcomes if not already present
            outcomes = st.session_state.get("gcp_care_recommendation", {}).get("_outcomes", {})
            if "flags" not in outcomes:
                outcomes["flags"] = []
            outcomes["flags"].append({"id": "likely_mc_no_dx", "severity": "high"})
    else:
        final_tier = suggested_tier
        meta = {}
        # Only clear interim flag if it wasn't already set by cognitive gate
        # (cognitive gate may have blocked MC early, so tier is already AL)
        if not st.session_state.get("_show_mc_interim_advice", False):
            st.session_state["_show_mc_interim_advice"] = False
        logging.info(
            "MC_CLAMP: suggested=%s, has_dx=%s → approved (no clamp)",
            suggested_tier, has_dx
        )
    
    return final_tier, meta


def render_mc_eligibility_banner(name: str | None = None) -> None:
    """
    Render a friendly eligibility note (amber banner).
    Scoped via class 'mc-eligibility-banner' to avoid global effects.
    Guarded to prevent duplicate renders during reruns.
    """
    # Guard against duplicate renders
    if st.session_state.get("_mc_banner_rendered", False):
        return
    
    person = name or st.session_state.get("person_name") or st.session_state.get("person_a_name") or "your loved one"
    st.markdown(
        f"""
<div class="mc-eligibility-banner" role="note" aria-label="Memory care eligibility note">
  <div class="mc-eligibility-icon">🛈</div>
  <div class="mc-eligibility-content">
    <p><strong>Note on eligibility for Memory Care</strong></p>
    <p>Based on {person}'s cognitive symptoms and daily needs, <strong>Memory Care may be appropriate</strong>.
    However, many communities require a <strong>formal dementia/Alzheimer's diagnosis</strong> before admission.
    If you don't have a diagnosis yet, <strong>Assisted Living</strong> can still provide daily support and safety
    while you speak with a physician about next steps.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_mc_banner_rendered"] = True
    logging.info("MC_ELIG: banner rendered and guard set")


# ==============================================================================
# GCP DECISION PIPELINE
# ==============================================================================

def publish_gcp_summary_bindings(
    state,
    final_tier: str,
    allowed_tiers: list[str] | None = None,
    flags: list[dict] | list[str] | None = None,
    rankings: list[tuple] | None = None,
    rationale: list[str] | None = None,
    confidence: float | None = None,
    advisory_meta: dict | None = None,
):
    """
    Publish the final decision to *all* fields that Summary or legacy code may read.
    This prevents 'blank until refresh' by making the data available immediately.
    
    Writes to:
    - gcp.{published_tier, allowed_tiers, flags, rankings, rationale, confidence, advisory_meta, summary_ready}
    - gcp.final_tier (nested)
    - gcp.final_tier (dotted key for legacy)
    - gcp_care_recommendation._outcomes (legacy structure)
    
    Args:
        state: Streamlit session state
        final_tier: Final adjudicated care tier
        allowed_tiers: List of tiers user can select
        flags: Risk/eligibility flags
        rankings: Tier rankings if available
        rationale: Tier rationale if available
        confidence: Confidence score if available
        advisory_meta: Advisory metadata (e.g., MC clamp info)
    """
    g = state.setdefault("gcp", {})
    g["published_tier"]  = final_tier
    g["allowed_tiers"]   = allowed_tiers or []
    g["flags"]           = flags or []
    g["rankings"]        = rankings or []
    g["rationale"]       = rationale or []
    g["confidence"]      = confidence
    g["advisory_meta"]   = advisory_meta or {}
    g["summary_ready"]   = True

    # Legacy "final" fields various parts still read
    g["final_tier"] = final_tier                 # nested
    state["gcp.final_tier"] = final_tier         # dotted legacy key (seen in older code)

    # Back-fill legacy outcomes object some Summary code uses
    legacy = state.setdefault("gcp_care_recommendation", {})
    legacy["_outcomes"] = {
        "tier": final_tier,
        "tier_rankings": rankings or [],
        "confidence": confidence,
        "flags": flags or [],
        "allowed_tiers": allowed_tiers or [],
        "rationale": rationale or [],
    }
    
    print(f"[GCP_PUBLISH] Published tier={final_tier} to all summary bindings (gcp.published_tier, gcp.final_tier, gcp.final_tier, _outcomes)")


def run_gcp_decision_pipeline(state) -> tuple[str, dict[str, Any]]:
    """
    Centralized GCP decision pipeline - runs once at Daily Living Continue.
    
    1) Collect all step inputs
    2) Compute deterministic tier
    3) Ask LLM mediator (if enabled)
    4) Adjudicate+publish into state['gcp'] and set summary_ready
    5) Set move_required gating flag
    6) Return (final_tier, meta)
    
    Args:
        state: Streamlit session state
    
    Returns:
        tuple: (final_tier, advisory_meta)
    """
    from core.perf import perf
    
    with perf("gcp.pipeline"):
        print("[GCP_PIPELINE] Starting centralized decision pipeline")
        
        # 1) Collect all GCP inputs from previous steps
        gcp = state.setdefault("gcp", {})
        module_state = state.get("gcp_care_recommendation", {})
        
        # 2) Compute deterministic tier using existing derive_outcome
        from products.gcp_v4.modules.care_recommendation.logic import derive_outcome
        from products.gcp_v4.modules.care_recommendation.flags import build_flags
        
        outcome = derive_outcome(module_state)
        det_tier = outcome.get("tier") if isinstance(outcome, dict) else getattr(outcome, "tier", "in_home")
        flags = build_flags(module_state)
        
        print(f"[GCP_PIPELINE] Deterministic tier: {det_tier}")
        
        # 3) Get LLM tier if enabled (derive_outcome already computed it)
        llm_tier = outcome.get("llm_tier") if isinstance(outcome, dict) else getattr(outcome, "llm_tier", None)
        allowed_tiers = outcome.get("allowed_tiers") if isinstance(outcome, dict) else getattr(outcome, "allowed_tiers", set())
        tier_rankings = outcome.get("tier_rankings", []) if isinstance(outcome, dict) else []
        rationale = outcome.get("rationale", []) if isinstance(outcome, dict) else []
        confidence = outcome.get("confidence", 0.0) if isinstance(outcome, dict) else 0.0
        
        # 4) Adjudicate final tier (handles MC clamp logic)
        final_tier, meta = adjudicate_final_tier(det_tier, llm_tier)
        
        print(f"[GCP_PIPELINE] Final tier after adjudication: {final_tier}")
        
        # 5) Publish to ALL summary bindings (new + legacy)
        publish_gcp_summary_bindings(
            state,
            final_tier=final_tier,
            allowed_tiers=list(allowed_tiers) if allowed_tiers else [],
            flags=flags,
            rankings=tier_rankings,
            rationale=rationale,
            confidence=confidence,
            advisory_meta=meta or {},
        )
        
        # 6) Set additional GCP state fields
        gcp["recommended_tier"] = det_tier  # Keep original for reference
        gcp["deterministic_tier"] = det_tier  # Alias for clarity
        
        # 7) Set move preference gating
        move_required = final_tier not in ("in_home", "in_home_care", "independent")
        gcp["move_required"] = move_required
        
        # 8) Set navigation override for next step
        state["gcp_next_step_override"] = "move_preferences" if move_required else "results"
        
        print(f"[GCP_PIPELINE] Pipeline complete: tier={final_tier} move={move_required} next={state['gcp_next_step_override']}")
        print(f"[GCP_PIPELINE] Published to gcp.published_tier and back-filled legacy _outcomes")
        
        # 9) Trigger LLM summary generation (ensure_summary_ready)
        from products.gcp_v4.modules.care_recommendation.logic import ensure_summary_ready
        ensure_summary_ready(module_state, flags, final_tier)
        
        return final_tier, meta


def run_module(config: ModuleConfig) -> dict[str, Any]:
    """Run a module flow defined by ModuleConfig. Returns updated module state."""
    state_key = config.state_key

    # Check if we need to restore state from tile_state (session expired but tile persists)
    tiles = st.session_state.setdefault("tiles", {})
    tile_state = tiles.setdefault(config.product, {})

    # If state doesn't exist but tile has saved_state, restore it
    if state_key not in st.session_state and "saved_state" in tile_state:
        st.session_state[state_key] = tile_state["saved_state"].copy()

    st.session_state.setdefault(state_key, {})
    state = st.session_state[state_key]

    total_steps = len(config.steps)

    # Validate module configuration
    if total_steps == 0:
        st.error("⚠️ Module configuration error: No steps defined.")
        st.stop()

    # Check tile state for last saved step (resume functionality)
    tiles = st.session_state.setdefault("tiles", {})
    tile_state = tiles.setdefault(config.product, {})
    saved_step = tile_state.get("last_step")

    # Resume from saved step if exists, otherwise start at 0
    if saved_step is not None and saved_step >= 0:
        step_index = saved_step
    else:
        step_index = int(st.session_state.get(f"{state_key}._step", 0))

    # Clamp to valid range with additional safety check
    step_index = max(0, min(step_index, total_steps - 1))

    # Final bounds validation before array access
    if step_index < 0 or step_index >= total_steps:
        st.error(
            f"⚠️ Invalid step index: {step_index} (total steps: {total_steps}). Resetting to step 0."
        )
        step_index = 0
        st.session_state[f"{state_key}._step"] = 0

    # Store step index for internal navigation
    st.session_state[f"{state_key}._step"] = step_index
    
    # Clear MC banner cache when starting fresh (step 0) to prevent stale state
    if step_index == 0:
        st.session_state.pop("_mc_advice_cached", None)
        st.session_state.pop("_mc_banner_rendered", None)
        st.session_state.pop("_interim_al_cached", None)
        st.session_state.pop("_show_mc_interim_advice", None)

    step = config.steps[step_index]

    # Substitute {{name}} template in title and apply content contract interpolation
    title = _substitute_title(step.title, state)
    
    # Also apply content contract interpolation to subtitle
    subtitle = _substitute_title(step.subtitle or "", state) if step.subtitle else None

    # Calculate progress BEFORE rendering header
    progress = _update_progress(config, state, step, step_index)

    # Calculate progress-eligible steps (exclude intro/results pages)
    progress_steps = [s for s in config.steps if s.show_progress]
    progress_total = len(progress_steps)

    # Check if current step should show progress indicators
    show_step_dots = step.show_progress

    # ========================================================================
    # CENTERED MODULE CONTAINER - Wrap all content (Hub-like aesthetic)
    # ========================================================================
    st.markdown('<div class="sn-app module-container">', unsafe_allow_html=True)

    # ========================================================================
    # NAVI PERSISTENT GUIDE BAR
    # Inject Navi's contextual guidance at the top of every module
    # ========================================================================
    # DISABLED: Now using main Navi panel (blue box) which shows step progress
    # The purple box was duplicate - main Navi panel at page top handles all guidance
    # _render_navi_guide_bar(config, step, state, step_index, progress_total)

    # Render header with actual progress
    # Note: Progress bar also disabled since Navi panel shows progress (X/Y steps)
    _render_header(
        step_index,
        total_steps,
        title,
        subtitle,
        progress,
        progress_total,
        show_step_dots,
        step.id == config.steps[0].id,
        config,
    )

    # Render content array (for info-type pages)
    # Check for custom intro rendering first (GCP v4 special case)
    custom_rendered = False
    print(f"[ENGINE_DEBUG] About to check custom intro: product={config.product}, step_id={step.id}")
    if config.product == "gcp_v4" and step.id == "intro":
        print("[ENGINE_DEBUG] Matched GCP v4 intro, calling custom renderer")
        try:
            from products.gcp_v4.modules.care_recommendation.intro import render_custom_intro_if_needed
            custom_rendered = render_custom_intro_if_needed()
            print(f"[ENGINE_DEBUG] Custom renderer returned: {custom_rendered}")
        except Exception as e:
            # Fall back to default rendering if custom intro fails
            print(f"[GCP_INTRO] Custom intro failed: {e}")
            import traceback
            traceback.print_exc()
            custom_rendered = False
    else:
        print(f"[ENGINE_DEBUG] Not GCP intro, skipping custom renderer")
    
    # Use default content rendering if no custom renderer or it failed
    if step.content and not custom_rendered:
        print(f"[ENGINE_DEBUG] Rendering default content")
        _render_content(step.content)
    else:
        print(f"[ENGINE_DEBUG] Skipping content render (has_content={bool(step.content)}, custom_rendered={custom_rendered})")


    new_values = _render_fields(step, state)
    if new_values:
        state.update(new_values)
        # Save state to tile_state for persistence across sessions
        tiles = st.session_state.setdefault("tiles", {})
        tile_state = tiles.setdefault(config.product, {})
        tile_state["saved_state"] = state.copy()

    is_results = config.results_step_id and step.id == config.results_step_id

    if is_results:
        _ensure_outcomes(config, state)

        # Check if product wants to skip default results rendering
        if not getattr(config, "skip_default_results", False):
            _render_results_view(state, config)

        # Close module container
        st.markdown("</div>", unsafe_allow_html=True)
        return state

    _render_summary(step, state)

    required_fields = _required_fields(step, state)
    missing = _required_missing(required_fields, state)

    # Render actions - get save_exit button state
    # Detect if this is the intro page (first step) - nothing to save yet
    is_intro_page = step.id == config.steps[0].id
    next_clicked, skip_clicked, save_exit_clicked, back_clicked, back_to_hub_clicked = actions(
        step.next_label,
        step.skip_label,
        is_intro=is_intro_page,
        show_back=(not is_intro_page and step_index > 0),
        step_index=step_index,
        config=config,
    )

    # Handle Back button
    if back_clicked:
        prev_index = max(0, step_index - 1)
        st.session_state[f"{config.state_key}._step"] = prev_index

        # Update tile state for resume functionality
        tiles = st.session_state.setdefault("tiles", {})
        tile_state = tiles.setdefault(config.product, {})
        tile_state["last_step"] = prev_index

        safe_rerun()

    # Handle Back to Hub
    if back_to_hub_clicked:
        _handle_save_exit(config, state, step_index, total_steps, reason="back_to_hub")
        # Close module container
        st.markdown("</div>", unsafe_allow_html=True)
        return state

    # Save & Continue Later - REMOVED (button no longer rendered)
    # Progress is automatically saved to tile_state and persists across sessions

    if next_clicked and missing:
        st.warning(f"Please complete the required fields: {', '.join(missing)}")
    allow_next = next_clicked and not missing
    if allow_next:
        _apply_step_effects(step, state)
    _handle_nav(config, step, step_index, total_steps, allow_next, skip_clicked)

    if config.results_step_id and step.id == config.results_step_id:
        _render_results_view(state, config)
        # Close module container
        st.markdown("</div>", unsafe_allow_html=True)
        return state

    # Close module container
    st.markdown("</div>", unsafe_allow_html=True)
    return state


def _render_header(
    step_index: int,
    total: int,
    title: str,
    subtitle: str | None,
    progress: float,
    progress_total: int,
    show_step_dots: bool = True,
    is_intro: bool = False,
    config: ModuleConfig | None = None,
) -> None:
    """Render module header without progress bar (Navi panel handles progress)."""
    from html import escape as _escape

    # Progress bar removed - Navi panel at top now shows step progress (X/Y)

    subtitle_html = ""
    if subtitle:
        # Convert newlines to <br> tags and wrap paragraphs
        lines = subtitle.split("\n")
        formatted_lines = []
        first_line = True
        for line in lines:
            stripped = line.strip()
            if stripped:
                # First line gets emphasized styling (h3)
                if first_line and stripped.endswith(":"):
                    formatted_lines.append(
                        f"<h3 class='h3' style='margin-top: 1.5rem; margin-bottom: 1rem;'>{_escape(stripped)}</h3>"
                    )
                    first_line = False
                else:
                    # Escape the line but preserve emoji and special chars
                    formatted_lines.append(f"<p>{_escape(stripped)}</p>")
            elif formatted_lines:  # Add spacing between paragraphs
                formatted_lines.append("<br/>")
        subtitle_html = f"<div class='lead'>{''.join(formatted_lines)}</div>"

    # Header without back button (back button moved to actions section)
    st.markdown(
        f"""
        <div class="mod-head">
          <div class="mod-head-row">
            <h2 class="h2">{_escape(title)}</h2>
          </div>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _substitute_title(title: str, state: Mapping[str, Any]) -> str:
    """Apply content contract interpolation to title and subtitle text."""
    # Import here to avoid circular dependencies
    from core.content_contract import build_token_context, interpolate
    
    # DEBUG: Log what's happening
    print(f"[SUBSTITUTE_TITLE_DEBUG] Input title: '{title}'")
    print(f"[SUBSTITUTE_TITLE_DEBUG] Session keys: {list(st.session_state.keys())}")
    
    # Build token context from current session state
    try:
        context = build_token_context(st.session_state)
        print(f"[SUBSTITUTE_TITLE_DEBUG] Context NAME: '{context.name}', NAME_POS: '{context.name_possessive}'")
        # Apply content contract interpolation
        interpolated = interpolate(title, context)
        print(f"[SUBSTITUTE_TITLE_DEBUG] Interpolated result: '{interpolated}'")
        return interpolated
    except Exception as e:
        print(f"[SUBSTITUTE_TITLE_DEBUG] Exception: {e}")
        # Fallback: try old {{name}} substitution for backward compatibility
        if "{{name}}" not in title:
            return title

        # Try to get name from module state first
        name = state.get("recipient_name") or state.get("person_name")

        # Fall back to session state
        if not name:
            profile = st.session_state.get("profile", {})
            name = profile.get("recipient_name") or profile.get("person_name")

        # Default to generic text
        if not name:
            name = "This Person"

        return title.replace("{{name}}", name)


def _render_content(content: list[str]) -> None:
    """Render content array for info-type pages.

    Args:
        content: List of content lines with markdown support.
                 Empty strings create spacing.
    """
    from core.text import personalize_text
    import re
    import json
    
    for line in content:
        if line.strip():
            # Apply personalization to non-empty lines before rendering
            personalized_line = personalize_text(line)
            
            # Safety: assert no unresolved tokens remain
            if re.search(r"\{NAME(_POS)?\}", personalized_line):
                raise AssertionError(f"Unresolved name token found in content: '{personalized_line}'")
            
            st.markdown(personalized_line)
        else:
            # Empty lines add spacing
            st.markdown("<br/>", unsafe_allow_html=True)


def _render_fields(step: StepDef, state: Mapping[str, Any]) -> dict[str, Any]:
    new_values: dict[str, Any] = {}
    for field in step.fields:
        if not _is_visible(field, state):
            continue
        renderer = components.RENDERERS.get(field.type)
        if not renderer:
            continue
        store_key = field.write_key or field.key
        current_value = state.get(store_key, field.default)
        value = renderer(field, current_value)
        new_values[store_key] = value
    return new_values


def _update_progress(
    config: ModuleConfig, state: dict[str, Any], step: StepDef, step_index: int
) -> float:
    # Only count steps that have show_progress=True (exclude intro)
    progress_steps = [s for s in config.steps if s.show_progress]
    total = len(progress_steps) or 1

    # Check if we're on results page FIRST - that's always 100%
    if config.results_step_id and step.id == config.results_step_id:
        progress = 1.0
    else:
        # Find the current step's index among progress-eligible steps
        try:
            progress_index = next(i for i, s in enumerate(progress_steps) if s.id == step.id)
        except StopIteration:
            # Current step doesn't count toward progress (like intro page)
            progress = 0.0
        else:
            # Calculate fractional progress within current step
            required = _required_fields(step, state)
            if required:
                completed = sum(1 for f in required if _has_value(state.get(f.write_key or f.key)))
                fraction = completed / len(required)
            else:
                fraction = 1.0

            # Progress is (completed steps + fraction of current) / total
            progress = (progress_index + fraction) / total

    progress_pct = round(progress * 100, 1)
    state["progress"] = progress_pct

    if progress >= 1.0:
        state["status"] = "done"
    elif progress > 0:
        state["status"] = "doing"
    else:
        state["status"] = "new"

    tiles = st.session_state.setdefault("tiles", {})
    tile_state = tiles.setdefault(config.product, {})
    tile_state["progress"] = progress_pct
    # NOTE: Do NOT update last_step here - it should only update on navigation
    # to avoid overwriting the step before user clicks Continue

    if progress >= 1.0:
        tile_state["status"] = "done"
    elif progress > 0:
        tile_state["status"] = "doing"
    else:
        tile_state["status"] = "new"

    _emit(
        "product.progress",
        {
            "product": config.product,
            "state_key": config.state_key,
            "progress": progress_pct,
        },
    )

    return progress


def _render_summary(step: StepDef, state: Mapping[str, Any]) -> None:
    """Render developer info in sidebar for debugging."""
    if step.show_bottom_bar and step.summary_keys:
        field_map = {f.write_key or f.key: f for f in step.fields}
        items = {
            key: _format_summary_value(state.get(key), field_map.get(key))
            for key in step.summary_keys
            if key in state
        }
        # Render in sidebar instead of bottom of main content
        with st.sidebar:
            st.markdown("### 🔧 Developer Info")
            for key, value in items.items():
                st.markdown(f"**{key}**")
                st.code(value, language="text")


def _handle_nav(
    config: ModuleConfig,
    step: StepDef,
    step_index: int,
    total_steps: int,
    next_clicked: bool,
    skip_clicked: bool,
) -> None:
    if not (next_clicked or skip_clicked):
        return

    # CRITICAL: Trigger GCP decision pipeline when leaving Daily Living step
    if config.product == "gcp_v4" and step.id == "daily_living" and next_clicked:
        print("[GCP_PIPELINE_TRIGGER] Daily Living complete - running decision pipeline")
        try:
            final_tier, meta = run_gcp_decision_pipeline(st.session_state)
            print(f"[GCP_PIPELINE_TRIGGER] Pipeline complete: tier={final_tier}")
            
            # Set canonical summary_ready flag (gate contract for CCR tile + other features)
            g = st.session_state.setdefault("gcp", {})
            g["summary_ready"] = True            # canonical
            st.session_state["summary_ready"] = True  # backfill legacy readers (optional)
            print(f"[GCP_PIPELINE_TRIGGER] Set summary_ready=True (canonical gate)")
            
            # Check for next step override (move_preferences or results)
            if "gcp_next_step_override" in st.session_state:
                next_step = st.session_state.pop("gcp_next_step_override")
                # Find the index of the target step
                for idx, s in enumerate(config.steps):
                    if s.id == next_step:
                        st.session_state[f"{config.state_key}._step"] = idx
                        
                        # Update tile state
                        tiles = st.session_state.setdefault("tiles", {})
                        tile_state = tiles.setdefault(config.product, {})
                        tile_state["last_step"] = idx
                        
                        print(f"[GCP_PIPELINE_TRIGGER] Routing to {next_step} (index {idx})")
                        _rerun_app()
                        return
        except Exception as e:
            print(f"[GCP_PIPELINE_ERROR] {e}")
            # Continue with normal flow on error

    next_index = min(step_index + 1, total_steps - 1)
    st.session_state[f"{config.state_key}._step"] = next_index

    # Update tile state with new step for resume functionality
    tiles = st.session_state.setdefault("tiles", {})
    tile_state = tiles.setdefault(config.product, {})
    tile_state["last_step"] = next_index

    if next_clicked and config.results_step_id and step.id == config.results_step_id:
        _emit(
            "product.completed",
            {"product": config.product, "state_key": config.state_key},
        )

    _rerun_app()


def _hub_route_for_product(product_key: str) -> str:
    """Resolve hub route key for a given product key."""
    fallback_map = {
        "gcp_v4": "gcp",
        "cost_v2": "cost_planner",
        "pfma_v2": "pfma",
    }
    candidates = [product_key]
    mapped = fallback_map.get(product_key)
    if mapped:
        candidates.append(mapped)
    if "_" in product_key:
        base_key = product_key.split("_", 1)[0]
        candidates.append(base_key)
    for key in candidates:
        if not key:
            continue
        info = PRODUCTS.get(key)
        if not info:
            continue
        hub_id = info.get("hub") or "concierge"
        return hub_id if hub_id.startswith("hub_") else f"hub_{hub_id}"
    return "hub_lobby"


def _handle_save_exit(
    config: ModuleConfig,
    state: dict[str, Any],
    step_index: int,
    total_steps: int,
    reason: str = "save_exit",
) -> None:
    """Handle Save & Continue Later button - saves progress and returns to hub."""
    # Progress is already auto-saved in state
    progress_pct = state.get("progress", 0)

    # Calculate readable step info
    progress_steps = [s for s in config.steps if s.show_progress]
    completed_progress_steps = min(step_index, len(progress_steps))

    # Store exit info for hub message
    state["last_exit_step"] = step_index
    state["last_exit_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["last_exit_reason"] = reason

    # Update tile state with current step for resume functionality
    tiles = st.session_state.setdefault("tiles", {})
    tile_state = tiles.setdefault(config.product, {})
    tile_state["last_step"] = step_index

    hub_route = _hub_route_for_product(config.product)

    # Set a session flag to show completion message
    st.session_state["_show_save_message"] = {
        "product": config.product,
        "progress": progress_pct,
        "step": completed_progress_steps + 1,
        "total": len(progress_steps),
        "reason": reason,
        "hub_route": hub_route,
    }

    event_name = "product.saved_exit" if reason == "save_exit" else "product.back_to_hub"
    payload = {
        "product": config.product,
        "state_key": config.state_key,
        "progress": progress_pct,
        "step_index": step_index,
        "hub_route": hub_route,
        "reason": reason,
    }
    _emit(event_name, payload)

    # Navigate to lobby using canonical helper
    from core.nav import go_to_lobby
    go_to_lobby()


def _ensure_outcomes(config: ModuleConfig, answers: dict[str, Any]) -> None:
    state_key = config.state_key
    outcome_key = f"{state_key}._outcomes"

    if st.session_state.get(outcome_key):
        return

    context = _compute_context(config)
    outcome = OutcomeContract()
    if config.outcomes_compute:
        fn = _resolve_callable(config.outcomes_compute)

        # Single analysis spinner with controlled mounting/unmounting
        analysis_placeholder = st.empty()

        # Set loading flags for deterministic state management
        st.session_state["llm_loading"] = True
        st.session_state["summary_ready"] = False

        # Show analysis spinner
        with analysis_placeholder.container():
            st.markdown("""
            <div class="assessment-analysis-spinner">
                <div class="analysis-content">
                    <span class="analysis-icon">💬</span>
                    <span class="analysis-text">Analyzing your assessment and preparing recommendations...</span>
                    <div class="analysis-progress">
                        <div class="progress-bar"></div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Inject CSS once (outside conditional to avoid flicker)
        st.markdown("""
        <style>
        .assessment-analysis-spinner {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 28px 24px;
            margin: 24px 0;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.05), rgba(59, 130, 246, 0.05));
            border: 2px solid rgba(139, 92, 246, 0.18);
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(139, 92, 246, 0.12);
            animation: analysis-pulse 2.5s ease-in-out infinite;
            max-width: 650px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .analysis-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
            text-align: center;
        }
        
        .analysis-content > div:first-child {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .analysis-icon {
            font-size: 1.5rem;
            animation: analysis-float 2s ease-in-out infinite;
        }
        
        .analysis-text {
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--brand-700);
            line-height: 1.4;
        }
        
        .analysis-progress {
            width: 200px;
            height: 4px;
            background: rgba(139, 92, 246, 0.2);
            border-radius: 2px;
            overflow: hidden;
            position: relative;
        }
        
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #8b5cf6, #3b82f6);
            border-radius: 2px;
            animation: analysis-progress 2s ease-in-out infinite;
        }
        
        @keyframes analysis-pulse {
            0%, 100% { 
                border-color: rgba(139, 92, 246, 0.18);
                box-shadow: 0 8px 24px rgba(139, 92, 246, 0.12);
            }
            50% { 
                border-color: rgba(139, 92, 246, 0.28);
                box-shadow: 0 12px 32px rgba(139, 92, 246, 0.18);
            }
        }
        
        @keyframes analysis-float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-4px); }
        }
        
        @keyframes analysis-progress {
            0% { width: 0%; transform: translateX(-100%); }
            50% { width: 100%; transform: translateX(0%); }
            100% { width: 100%; transform: translateX(100%); }
        }
        </style>
        """, unsafe_allow_html=True)

        try:
            result = fn(answers=answers, context=context)
            if isinstance(result, OutcomeContract):
                outcome = result
            elif isinstance(result, dict):
                # ========================================
                # ADJUDICATION CLAMP: Apply safety gates before publishing
                # ========================================
                base_tier = result.get("tier", "")
                llm_tier = result.get("llm_tier")  # If LLM mode is enabled
                
                # Apply adjudication clamp (non-negotiable safety gate)
                final_tier, advisory_meta = adjudicate_final_tier(base_tier, llm_tier)
                
                # Update tier with adjudicated value
                if final_tier != base_tier:
                    logging.warning(
                        "MC_ADJUDICATION: tier changed %s → %s (clamped=%s)",
                        base_tier, final_tier, advisory_meta.get("advisory", {}).get("clamped", False)
                    )
                    result["tier"] = final_tier
                    result["tier_original"] = base_tier  # Preserve original for analytics
                    result["advisory"] = advisory_meta.get("advisory", {})
                
                # ========================================
                # PUBLISH FINAL TIER: Persist to canonical session keys
                # ========================================
                # Ensure the UI reads the POST-ADJUDICATION tier, not pre-clamp
                g = st.session_state.setdefault("gcp", {})
                g["published_tier"] = final_tier
                g["recommended_tier"] = final_tier  # Mirror for backward compatibility
                if advisory_meta:
                    g["advisory_meta"] = advisory_meta
                
                logging.info(
                    "GCP_PUBLISH: published_tier=%s (original=%s, advisory=%s)",
                    final_tier, 
                    result.get("tier_original", final_tier),
                    bool(advisory_meta)
                )
                
                # Don't wrap in OutcomeContract - store dict directly
                # This allows product-specific schemas (e.g., GCP's tier/tier_score)
                st.session_state[outcome_key] = result

                # Still handle legacy handoff for backward compatibility
                handoff = st.session_state.setdefault("handoff", {})
                handoff[state_key] = result

                _emit(
                    "module.outcomes.ready",
                    {
                        "state_key": state_key,
                        "outcome": str(result.get("tier") or result.get("recommendation", "")),
                    },
                )

                # Clear loading state and spinner after successful computation
                st.session_state["llm_loading"] = False
                st.session_state["summary_ready"] = True
                analysis_placeholder.empty()

                return  # Early return - we're done
        except Exception as e:
            import traceback

            st.error(f"❌ Error computing outcomes: {type(e).__name__}: {str(e)}")
            st.text(traceback.format_exc())
            outcome = OutcomeContract()

            # Clear loading state even on error
            st.session_state["llm_loading"] = False
            st.session_state["summary_ready"] = False
            analysis_placeholder.empty()

    audit = dict(outcome.audit)
    audit.update(
        {
            "version": config.version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    outcome.audit = audit

    st.session_state[outcome_key] = asdict(outcome)

    handoff = st.session_state.setdefault("handoff", {})
    handoff[state_key] = {
        "recommendation": outcome.recommendation,
        "flags": dict(outcome.flags),
        "tags": list(outcome.tags),
        "domain_scores": dict(outcome.domain_scores),
    }

    if outcome.recommendation:
        answers["care_tier"] = outcome.recommendation
        answers["status"] = "done"
        answers["progress"] = 100.0

        person_name = context.get("person_a_name", "This person")
        reason = (
            f"{person_name}'s care plan suggests {outcome.recommendation.replace('_', ' ').title()}"
        )
        nudges: list[str] = []
        if outcome.flags.get("emotional_followup"):
            nudges.append("Emotional wellbeing may need an advisor check-in.")
        if outcome.flags.get("fall_risk"):
            nudges.append("Fall prevention should be part of your next step.")

        concierge_panel = {
            "reason": reason,
            "next_step": "cost",
        }
        if nudges:
            concierge_panel["nudges"] = nudges

        st.session_state.setdefault("mcip", {})["concierge"] = concierge_panel

    _emit(
        "module.outcomes.ready",
        {"state_key": state_key, "recommendation": outcome.recommendation},
    )


def _resolve_callable(path: str):
    module_path, attr = path.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _compute_context(config: ModuleConfig) -> dict[str, Any]:
    state = st.session_state.get(config.state_key, {})
    profile = st.session_state.get("profile", {})
    auth = st.session_state.get("auth", {})
    return {
        "config": config,  # Include config for scoring functions
        "product": config.product,
        "version": config.version,
        "person_a_name": state.get("recipient_name") or "this person",
        "geo": profile.get("state"),
        "auth": bool(auth.get("is_authenticated")),
    }


def _emit(event: str, payload: dict[str, Any] | None = None) -> None:
    try:
        log_event(event, payload or {})
    except Exception:
        pass


def _is_visible(field: FieldDef, state: Mapping[str, Any]) -> bool:
    cond = field.visible_if
    if not cond:
        return True
    key = cond.get("key")
    if key is None or key not in state:
        return False
    if "eq" in cond:
        return state.get(key) == cond["eq"]
    if "in" in cond:
        values = cond.get("in")
        return state.get(key) in values if isinstance(values, (list, tuple, set)) else False
    return True


def _format_summary_value(value: Any, field: FieldDef | None = None) -> str:
    if field:
        return _display_value(field, value)
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}" if abs(value) >= 1000 else f"{value}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if str(v))
    return str(value)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _required_fields(step: StepDef, state: Mapping[str, Any]) -> list[FieldDef]:
    fields: list[FieldDef] = []
    for field in step.fields:
        if not field.required:
            continue
        if not _is_visible(field, state):
            continue
        store_key = field.write_key or field.key
        if field.ask_if_missing and _has_value(state.get(store_key)):
            continue
        fields.append(field)
    return fields


def _required_missing(required_fields: Sequence[FieldDef], state: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        store_key = field.write_key or field.key
        value = state.get(store_key)
        if not _has_value(value):
            missing.append(field.label)
    return missing


def _apply_step_effects(step: StepDef, state: dict[str, Any]) -> None:
    if not step.fields:
        return
    flags = state.setdefault("flags", {})
    for field in step.fields:
        if not field.effects:
            continue
        store_key = field.write_key or field.key
        value = state.get(store_key)
        _apply_effects(field, value, flags)


def _apply_effects(field: FieldDef, value: Any, flags: dict[str, Any]) -> None:
    if not field.effects:
        return
    values: list[str] = []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = [str(v) for v in value]
    elif value is not None:
        values = [str(value)]
    for effect in field.effects:
        triggers = effect.get("when_value_in", [])
        if not triggers:
            continue
        if _effect_triggered(values, triggers):
            flag_key = effect.get("set_flag")
            if flag_key:
                flags[flag_key] = True
                message = effect.get("flag_message")
                if message:
                    flags[f"{flag_key}_message"] = message


def _display_value(field: FieldDef, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        if field.options:
            mapping = {
                str(opt.get("value", opt.get("label"))): str(opt.get("label", opt.get("value")))
                for opt in (field.options or [])
            }
            return ", ".join(mapping.get(str(v), str(v)) for v in value if str(v))
        return ", ".join(str(v) for v in value if str(v))
    if field.options:
        lookup = {
            str(opt.get("value", opt.get("label"))): str(opt.get("label", opt.get("value")))
            for opt in (field.options or [])
        }
        return lookup.get(str(value), str(value))
    return str(value)


def _find_field(config: ModuleConfig, key: str) -> FieldDef | None:
    for step in config.steps:
        for field in step.fields:
            if (field.write_key or field.key) == key:
                return field
    return None


def _get_recommendation(mod: dict[str, Any], config: ModuleConfig) -> str | None:
    """Get recommendation text from outcomes or module state."""
    # Try to get from outcomes first (preferred)
    outcome_key = f"{config.state_key}._outcomes"
    outcomes = st.session_state.get(outcome_key, {})

    # GCP v4 uses "tier" field (new system)
    tier = outcomes.get("tier")
    if tier:
        # Special handling for independent tier - more helpful message
        if tier.lower() == "independent":
            return "Good for now! If things change, consider In-Home Care."

        mapping = {
            "in_home": "In-Home Care with Support",
            "assisted_living": "Assisted Living",
            "memory_care": "Memory Care",
        }
        pretty = mapping.get(tier.lower(), tier.replace("_", " ").title())
        return f"Based on your answers, we recommend {pretty}."

    # Legacy modules use "recommendation" field
    recommendation = outcomes.get("recommendation")
    if recommendation:
        # If the recommendation is already properly formatted (contains capitals or special chars),
        # use it as-is (this is the case for new logic_v3 output)
        if (
            any(c.isupper() for c in recommendation)
            or "/" in recommendation
            or "-" in recommendation
        ):
            return f"Based on your answers, we recommend {recommendation}."

        # Otherwise, normalize the recommendation key for backward compatibility
        rec_key = recommendation.lower().replace(" ", "_").replace("/", "_").replace("-", "_")

        # CRITICAL: Map recommendation to display name - ONLY 5 allowed tiers
        mapping = {
            "no_care_needed": "No Care Needed",
            "in_home": "In-Home Care",
            "in_home_care": "In-Home Care",
            "assisted_living": "Assisted Living",
            "memory_care": "Memory Care",
            "memory_care_high_acuity": "Memory Care (High Acuity)",
        }

        pretty = mapping.get(rec_key)
        if not pretty:
            # Fallback: title case the recommendation
            pretty = recommendation.replace("_", " ").replace("/", " / ").title()

        return f"Based on your answers, we recommend {pretty}."

    # Fallback: try module state
    text = str(mod.get("recommendation_text", "")).strip()
    if text:
        if text.lower().startswith("based on your answers"):
            return text
        return f"Based on your answers, we recommend {text}."

    tier = str(mod.get("care_tier_label") or mod.get("care_tier") or "").strip()
    if not tier:
        return None
    # CRITICAL: Map tier to display name - ONLY 5 allowed tiers
    mapping = {
        "no_care_needed": "No Care Needed",
        "in_home": "In-Home Care",
        "assisted_living": "Assisted Living",
        "memory_care": "Memory Care",
        "memory_care_high_acuity": "Memory Care (High Acuity)",
    }
    pretty = mapping.get(tier.lower(), tier.replace("_", " ").title())
    return f"Based on your answers, we recommend {pretty}."


def _render_confidence_improvement(
    outcomes: dict[str, Any], config: ModuleConfig, state: dict[str, Any]
) -> None:
    """Render confidence improvement guidance on results page.

    Redesigned as split cards showing progress and clarity with actionable guidance.

    Args:
        outcomes: Outcome data with confidence and scoring details
        config: Module configuration
        state: Module state with user answers
    """
    confidence = outcomes.get("confidence", 1.0)
    confidence_pct = int(confidence * 100)

    # Only show improvement guidance if confidence < 100%
    if confidence_pct >= 100:
        return

    # Get scoring details
    tier_score = outcomes.get("tier_score", 0)
    tier = outcomes.get("tier", "")

    # Calculate completeness
    answered_count = 0
    total_count = 0
    unanswered_questions = []

    for step in config.steps:
        if not step.fields:  # Skip intro/results pages
            continue
        for field in step.fields:
            if field.required:
                total_count += 1
                value = state.get(field.key)
                if value is not None and value != "" and value != []:
                    answered_count += 1
                else:
                    unanswered_questions.append(
                        {"label": field.label, "step_id": step.id, "step_title": step.title}
                    )

    completeness = answered_count / total_count if total_count > 0 else 1.0
    completeness_pct = int(completeness * 100)

    # Determine tier boundaries for clarity
    tier_thresholds = {
        "no_care_needed": (0, 8),
        "in_home": (9, 16),
        "assisted_living": (17, 24),
        "memory_care": (25, 39),
        "memory_care_high_acuity": (40, 100),
    }

    boundary_clarity = 100  # Default
    clarity_message = "Clear"
    if tier in tier_thresholds:
        min_score, max_score = tier_thresholds[tier]
        distance_from_min = tier_score - min_score
        distance_from_max = max_score - tier_score
        distance_from_boundary = min(distance_from_min, distance_from_max)
        boundary_clarity = min(int((distance_from_boundary / 3.0) * 100), 100)

        if boundary_clarity >= 80:
            clarity_message = "Strong — well within tier"
        elif boundary_clarity >= 50:
            clarity_message = "Moderate — some distance from boundary"
        else:
            clarity_message = "Near boundary — consider reviewing"

    st.markdown("### 💡 Improve Your Confidence")

    st.markdown(
        """
    <p style="font-size: 14px; color: #64748b; margin-bottom: 20px;">
        Your confidence score is based on how complete your answers are and how clear your tier placement is.
    </p>
    """,
        unsafe_allow_html=True,
    )

    # Split into two horizontal cards
    col1, col2 = st.columns(2)

    with col1:
        # Progress card
        completeness_color = (
            "#22c55e"
            if completeness_pct >= 90
            else "#f59e0b"
            if completeness_pct >= 70
            else "#ef4444"
        )

        st.markdown(
            f"""
        <div style="
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            height: 100%;
        ">
            <div style="font-size: 12px; color: #64748b; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 12px;">
                QUESTION COMPLETENESS
            </div>
            <div style="font-size: 32px; font-weight: 600; color: {completeness_color}; margin-bottom: 8px;">
                {completeness_pct}%
            </div>
            <div style="font-size: 13px; color: #64748b; margin-bottom: 12px;">
                {answered_count} of {total_count} questions answered
            </div>
            <div style="
                background: #f1f5f9;
                height: 8px;
                border-radius: 4px;
                overflow: hidden;
            ">
                <div style="
                    background: {completeness_color};
                    height: 100%;
                    width: {completeness_pct}%;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        # Clarity card
        clarity_color = (
            "#22c55e"
            if boundary_clarity >= 80
            else "#f59e0b"
            if boundary_clarity >= 50
            else "#ef4444"
        )

        st.markdown(
            f"""
        <div style="
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            height: 100%;
        ">
            <div style="font-size: 12px; color: #64748b; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 12px;">
                RECOMMENDATION CLARITY
            </div>
            <div style="font-size: 32px; font-weight: 600; color: {clarity_color}; margin-bottom: 8px;">
                {boundary_clarity}%
            </div>
            <div style="font-size: 13px; color: #64748b; margin-bottom: 12px;">
                {clarity_message}
            </div>
            <div style="
                background: #f1f5f9;
                height: 8px;
                border-radius: 4px;
                overflow: hidden;
            ">
                <div style="
                    background: {clarity_color};
                    height: 100%;
                    width: {boundary_clarity}%;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Guidance section below both cards
    if completeness_pct < 100 or boundary_clarity < 80:
        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        with st.expander("🔍 How to Improve Your Confidence", expanded=(completeness_pct < 90)):
            if completeness_pct < 100 and unanswered_questions:
                st.markdown("**📝 Complete Unanswered Questions**")
                st.markdown(
                    f"You have {len(unanswered_questions)} unanswered question(s). Answering them will improve your confidence score."
                )

                if len(unanswered_questions) <= 5:
                    for q in unanswered_questions:
                        st.markdown(f"- {q['label']}")

            if boundary_clarity < 80 and tier in tier_thresholds:
                st.markdown("**📊 Your Score is Near a Tier Boundary**")
                min_score, max_score = tier_thresholds[tier]
                st.markdown(f"""
                Your current score is **{tier_score} points**, which places you in the **{tier.replace("_", " ").title()}** tier (range: {min_score}-{max_score} points).
                
                You're close to a tier boundary, which means small changes in your answers could affect your recommendation. Consider reviewing your responses for accuracy.
                """)

            # Go back button
            st.markdown("<div style='margin: 16px 0;'></div>", unsafe_allow_html=True)
            if st.button("← Review Your Answers", type="secondary", use_container_width=True):
                # Go back to first question step
                for idx, step in enumerate(config.steps):
                    if step.fields and not step.id.startswith("intro"):
                        st.session_state[f"{config.state_key}._step"] = idx
                        _rerun_app()
                        break


def _render_results_view(mod: dict[str, Any], config: ModuleConfig) -> None:
    """Render results with Navi announcing recommendation + clean detail cards."""

    # ========================================
    # NAVIGATION GATE: Handle proceed request at top (before rendering UI)
    # ========================================
    # Check if user clicked Continue button (debounce mechanism)
    proceed_requested = st.session_state.get("gcp.proceed_requested", False)
    summary_ready = st.session_state.get("summary_ready", False) or st.session_state.get("gcp.llm_result_ready", False)

    if proceed_requested:
        if summary_ready:
            # Clear the flag and navigate
            st.session_state["gcp.proceed_requested"] = False
            print("[GCP_NAV] to=cost_v2 proceed=True ready=True")

            from core.flags import get_flag
            from core.nav import route_to

            # Set handoff flag
            st.session_state["flow.from_gcp"] = True

            # Check for partner interstitial requirement
            partner_flow_enabled = get_flag("FEATURE_HOUSEHOLD_PARTNER_FLOW")
            if partner_flow_enabled:
                # TODO: Add partner interstitial logic here
                # For now, proceed directly to learn recommendation
                pass

            # Phase 4B: Route to Learn About My Recommendation instead of directly to Cost Planner
            print("[GCP_NAV] Navigate to learn_recommendation (Phase 4B)")
            route_to("learn_recommendation")
            return  # Exit early after navigation
        else:
            # Summary not ready yet - show loading state and block
            print("[GCP_NAV] waiting proceed=True ready=False")
            st.info("⏳ Preparing your summary...")
            st.stop()  # Stop rendering and wait for next rerun

    # ========================================
    # NORMAL RESULTS RENDERING
    # ========================================

    # Get data
    outcome_key = f"{config.state_key}._outcomes"
    outcomes = st.session_state.get(outcome_key, {})
    recommendation = _get_recommendation(mod, config)
    confidence = outcomes.get("confidence", 1.0)
    # Handle None confidence gracefully
    if confidence is None:
        confidence = 1.0
    confidence_pct = int(confidence * 100)
    tier = outcomes.get("tier", "")
    tier_score = outcomes.get("tier_score", 0)

    # Extract recommendation text (clean)
    if recommendation and "recommend" in recommendation.lower():
        rec_text = recommendation.split("recommend")[-1].strip().rstrip(".")
    elif recommendation:
        rec_text = recommendation
    else:
        rec_text = "Your Guided Care Plan"

    # ========================================
    # 1. BLUE NAVI HEADER (skip if product already rendered one)
    # ========================================
    # Product pages (GCP) render the header at the top; avoid duplication here.
    
    # Open scoped wrapper for recommendation layout spacing
    st.markdown('<div class="gcp-rec">', unsafe_allow_html=True)
    
    # Check if interim AL should be presented
    show_interim_al = get_cached_interim_al()
    
    try:
        if not st.session_state.get("_gcp_cp_header_rendered", False):
            from core.ui import render_navi_panel_v2
            header_title = "Your Guided Care Plan"
            
            # Use helper to get subtitle based on final tier (post-adjudication)
            header_reason = get_results_subtitle(st.session_state)
            
            render_navi_panel_v2(
                title=header_title,
                reason=header_reason,
                encouragement={"icon": "💬", "text": "You can adjust details anytime and explore costs next.", "status": "in_progress"},
                context_chips=[],
                primary_action={"label": "", "route": ""},
                variant="module",
            )
            # Mark as rendered to protect against downstream duplicate calls
            st.session_state["_gcp_cp_header_rendered"] = True
            st.session_state["_gcp_cp_header_key"] = "gcp_cp_header::results"
    except Exception:
        pass

    # --- Conditional interim AL callout (in white space) ---
    if show_interim_al:
        from products.gcp_v4.ui_helpers import render_interim_al_callout, vrhythm
        vrhythm("after-navi")
        render_interim_al_callout()
        vrhythm("before-meaning")

    # --- Conditional Memory Care eligibility banner ---
    show_banner = _get_cached_mc_advice()
    
    # Debug pin (visible only in dev_mode)
    if st.session_state.get("dev_mode"):
        outcome_ids = _get_outcome_flags()
        st.caption(f"🔍 MC_ELIG pin: show={show_banner}, flags={sorted(outcome_ids)}")
    
    if show_banner:
        logging.info("MC_ELIG: rendering eligibility advice banner")
        render_mc_eligibility_banner()

    # Wrap the recommendation body text so we can add spacing below
    st.markdown('<div class="rec-body">', unsafe_allow_html=True)
    
    # Clean paragraphs under header
    try:
        from products.gcp_v4.ui_helpers import render_clean_summary
        render_clean_summary()
    except Exception as e:
        print(f"[ENGINE] render_clean_summary() FAILED: {e}")
        pass
    
    st.markdown('</div>', unsafe_allow_html=True)  # close rec-body

    # ========================================
    # 2. RECOMMENDATION CLARITY - Collapsible Drawer (Developer Tool)
    # ========================================

    # Calculate clarity metrics (for fine-tuning)
    tier_thresholds = {
        "no_care_needed": (0, 8),
        "in_home": (9, 16),
        "assisted_living": (17, 24),
        "memory_care": (25, 39),
        "memory_care_high_acuity": (40, 100),
    }

    boundary_clarity = 100
    clarity_message = "Clear"
    if tier in tier_thresholds:
        min_score, max_score = tier_thresholds[tier]
        distance_from_min = tier_score - min_score
        distance_from_max = max_score - tier_score
        distance_from_boundary = min(distance_from_min, distance_from_max)
        boundary_clarity = min(int((distance_from_boundary / 3.0) * 100), 100)

        if boundary_clarity >= 80:
            clarity_message = "Strong — well within tier"
        elif boundary_clarity >= 50:
            clarity_message = "Moderate — some distance from boundary"
        else:
            clarity_message = "Near boundary — consider reviewing"

    # ========================================
    # 2. NEXT ACTIONS - Three Simple Buttons
    # ========================================

    # Wrap the 3-button row so we can add spacing above it
    st.markdown('<div class="rec-actions">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🏁 Start Over – Answer Questions Again", key="btn_restart_gcp", use_container_width=True):
            # Clear only GCP-related state to avoid LLM recompute on click
            # Preserve auth, session_id, dev_mode
            preserve = {"auth", "session_id", "dev_mode"}
            for k in list(st.session_state.keys()):
                if k not in preserve:
                    if k.startswith("gcp_") or k in ("_summary_advice", "_hours_suggestion", "_hours_ack", "_hours_nudge_key", "_hours_nudge_new", "_gcp_llm_advice", "_mc_advice_cached", "_mc_banner_rendered", "_gcp_cp_header_rendered", "_interim_al_cached", "_show_mc_interim_advice"):
                        st.session_state.pop(k, None)

            # Reset to step 0 (first question - Age section)
            st.session_state[f"{config.state_key}._step"] = 0

            # Update tile state to step 0
            tiles = st.session_state.setdefault("tiles", {})
            tile_state = tiles.setdefault(config.product, {})
            tile_state["last_step"] = 0

            # Clear other progress markers
            for k in ("gcp_view", "persistence_loaded"):
                st.session_state.pop(k, None)

            # Rerun to show first question
            from core.modules.engine import safe_rerun
            safe_rerun()

    with col2:
        if st.button("💰 Explore Care Options & Costs", key="btn_costs", type="primary", use_container_width=True):
            from core.nav import route_to
            print("[GCP_RESULTS] Navigate to cost_intro")
            route_to("cost_intro")

    with col3:
        if st.button("🏠 Return to Lobby", key="btn_hub", use_container_width=True):
            from core.nav import route_to
            route_to("hub_lobby")

    st.markdown('</div>', unsafe_allow_html=True)  # close rec-actions

    # Bottom horizontal rule
    st.markdown("---")
    
    st.markdown('</div>', unsafe_allow_html=True)  # close gcp-rec


def _render_results_summary(state: dict[str, Any], config: ModuleConfig) -> None:
    bullets: list[str] = []

    def add_bullet(prefix: str, field_key: str, join: bool = False) -> None:
        field = _find_field(config, field_key)
        if not field:
            return
        value = state.get(field_key)
        if not _has_value(value):
            return
        text = _display_value(field, value)
        if join and isinstance(value, (list, tuple, set)):
            text = ", ".join(str(v) for v in value if str(v))
        bullets.append(f"{prefix} {text}")

    add_bullet("Independence snapshot:", "help_overall")
    add_bullet("Cognitive notes:", "memory_changes")
    add_bullet("Medication complexity:", "meds_complexity")

    chronic_chunks: list[str] = []
    chronic_field = _find_field(config, "chronic_conditions")
    chronic_value = state.get("chronic_conditions")
    if chronic_field and _has_value(chronic_value):
        chronic_chunks.append(_display_value(chronic_field, chronic_value))

    additional_value = state.get("additional_conditions")
    if isinstance(additional_value, (list, tuple, set)):
        chronic_chunks.extend(str(v) for v in additional_value if str(v))
    elif additional_value:
        chronic_chunks.append(str(additional_value))

    if chronic_chunks:
        bullets.append(f"Chronic conditions: {', '.join(chronic_chunks)}")

    flags = state.get("flags", {})
    if isinstance(flags, dict) and flags.get("emotional_followup"):
        message = (
            flags.get("emotional_followup_message")
            or "Emotional well-being: follow-up recommended."
        )
        bullets.append(message)

    add_bullet("Caregiver hours/day:", "hours_per_day")
    add_bullet("Location/access:", "isolation")

    if not bullets:
        return

    items = "".join(f"<li>{H(b)}</li>" for b in bullets)
    st.markdown(f"<ul>{items}</ul>", unsafe_allow_html=True)


def _render_recommendation_details(points: list[str]) -> None:
    """Render recommendation details in a clean, icon-based grid.

    Groups summary points by category with visual icons.
    """
    # Categorize points by keyword detection
    categories = {
        "cognitive": {"icon": "🧠", "label": "Cognitive Health", "points": []},
        "medication": {"icon": "💊", "label": "Medications", "points": []},
        "mobility": {"icon": "🦽", "label": "Mobility & Safety", "points": []},
        "health": {"icon": "❤️", "label": "Health Conditions", "points": []},
        "daily": {"icon": "🏠", "label": "Daily Living", "points": []},
        "social": {"icon": "👥", "label": "Social & Support", "points": []},
    }

    # Categorize each point
    for point in points:
        point_lower = point.lower()
        categorized = False

        # Cognitive
        if any(
            word in point_lower
            for word in ["memory", "cognitive", "confusion", "dementia", "alzheimer"]
        ):
            categories["cognitive"]["points"].append(point)
            categorized = True

        # Medication
        if any(word in point_lower for word in ["medication", "prescription", "med", "drug"]):
            categories["medication"]["points"].append(point)
            categorized = True

        # Mobility
        if any(
            word in point_lower
            for word in ["mobility", "fall", "walk", "wheelchair", "transfer", "balance"]
        ):
            categories["mobility"]["points"].append(point)
            categorized = True

        # Health conditions
        if any(
            word in point_lower
            for word in ["chronic", "condition", "disease", "illness", "diabetes", "heart"]
        ):
            categories["health"]["points"].append(point)
            categorized = True

        # Daily living
        if any(
            word in point_lower
            for word in ["adl", "bathing", "dressing", "eating", "toileting", "grooming", "hygiene"]
        ):
            categories["daily"]["points"].append(point)
            categorized = True

        # Social
        if any(
            word in point_lower
            for word in ["social", "isolation", "alone", "caregiver", "family", "support"]
        ):
            categories["social"]["points"].append(point)
            categorized = True

        # If not categorized, add to daily living as default
        if not categorized:
            categories["daily"]["points"].append(point)

    # Render only categories that have points
    active_categories = [cat for cat in categories.values() if cat["points"]]

    if not active_categories:
        return

    # Determine grid columns based on count
    num_cols = min(len(active_categories), 3)
    cols = st.columns(num_cols)

    for idx, category in enumerate(active_categories):
        with cols[idx % num_cols]:
            st.markdown(
                f"""
            <div style="
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                min-height: 120px;
            ">
                <div style="
                    font-size: 24px;
                    margin-bottom: 8px;
                ">{category["icon"]}</div>
                <div style="
                    font-size: 12px;
                    font-weight: 600;
                    color: #64748b;
                    letter-spacing: 0.5px;
                    margin-bottom: 12px;
                ">{category["label"].upper()}</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.5;">
                    {"<br>".join([f"• {H(p)}" for p in category["points"]])}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    # Add collapsible "View More Details" if there are many points
    if len(points) > 6:
        with st.expander("📋 View Full Details", expanded=False):
            items = "".join(f"<li style='margin-bottom: 8px;'>{H(p)}</li>" for p in points)
            st.markdown(f"<ul style='line-height: 1.6;'>{items}</ul>", unsafe_allow_html=True)


def _render_results_ctas_once(config: ModuleConfig) -> None:
    """Render action buttons on results page."""
    state_key = config.state_key

    st.markdown('<div class="sn-app mod-actions">', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Review Answers button - navigate back to first question
        if st.button(
            "← Review Your Answers",
            key="_results_review",
            type="secondary",
            use_container_width=True,
            help="Go back to review or update your answers",
        ):
            # Navigate back to first question (step 0)
            st.session_state[f"{state_key}._step"] = 0

            # Update tile state
            tiles = st.session_state.setdefault("tiles", {})
            tile_state = tiles.setdefault(config.product, {})
            tile_state["last_step"] = 0

            safe_rerun()

    with col2:
        # Back to Lobby button
        if st.button(
            "← Back to Lobby",
            key="_results_back_hub",
            type="secondary",
            use_container_width=True,
            help="Return to the main lobby",
        ):
            from core.nav import go_to_lobby
            go_to_lobby()

    st.markdown("</div>", unsafe_allow_html=True)

    # Primary next step: Calculate Costs (only for GCP) - tier-aware CTA
    if config.product == "gcp_v4":
        st.markdown("---")
        st.markdown('<div class="sn-app mod-actions">', unsafe_allow_html=True)

        # Build streamlined CTA for Learn About Recommendation handoff (Phase 4B)
        cta_label = "Next: Learn About Your Care Option →"
        cta_help = "Understand your recommendation before exploring costs"

        # Disable button if summary not ready (extra safety)
        summary_ready = st.session_state.get("summary_ready", False) or st.session_state.get("gcp.llm_result_ready", False)

        if st.button(
            cta_label,
            key="_results_next_cost",
            type="primary",
            use_container_width=True,
            help=cta_help,
            disabled=not summary_ready,
        ):
            # Set proceed flag and rerun - navigation happens at top of _render_results_view
            print(f"[GCP_CTA] results_continue clicked ready={summary_ready}")
            st.session_state["gcp.proceed_requested"] = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def _effect_triggered(values: Sequence[str], triggers: Sequence[str]) -> bool:
    normalized_values = [v.strip().lower() for v in values if str(v).strip()]
    normalized_triggers = [t.strip().lower() for t in triggers if str(t).strip()]
    for trigger in normalized_triggers:
        for current in normalized_values:
            if current == trigger or trigger in current:
                return True
    return False


def _rerun_app() -> None:
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
        return
    legacy_rerun = getattr(st, "experimental_rerun", None)
    if callable(legacy_rerun):
        legacy_rerun()
        return
    raise RuntimeError("Streamlit rerun is unavailable in this environment.")


def _render_navi_guide_bar(
    config: ModuleConfig, step: StepDef, state: dict[str, Any], step_index: int, progress_total: int
) -> None:
    """Render Navi's persistent guide bar at top of module.

    PRIORITY: Use step.navi_guidance if embedded in module JSON.
    FALLBACK: Use navi_dialogue.json for legacy modules.

    Args:
        config: Module configuration
        step: Current step definition
        state: Module state
        step_index: Current step index
        progress_total: Total progress-eligible steps
    """
    try:
        from core.mcip import MCIP
        from core.ui import render_navi_guide_bar

        # Check if step has embedded navi_guidance (new system)
        if step.navi_guidance:
            message = step.navi_guidance
        # Check if module has intro/outro guidance
        elif step_index == 0 and config.navi_intro:
            message = config.navi_intro
        elif (
            step_index == len(config.steps) - 1
            or (config.results_step_id and step.id == config.results_step_id)
        ) and config.navi_outro:
            message = config.navi_outro
        else:
            # Fallback to dialogue JSON (legacy system)
            from core.navi_dialogue import NaviDialogue

            # Map product key to dialogue key
            product_to_dialogue = {"gcp_v4": "gcp", "cost_v2": "cost_planner", "pfma_v2": "pfma"}

            dialogue_product = product_to_dialogue.get(config.product, config.product)

            # Determine module key from step
            is_first_step = step_index == 0
            is_last_step = step_index == len(config.steps) - 1
            is_results = config.results_step_id and step.id == config.results_step_id

            if is_first_step:
                module_key = "intro"
            elif is_results or is_last_step:
                module_key = "complete"
            else:
                module_key = step.id if step.id else "intro"

            # Build context from MCIP
            context = {}
            try:
                care_rec = MCIP.get_care_recommendation()
                if care_rec:
                    context["tier"] = care_rec.tier
                    context["confidence"] = int(care_rec.confidence * 100)
            except:
                pass

            try:
                financial = MCIP.get_financial_profile()
                if financial:
                    context["monthly_cost"] = f"${financial.estimated_monthly_cost:,.0f}"
                    context["runway_months"] = financial.runway_months
            except:
                pass

            # Get message from dialogue JSON
            message = NaviDialogue.get_module_message(dialogue_product, module_key, context)

        if not message:
            return

        # Calculate current progress step
        progress_steps = [s for s in config.steps if s.show_progress]
        current_progress = sum(1 for s in progress_steps if config.steps.index(s) < step_index) + (
            1 if step.show_progress else 0
        )

        # Determine if we should show progress
        is_first_step = step_index == 0
        is_results = config.results_step_id and step.id == config.results_step_id
        show_progress_bar = progress_total > 0 and not is_first_step and not is_results

        # Get color from message or use default
        color = message.get("color", "#8b5cf6")

        render_navi_guide_bar(
            text=message.get("text", ""),
            subtext=message.get("subtext"),
            icon=message.get("icon", "🤖"),
            show_progress=show_progress_bar,
            current_step=current_progress if current_progress > 0 else None,
            total_steps=progress_total if progress_total > 0 else None,
            color=color,
        )
    except Exception as e:
        # Silently fail if Navi can't render (don't break module flow)
        import sys

        print(f"[WARN] Navi guide bar failed: {e}", file=sys.stderr)


def load_modules_for_product(product_key: str) -> list[dict[str, Any]]:
    """Load module metadata for a given product.
    
    Discovers modules associated with a product by checking the products/
    directory structure. Each product can have multiple modules in its
    modules/ subdirectory with config.py files.
    
    This function provides explicit module discovery for the Lobby Hub
    and other product navigation systems, making the dynamic architecture
    more visible.
    
    Args:
        product_key: Product identifier (e.g., 'gcp_v4', 'cost_planner_v2')
    
    Returns:
        List of module metadata dicts with keys:
            - module_id: Unique module identifier
            - title: Display title
            - enabled: Whether module is active
            - weight: Sort order
            - config: ModuleConfig object if available
    
    Example:
        >>> modules = load_modules_for_product('gcp_v4')
        >>> for mod in modules:
        ...     print(f"{mod['title']}: {mod['module_id']}")
    
    Note:
        The existing run_module() function handles actual module execution.
        This function is for discovery/navigation purposes only.
    """
    modules = []
    
    # Map product_key to product path
    product_paths = {
        'gcp_v4': 'products/concierge_hub/gcp_v4',
        'cost_planner_v2': 'products/concierge_hub/cost_planner_v2',
        'cost_v2': 'products/concierge_hub/cost_planner_v2',
        'pfma_v3': 'products/concierge_hub/pfma_v3',
    }
    
    product_path = product_paths.get(product_key)
    if not product_path:
        return modules
    
    # Check if product has a modules directory
    import os
    modules_path = os.path.join(product_path, 'modules')
    
    if not os.path.exists(modules_path):
        return modules
    
    # Discover module configs
    for module_name in os.listdir(modules_path):
        module_dir = os.path.join(modules_path, module_name)
        if not os.path.isdir(module_dir):
            continue
        
        config_file = os.path.join(module_dir, 'config.py')
        if not os.path.exists(config_file):
            continue
        
        # Load module config
        try:
            from core.modules.schema import ModuleConfig
            config_module = importlib.import_module(
                f"{product_path.replace('/', '.')}.modules.{module_name}.config"
            )
            
            if hasattr(config_module, 'get_config'):
                config = config_module.get_config()
                
                modules.append({
                    'module_id': config.state_key,
                    'title': config.title or module_name,
                    'enabled': True,
                    'weight': getattr(config, 'weight', 10),
                    'config': config,
                })
        except Exception as e:
            # Skip modules that can't be loaded
            print(f"[MODULE_DISCOVERY] Failed to load {module_name}: {e}")
            continue
    
    # Sort by weight
    modules.sort(key=lambda m: m['weight'])
    
    return modules


__all__ = ["run_module", "load_modules_for_product"]
