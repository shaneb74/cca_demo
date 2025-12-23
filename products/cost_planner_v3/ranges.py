"""
Cost Planner v3 - Cost Range Calculation

Calculates confidence-based cost ranges (low/likely/high estimates).
"""

from typing import Set, Dict, Any
from products.cost_planner_v3.constants import CONFIDENCE_RANGES


def calculate_cost_range(
    total: float,
    gcp_flags: Set[str],
    gcp_answers: Dict[str, Any],
    care_type: str
) -> Dict[str, Any]:
    """
    Calculate low/likely/high estimates with confidence level.
    
    Ranges widen based on uncertainty factors:
    - High confidence (±7%): Stable, predictable needs
    - Medium confidence (±12%): Some variability expected
    - Low confidence (±20%): High uncertainty/market variation
    
    Args:
        total: Calculated monthly cost
        gcp_flags: Set of care flags from GCP
        gcp_answers: Normalized answer dictionary
        care_type: Type of care being calculated
    
    Returns:
        {
            "low": float,
            "likely": float,
            "high": float,
            "confidence": "high" | "medium" | "low",
            "range_pct": float,
            "range_explanation": str,
            "widening_factors": list[str]
        }
    """
    
    # Determine confidence level and collect widening factors
    widening_factors = []
    
    if has_high_uncertainty(gcp_flags, gcp_answers, care_type):
        confidence = "low"
        widening_factors = get_high_uncertainty_factors(gcp_flags, gcp_answers, care_type)
    elif has_moderate_uncertainty(gcp_flags, gcp_answers, care_type):
        confidence = "medium"
        widening_factors = get_moderate_uncertainty_factors(gcp_flags, gcp_answers, care_type)
    else:
        confidence = "high"
        widening_factors = ["Care needs are stable and predictable"]
    
    range_pct = CONFIDENCE_RANGES[confidence]
    
    low = total * (1 - range_pct)
    likely = total
    high = total * (1 + range_pct)
    
    # Generate explanation
    explanation = generate_range_explanation(confidence, widening_factors)
    
    return {
        "low": round(low, 2),
        "likely": round(likely, 2),
        "high": round(high, 2),
        "confidence": confidence,
        "range_pct": range_pct,
        "range_explanation": explanation,
        "widening_factors": widening_factors
    }


def has_high_uncertainty(gcp_flags: Set[str], gcp_answers: Dict[str, Any], care_type: str) -> bool:
    """
    Check for high uncertainty factors (±20% range).
    
    High uncertainty occurs when:
    - Severe behavioral concerns (unpredictable needs)
    - High-acuity memory care (wide market variation)
    - 2-person transfers + multiple ADLs (complex staffing)
    - In-home with continuous supervision (24/7 coverage)
    """
    
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    badls_count = gcp_answers.get("badls_count", 0)
    
    # Severe behavioral concerns
    if "behavioral_concerns" in gcp_flags and behaviors_count >= 3:
        return True
    
    # High-acuity memory care (always high uncertainty)
    if care_type == "memory_care_high_acuity":
        return True
    
    # 2-person transfer + multiple ADLs
    if "transfer_assistance_2person" in gcp_flags and badls_count >= 3:
        return True
    
    # Mechanical lift required
    if "transfer_lift_required" in gcp_flags:
        return True
    
    # In-home with continuous supervision
    if care_type == "in_home_care" and "continuous_supervision" in gcp_flags:
        return True
    
    return False


def has_moderate_uncertainty(gcp_flags: Set[str], gcp_answers: Dict[str, Any], care_type: str) -> bool:
    """
    Check for moderate uncertainty factors (±12% range).
    
    Moderate uncertainty occurs when:
    - Memory care with behaviors (variability in management)
    - Multiple falls + mobility concerns (fall prevention complexity)
    - Chronic instability (multiple conditions + falls)
    - High dependence in any domain
    """
    
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    chronic_count = len(gcp_answers.get("chronic_conditions", []))
    
    # Memory care with behaviors
    if care_type in ["memory_care", "memory_care_high_acuity"] and "behavioral_concerns" in gcp_flags:
        return True
    
    # Multiple falls + mobility concerns
    if "falls_multiple" in gcp_flags and "high_mobility_dependence" in gcp_flags:
        return True
    
    # Chronic instability (multiple conditions + falls)
    if chronic_count >= 3 and "falls_multiple" in gcp_flags:
        return True
    
    # High dependence (varies by provider)
    if "high_dependence" in gcp_flags:
        return True
    
    # Continuous supervision needs
    if "continuous_supervision" in gcp_flags and care_type != "in_home_care":
        return True
    
    return False


