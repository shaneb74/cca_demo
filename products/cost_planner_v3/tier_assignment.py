"""
Cost Planner v3 - Tier Assignment Logic

Maps GCP flags and answers to care tiers.
"""

from typing import Set, Dict, Any


def assign_assisted_living_tier(gcp_flags: Set[str], gcp_answers: Dict[str, Any]) -> str:
    """
    Assign AL tier based on GCP flags and answers.
    
    Logic Priority:
    1. Multiple high-intensity needs → Tier 4
    2. Memory/behavioral/extensive ADLs → Tier 3
    3. Mobility/moderate ADLs → Tier 2
    4. Medication/mild ADLs → Tier 1
    5. Default → Tier 0
    
    Args:
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
    
    Returns:
        "tier_0" | "tier_1" | "tier_2" | "tier_3" | "tier_4"
    """
    
    badls_count = gcp_answers.get("badls_count", 0)
    iadls_count = gcp_answers.get("iadls_count", 0)
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    
    # TIER 4: Multiple high-intensity needs
    tier_4_conditions = [
        "severe_cognitive_risk" in gcp_flags,
        "high_mobility_dependence" in gcp_flags,
        "behavioral_concerns" in gcp_flags,
        badls_count >= 3,
        "continuous_supervision" in gcp_flags
    ]
    if sum(tier_4_conditions) >= 2:
        return "tier_4"
    
    # TIER 3: Memory support OR behavioral OR extensive ADLs
    if any([
        "severe_cognitive_risk" in gcp_flags,
        "moderate_cognitive_decline" in gcp_flags and badls_count >= 2,
        "behavioral_concerns" in gcp_flags,
        badls_count >= 3,
        "high_dependence" in gcp_flags
    ]):
        return "tier_3"
    
    # TIER 2: Mobility assistance OR moderate ADL help
    if any([
        "high_mobility_dependence" in gcp_flags,
        "transfer_assistance_1person" in gcp_flags,
        badls_count >= 2,
        "incontinence_management" in gcp_flags,
        "falls_multiple" in gcp_flags
    ]):
        return "tier_2"
    
    # TIER 1: Medication management OR mild ADL help
    meds = gcp_answers.get("meds_complexity")
    if any([
        meds in ["moderate", "complex"],
        badls_count == 1,
        iadls_count >= 4,
        "mild_cognitive_decline" in gcp_flags
    ]):
        return "tier_1"
    
    # TIER 0: Minimal support (default)
    return "tier_0"


def assign_memory_care_tier(gcp_flags: Set[str], gcp_answers: Dict[str, Any]) -> str:
    """
    Assign MC tier based on GCP flags and answers.
    
    Note: Memory care baseline already includes secured environment + memory support.
    Tiers reflect ADL/behavioral complexity on top of baseline MC.
    
    Args:
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
    
    Returns:
        "tier_0" | "tier_1" | "tier_2" | "tier_3" | "tier_4"
    """
    
    badls_count = gcp_answers.get("badls_count", 0)
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    
    # TIER 4: Severe behaviors or hands-on care
    if any([
        "behavioral_concerns" in gcp_flags and behaviors_count >= 3,
        "continuous_supervision" in gcp_flags and "high_dependence" in gcp_flags,
        badls_count >= 4,
        "transfer_lift_required" in gcp_flags
    ]):
        return "tier_4"
    
    # TIER 3: Behavioral concerns or complex ADLs
    if any([
        "behavioral_concerns" in gcp_flags,
        badls_count >= 3,
        "transfer_assistance_2person" in gcp_flags,
        "high_dependence" in gcp_flags
    ]):
        return "tier_3"
    
    # TIER 2: Moderate ADLs or mobility needs
    if any([
        badls_count >= 2,
        "high_mobility_dependence" in gcp_flags,
        "incontinence_management" in gcp_flags
    ]):
        return "tier_2"
    
    # TIER 1: Mild ADL or mobility support
    if any([
        badls_count == 1,
        "transfer_assistance_1person" in gcp_flags,
        "moderate_mobility" in gcp_flags
    ]):
        return "tier_1"
    
    # TIER 0: Standard MC (baseline)
    return "tier_0"


