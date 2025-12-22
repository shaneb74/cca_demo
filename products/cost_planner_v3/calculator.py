"""
Cost Planner v3 - Main Calculator

Tier-based cost calculation engine with regional scaling and confidence ranges.
"""

from typing import Dict, Any, Optional
from products.cost_planner_v3.constants import (
    get_base_cost,
    get_tier_increment,
    get_tier_config
)
from products.cost_planner_v3.tier_assignment import (
    assign_assisted_living_tier,
    assign_memory_care_tier,
    should_recommend_memory_care_instead_of_al,
    should_recommend_high_acuity_mc,
    prepare_gcp_context
)
from products.cost_planner_v3.add_ons import calculate_add_ons
from products.cost_planner_v3.ranges import calculate_cost_range


def calculate_care_costs(
    gcp_outcome: Dict[str, Any],
    regional_multiplier: float = 1.0,
    care_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate care costs using tier-based model.
    
    Args:
        gcp_outcome: Complete GCP assessment results with flags and answers
        regional_multiplier: Geographic cost adjustment (default: 1.0)
        care_type: Override care type (if None, uses GCP recommendation)
    
    Returns:
        Complete cost breakdown with ranges, explanations, and sources
        
    Example:
        >>> result = calculate_care_costs(gcp_outcome, regional_multiplier=1.3)
        >>> print(result["total_monthly"])
        7982.00
        >>> print(result["confidence"])
        "medium"
    """
    
    # Prepare normalized GCP context
    gcp_flags, gcp_answers = prepare_gcp_context(gcp_outcome)
    
    # Determine care type
    if care_type is None:
        care_type = determine_care_type(gcp_outcome, gcp_flags)
    
    # Calculate costs based on care type
    if care_type == "assisted_living":
        result = calculate_assisted_living(gcp_flags, gcp_answers, regional_multiplier)
    elif care_type == "memory_care":
        result = calculate_memory_care(gcp_flags, gcp_answers, regional_multiplier)
    elif care_type == "memory_care_high_acuity":
        result = calculate_memory_care_high_acuity(gcp_flags, gcp_answers, regional_multiplier)
    elif care_type == "in_home_care":
        result = calculate_in_home_care(gcp_flags, gcp_answers, regional_multiplier)
    elif care_type == "homemaker_care":
        result = calculate_homemaker_care(gcp_flags, gcp_answers, regional_multiplier)
    elif care_type == "home_with_carry":
        result = calculate_home_with_carry(gcp_flags, gcp_answers, regional_multiplier)
    else:
        raise ValueError(f"Unknown care type: {care_type}")
    
    # Add range calculations
    range_result = calculate_cost_range(
        result["total_monthly"],
        gcp_flags,
        gcp_answers,
        care_type
    )
    
    result.update({
        "low_estimate": range_result["low"],
        "likely_estimate": range_result["likely"],
        "high_estimate": range_result["high"],
        "confidence": range_result["confidence"],
        "range_pct": range_result["range_pct"],
        "range_explanation": range_result["range_explanation"],
        "widening_factors": range_result["widening_factors"]
    })
    
    # Add metadata
    result.update({
        "care_type": care_type,
        "regional_multiplier": regional_multiplier,
        "model_version": "3.0.0",
        "calculation_method": "tier_based"
    })
    
    return result


def determine_care_type(gcp_outcome: Dict[str, Any], gcp_flags: set) -> str:
    """
    Determine care type from GCP recommendation.
    
    Args:
        gcp_outcome: GCP assessment results
        gcp_flags: Set of care flags
    
    Returns:
        Care type string
    """
    
    # Get GCP recommendation
    recommendation = gcp_outcome.get("recommendation", "assisted_living")
    
    # Check for tier overflow (AL → MC)
    if recommendation == "assisted_living":
        gcp_answers = gcp_outcome.get("answers", {})
        if should_recommend_memory_care_instead_of_al(gcp_flags, gcp_answers):
            recommendation = "memory_care"
    
    # Check for high-acuity escalation (MC → MC-HA)
    if recommendation == "memory_care":
        gcp_answers = gcp_outcome.get("answers", {})
        if should_recommend_high_acuity_mc(gcp_flags, gcp_answers):
            recommendation = "memory_care_high_acuity"
    
    return recommendation


def calculate_assisted_living(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """Calculate AL costs with tier-based pricing."""
    
    # Get base cost
    base_cost = get_base_cost("assisted_living")
    regional_base = base_cost * regional_multiplier
    
    # Assign tier
    tier_id = assign_assisted_living_tier(gcp_flags, gcp_answers)
    tier_config = get_tier_config("assisted_living", tier_id)
    
    # Get tier increment
    tier_increment = get_tier_increment("assisted_living", tier_id, regional_multiplier)
    
    # Calculate add-ons
    max_addon = min(800, regional_base * 0.15)
    addons = calculate_add_ons(gcp_flags, gcp_answers, max_addon)
    addon_total = sum(a["amount"] for a in addons)
    
    # Total
    total = regional_base + tier_increment + addon_total
    
    return {
        "total_monthly": round(total, 2),
        "base_cost": round(base_cost, 2),
        "regional_base": round(regional_base, 2),
        "tier": tier_config["label"],
        "tier_id": tier_id,
        "tier_increment": round(tier_increment, 2),
        "tier_description": tier_config["description"],
        "addons": addons,
        "addon_total": round(addon_total, 2),
        "addon_cap": round(max_addon, 2),
        "breakdown": [
            {"label": "National Base", "amount": round(base_cost, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_base - base_cost, 2)},
            {"label": f"Care Tier: {tier_config['label']}", "amount": round(tier_increment, 2)},
            {"label": "Add-ons", "amount": round(addon_total, 2)}
        ]
    }


def calculate_memory_care(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """Calculate MC costs with tier-based pricing."""
    
    # Get base cost
    base_cost = get_base_cost("memory_care")
    regional_base = base_cost * regional_multiplier
    
    # Assign tier
    tier_id = assign_memory_care_tier(gcp_flags, gcp_answers)
    tier_config = get_tier_config("memory_care", tier_id)
    
    # Get tier increment
    tier_increment = get_tier_increment("memory_care", tier_id, regional_multiplier)
    
    # Calculate add-ons
    max_addon = min(800, regional_base * 0.15)
    addons = calculate_add_ons(gcp_flags, gcp_answers, max_addon)
    addon_total = sum(a["amount"] for a in addons)
    
    # Total
    total = regional_base + tier_increment + addon_total
    
    return {
        "total_monthly": round(total, 2),
        "base_cost": round(base_cost, 2),
        "regional_base": round(regional_base, 2),
        "tier": tier_config["label"],
        "tier_id": tier_id,
        "tier_increment": round(tier_increment, 2),
        "tier_description": tier_config["description"],
        "addons": addons,
        "addon_total": round(addon_total, 2),
        "addon_cap": round(max_addon, 2),
        "breakdown": [
            {"label": "National Base", "amount": round(base_cost, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_base - base_cost, 2)},
            {"label": f"Care Tier: {tier_config['label']}", "amount": round(tier_increment, 2)},
            {"label": "Add-ons", "amount": round(addon_total, 2)}
        ]
    }


def calculate_memory_care_high_acuity(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """Calculate high-acuity MC costs."""
    
    # Get base cost
    base_cost = get_base_cost("memory_care_high_acuity")
    regional_base = base_cost * regional_multiplier
    
    # High-acuity has no tiers (already intensive)
    # Only add-ons apply
    
    max_addon = min(800, regional_base * 0.15)
    addons = calculate_add_ons(gcp_flags, gcp_answers, max_addon)
    addon_total = sum(a["amount"] for a in addons)
    
    # Total
    total = regional_base + addon_total
    
    return {
        "total_monthly": round(total, 2),
        "base_cost": round(base_cost, 2),
        "regional_base": round(regional_base, 2),
        "tier": "High Acuity",
        "tier_id": "high_acuity",
        "tier_increment": 0.0,
        "tier_description": "24/7 specialized memory care with highest level of support",
        "addons": addons,
        "addon_total": round(addon_total, 2),
        "addon_cap": round(max_addon, 2),
        "breakdown": [
            {"label": "National Base", "amount": round(base_cost, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_base - base_cost, 2)},
            {"label": "Add-ons", "amount": round(addon_total, 2)}
        ]
    }


def calculate_in_home_care(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """
    Calculate in-home care costs (hourly-based).
    
    Note: Requires hours_per_week from GCP outcome
    """
    
    # Get hourly base
    hourly_base = get_base_cost("in_home_hourly")
    regional_hourly = hourly_base * regional_multiplier
    
    # Get recommended hours (from GCP or default to 20/week)
    hours_per_week = gcp_answers.get("recommended_hours_per_week", 20)
    hours_per_month = hours_per_week * 4.33  # Average weeks per month
    
    # Calculate monthly cost
    total = regional_hourly * hours_per_month
    
    return {
        "total_monthly": round(total, 2),
        "hourly_base": round(hourly_base, 2),
        "regional_hourly": round(regional_hourly, 2),
        "hours_per_week": hours_per_week,
        "hours_per_month": round(hours_per_month, 1),
        "tier": f"{hours_per_week} hours/week",
        "tier_id": "hourly",
        "breakdown": [
            {"label": "National Hourly Rate", "amount": round(hourly_base, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_hourly - hourly_base, 2)},
            {"label": f"{hours_per_week} hrs/week × 4.33", "amount": round(total, 2)}
        ]
    }


def calculate_homemaker_care(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """Calculate homemaker care costs (light assistance)."""
    
    # Get hourly base (homemaker is typically ~85% of skilled care)
    hourly_base = get_base_cost("homemaker_hourly")
    regional_hourly = hourly_base * regional_multiplier
    
    # Default to 10 hours/week for homemaker
    hours_per_week = gcp_answers.get("recommended_hours_per_week", 10)
    hours_per_month = hours_per_week * 4.33
    
    total = regional_hourly * hours_per_month
    
    return {
        "total_monthly": round(total, 2),
        "hourly_base": round(hourly_base, 2),
        "regional_hourly": round(regional_hourly, 2),
        "hours_per_week": hours_per_week,
        "hours_per_month": round(hours_per_month, 1),
        "tier": f"{hours_per_week} hours/week",
        "tier_id": "hourly",
        "breakdown": [
            {"label": "National Hourly Rate", "amount": round(hourly_base, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_hourly - hourly_base, 2)},
            {"label": f"{hours_per_week} hrs/week × 4.33", "amount": round(total, 2)}
        ]
    }


def calculate_home_with_carry(
    gcp_flags: set,
    gcp_answers: dict,
    regional_multiplier: float
) -> Dict[str, Any]:
    """
    Calculate in-home care with family caregiver support.
    
    Assumes family provides ~50% of care hours.
    """
    
    # Get hourly base
    hourly_base = get_base_cost("in_home_hourly")
    regional_hourly = hourly_base * regional_multiplier
    
    # Recommended hours (reduced by ~50% due to family support)
    full_hours = gcp_answers.get("recommended_hours_per_week", 20)
    hours_per_week = full_hours * 0.5  # Family carries half
    hours_per_month = hours_per_week * 4.33
    
    total = regional_hourly * hours_per_month
    
    return {
        "total_monthly": round(total, 2),
        "hourly_base": round(hourly_base, 2),
        "regional_hourly": round(regional_hourly, 2),
        "hours_per_week": round(hours_per_week, 1),
        "hours_per_month": round(hours_per_month, 1),
        "family_hours_per_week": round(full_hours - hours_per_week, 1),
        "tier": f"{round(hours_per_week, 1)} hours/week (with family support)",
        "tier_id": "hourly_with_carry",
        "breakdown": [
            {"label": "National Hourly Rate", "amount": round(hourly_base, 2)},
            {"label": f"Regional Adjustment ({regional_multiplier}x)", "amount": round(regional_hourly - hourly_base, 2)},
            {"label": f"{round(hours_per_week, 1)} hrs/week × 4.33", "amount": round(total, 2)},
            {"label": f"Family provides ~{round(full_hours - hours_per_week, 1)} hrs/week", "amount": 0.0}
        ]
    }
