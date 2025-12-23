"""
Cost Planner v3 - Add-On Calculation Logic

Calculates capped secondary cost modifiers for care needs not captured in tiers.
"""

from typing import Set, Dict, Any, List
from products.cost_planner_v3.constants import MAX_ADDON_PCT, MAX_ADDON_ABSOLUTE, ADDON_AMOUNTS


def calculate_add_ons(
    care_type: str,
    gcp_flags: Set[str],
    gcp_answers: Dict[str, Any],
    regional_base: float
) -> List[Dict[str, Any]]:
    """
    Calculate capped add-ons for secondary care needs.
    
    Add-ons are used for:
    - Fall monitoring (when not primary tier driver)
    - Chronic condition complexity (when materially affecting care)
    - Incontinence care (when not captured in tier)
    
    Args:
        care_type: Type of care ("assisted_living", "memory_care", etc.)
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
        regional_base: Base cost after regional adjustment
    
    Returns:
        List of {"label": str, "amount": float, "description": str}
    """
    
    add_ons = []
    
    # Calculate maximum single add-on cap
    max_addon = min(MAX_ADDON_ABSOLUTE, regional_base * MAX_ADDON_PCT)
    
    # Fall monitoring add-on (if falls present but not primary driver)
    if "falls_multiple" in gcp_flags:
        add_ons.append({
            "label": "Fall Prevention Monitoring",
            "amount": min(400, max_addon * ADDON_AMOUNTS["fall_monitoring"]),
            "description": "Enhanced monitoring and prevention protocols",
            "reason": "Multiple falls in past 6 months"
        })
    
    # Chronic condition complexity (only when affecting care delivery)
    if should_apply_chronic_addon(gcp_flags, gcp_answers):
        chronic_count = len(gcp_answers.get("chronic_conditions", []))
        add_ons.append({
            "label": "Chronic Condition Management",
            "amount": min(300, max_addon * ADDON_AMOUNTS["chronic_complexity"]),
            "description": "Coordination and monitoring for complex chronic conditions",
            "reason": f"{chronic_count} chronic conditions requiring active management"
        })
    
    # Incontinence care (if not already captured in tier)
    badls_count = gcp_answers.get("badls_count", 0)
    if "incontinence_management" in gcp_flags and badls_count < 2:
        add_ons.append({
            "label": "Incontinence Care",
            "amount": min(250, max_addon * ADDON_AMOUNTS["incontinence_care"]),
            "description": "Regular assistance and supplies",
            "reason": "Requires incontinence management support"
        })
    
    # Cap total add-ons
    total_addons = sum(a["amount"] for a in add_ons)
    if total_addons > max_addon:
        # Proportionally reduce all add-ons to fit cap
        scale_factor = max_addon / total_addons
        for add_on in add_ons:
            add_on["amount"] = add_on["amount"] * scale_factor
            add_on["capped"] = True
    else:
        for add_on in add_ons:
            add_on["capped"] = False
    
    return add_ons


def should_apply_chronic_addon(gcp_flags: Set[str], gcp_answers: Dict[str, Any]) -> bool:
    """
    Determine if chronic conditions justify cost add-on.
    
    Core principle: Chronic conditions only increase cost when they
    materially affect care delivery.
    
    Chronic conditions increase cost when they:
    - Increase ADL support needs
    - Require medication coordination
    - Need active symptom monitoring
    - Affect mobility or safety
    
    Args:
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
    
    Returns:
        True if chronic add-on justified
    """
    
    chronic_list = gcp_answers.get("chronic_conditions", [])
    chronic_count = len(chronic_list)
    
    # No chronic conditions = no add-on
    if chronic_count == 0:
        return False
    
    # Multiple chronic conditions + medication complexity
    meds = gcp_answers.get("meds_complexity")
    if chronic_count >= 3 and meds in ["moderate", "complex"]:
        return True
    
    # Chronic conditions + falls (indicating instability)
    if chronic_count >= 2 and "falls_multiple" in gcp_flags:
        return True
    
    # Specific high-impact chronic conditions
    high_impact_conditions = {
        "parkinsons",      # Affects mobility, ADLs, progressive
        "copd",            # Affects mobility, requires monitoring
        "heart_disease",   # Requires monitoring, activity limitations
        "stroke"           # Often affects ADLs, mobility, speech
    }
    
    # High-impact condition + functional impairment
    has_high_impact = any(c in chronic_list for c in high_impact_conditions)
    badls_count = gcp_answers.get("badls_count", 0)
    
    if has_high_impact and badls_count >= 1:
        return True
    
    # Multiple high-impact conditions
    high_impact_count = sum(1 for c in chronic_list if c in high_impact_conditions)
    if high_impact_count >= 2:
        return True
    
    # Default: No add-on
    return False


def explain_chronic_addon_logic(gcp_flags: Set[str], gcp_answers: Dict[str, Any]) -> str:
    """
    Generate explanation for why chronic conditions do/don't increase cost.
    
    Returns:
        Human-readable explanation
    """
    
    chronic_list = gcp_answers.get("chronic_conditions", [])
    chronic_count = len(chronic_list)
    
    if chronic_count == 0:
        return "No chronic conditions reported."
    
    if not should_apply_chronic_addon(gcp_flags, gcp_answers):
        return (
            f"{chronic_count} chronic condition(s) present but stable and "
            "not requiring additional care coordination at this time."
        )
    
    # Build explanation for why add-on applies
    reasons = []
    
    meds = gcp_answers.get("meds_complexity")
    if chronic_count >= 3 and meds in ["moderate", "complex"]:
        reasons.append("multiple conditions requiring complex medication management")
    
    if chronic_count >= 2 and "falls_multiple" in gcp_flags:
        reasons.append("chronic instability contributing to fall risk")
    
    high_impact = ["parkinsons", "copd", "heart_disease", "stroke"]
    has_high_impact = any(c in chronic_list for c in high_impact)
    badls_count = gcp_answers.get("badls_count", 0)
    
    if has_high_impact and badls_count >= 1:
        impact_names = [c.replace("_", " ").title() for c in chronic_list if c in high_impact]
        reasons.append(f"{', '.join(impact_names)} affecting daily function")
    
    if reasons:
        return (
            f"{chronic_count} chronic condition(s) increasing care needs due to: "
            f"{'; '.join(reasons)}."
        )
    
    return f"{chronic_count} chronic conditions requiring active management."