def should_recommend_memory_care_instead_of_al(
    gcp_flags: Set[str], 
    gcp_answers: Dict[str, Any]
) -> bool:
    """
    Determine if resident needs Memory Care instead of Assisted Living.
    This is tier overflow logic - when AL complexity exceeds AL capability.
    
    Args:
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
    
    Returns:
        True if Memory Care recommended over AL
    """
    
    badls_count = gcp_answers.get("badls_count", 0)
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    
    # Diagnosed dementia + any complexity
    if "memory_care_dx" in gcp_flags and any([
        badls_count >= 2,
        "behavioral_concerns" in gcp_flags,
        "continuous_supervision" in gcp_flags
    ]):
        return True
    
    # Severe cognitive risk + safety concerns
    if "severe_cognitive_risk" in gcp_flags and any([
        "behavioral_concerns" in gcp_flags,
        "continuous_supervision" in gcp_flags,
        gcp_answers.get("safe_alone") == "no"
    ]):
        return True
    
    # Multiple behaviors indicating memory care need
    if behaviors_count >= 3:
        return True
    
    return False


def should_recommend_high_acuity_mc(
    gcp_flags: Set[str],
    gcp_answers: Dict[str, Any],
    mc_tier: str
) -> bool:
    """
    Determine if High-Acuity Memory Care is needed.
    
    High-acuity triggers:
    - Tier 4 MC + skilled nursing indicators
    - Intensive ADL + behavioral needs
    - Total dependence markers
    
    Args:
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
        mc_tier: Assigned memory care tier
    
    Returns:
        True if High-Acuity MC recommended
    """
    
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    
    # MC Tier 4 + skilled nursing indicators
    if mc_tier == "tier_4" and any([
        "transfer_lift_required" in gcp_flags,
        gcp_answers.get("incontinence") == "complete",
        "continuous_supervision" in gcp_flags and behaviors_count >= 2
    ]):
        return True
    
    return False


def prepare_gcp_context(gcp_outcome: dict) -> dict:
    """
    Extract and normalize GCP data for cost calculation.
    
    Args:
        gcp_outcome: Raw GCP outcome from derive_outcome()
    
    Returns:
        {
            "flags": set,
            "answers": dict (normalized),
            "tier": str,
            "score": int
        }
    """
    
    flags = set(gcp_outcome.get("flags", []))
    answers = gcp_outcome.get("answers", {})
    
    # Calculate counts for tier assignment
    badls_list = answers.get("badls", [])
    iadls_list = answers.get("iadls", [])
    behaviors_list = answers.get("behaviors", [])
    chronic_list = answers.get("chronic_conditions", [])
    
    # Handle "none" values in lists
    if isinstance(badls_list, list):
        badls_list = [b for b in badls_list if b != "none"]
    else:
        badls_list = []
    
    if isinstance(iadls_list, list):
        iadls_list = [i for i in iadls_list if i != "none"]
    else:
        iadls_list = []
    
    if isinstance(behaviors_list, list):
        behaviors_list = [b for b in behaviors_list if b != "none"]
    else:
        behaviors_list = []
    
    if isinstance(chronic_list, list):
        chronic_list = [c for c in chronic_list if c != "none"]
    else:
        chronic_list = []
    
    # Normalize answers for tier logic
    normalized = {
        "badls_count": len(badls_list),
        "badls_list": badls_list,
        "iadls_count": len(iadls_list),
        "iadls_list": iadls_list,
        "behaviors_count": len(behaviors_list),
        "behaviors_list": behaviors_list,
        "chronic_conditions": chronic_list,
        "meds_complexity": answers.get("meds_complexity"),
        "incontinence": answers.get("incontinence"),
        "safe_alone": answers.get("safe_alone"),
        "transfers": answers.get("transfers"),
        "mobility": answers.get("mobility"),
        "memory_changes": answers.get("memory_changes"),
        "mood": answers.get("mood"),
        "falls": answers.get("falls")
    }
    
    return {
        "flags": flags,
        "answers": normalized,
        "tier": gcp_outcome.get("tier"),
        "score": gcp_outcome.get("score", 0),
        "support_band": gcp_outcome.get("support_band", "low"),
        "hours_band": gcp_outcome.get("hours_band", "<1h")
    }