def get_high_uncertainty_factors(gcp_flags: Set[str], gcp_answers: Dict[str, Any], care_type: str) -> list[str]:
    """Get list of factors causing high uncertainty."""
    factors = []
    
    behaviors_count = gcp_answers.get("behaviors_count", 0)
    
    if behaviors_count >= 3:
        factors.append(f"Significant behavioral needs ({behaviors_count} behaviors) require intensive support")
    
    if care_type == "memory_care_high_acuity":
        factors.append("High-acuity memory care has wide market variation")
    
    if "transfer_assistance_2person" in gcp_flags or "transfer_lift_required" in gcp_flags:
        factors.append("2-person transfers or mechanical lifts require specialized staffing")
    
    if "continuous_supervision" in gcp_flags and care_type == "in_home_care":
        factors.append("24/7 in-home care has wide market variation")
    
    return factors


def get_moderate_uncertainty_factors(gcp_flags: Set[str], gcp_answers: Dict[str, Any], care_type: str) -> list[str]:
    """Get list of factors causing moderate uncertainty."""
    factors = []
    
    if "behavioral_concerns" in gcp_flags:
        factors.append("Behavioral needs may vary and require flexible support")
    
    if "falls_multiple" in gcp_flags:
        factors.append("Fall risk requires enhanced monitoring")
    
    chronic_count = len(gcp_answers.get("chronic_conditions", []))
    if chronic_count >= 3:
        factors.append(f"{chronic_count} chronic conditions may require additional oversight")
    
    if "high_dependence" in gcp_flags:
        factors.append("High level of care dependency varies by provider capability")
    
    if "continuous_supervision" in gcp_flags:
        factors.append("Continuous supervision requirements vary by community")
    
    return factors


def generate_range_explanation(confidence: str, widening_factors: list[str]) -> str:
    """
    Generate human-readable explanation for range width.
    
    Args:
        confidence: "high", "medium", or "low"
        widening_factors: List of factors affecting range
    
    Returns:
        Human-readable explanation string
    """
    
    if confidence == "high":
        return (
            "Cost range is narrow (±7%) because care needs are stable and predictable. "
            "Most communities will fall within this range."
        )
    
    elif confidence == "medium":
        reason_text = " and ".join(widening_factors).lower()
        return (
            f"Cost range is moderate (±12%) because {reason_text}. "
            "Different communities may price these needs differently."
        )
    
    else:  # low confidence
        reason_text = "; ".join(widening_factors).lower()
        return (
            f"Cost range is wide (±20%) because {reason_text}. "
            "Significant market variation exists for these complex care needs."
        )


def explain_range_to_advisor(range_result: dict) -> str:
    """
    Generate advisor-facing explanation of cost range.
    
    Args:
        range_result: Result from calculate_cost_range()
    
    Returns:
        Formatted explanation for advisors
    """
    
    confidence = range_result["confidence"]
    low = range_result["low"]
    high = range_result["high"]
    likely = range_result["likely"]
    pct = range_result["range_pct"] * 100
    
    explanation_parts = []
    
    # Range summary
    explanation_parts.append(
        f"**Estimated Cost Range:** ${low:,.0f} - ${high:,.0f}/month "
        f"(most likely: ${likely:,.0f})"
    )
    
    # Confidence level
    confidence_labels = {
        "high": "High Confidence (±{:.0f}%)".format(pct),
        "medium": "Moderate Confidence (±{:.0f}%)".format(pct),
        "low": "Lower Confidence (±{:.0f}%)".format(pct)
    }
    explanation_parts.append(f"**Confidence:** {confidence_labels[confidence]}")
    
    # Explanation
    explanation_parts.append(f"\n{range_result['range_explanation']}")
    
    # Widening factors detail
    if range_result["widening_factors"]:
        explanation_parts.append("\n**Factors Affecting Range:**")
        for factor in range_result["widening_factors"]:
            explanation_parts.append(f"- {factor}")
    
    return "\n".join(explanation_parts)
