"""
Comparison View Cost Calculations

Phase 2 enhancement: Care-type-specific cost calculations for comparison view.
Supports facility care (AL, MC, MC-HA) and in-home care with different modifiers.

ARCHITECTURE:
- Reuses existing base rates, regional multipliers, and flag system
- Extends modifier logic to support per-care-type percentages
- Adds home carry cost with regional scaling
- Returns structured breakdown payloads for UI rendering

DOES NOT:
- Duplicate existing rate/regional data structures
- Modify MCIP contracts (Phase 3)
- Change product routing
"""

from dataclasses import dataclass
from typing import Any

from core.mcip import MCIP
from products.cost_planner_v2.utils.regional_data import RegionalDataProvider

# ==============================================================================
# BASE RATES
# ==============================================================================

# Facility base rates (monthly)
# Source: Genworth 2024 Cost of Care Survey
# Updated: December 2025 - Genworth annual median $70,800 = $5,900/month
FACILITY_BASE_RATES = {
    "assisted_living": 5900,  # National median (Genworth 2024: $70,800/year)
    "memory_care": 7400,  # Derived: AL × 1.254 (typical MC premium)
    "memory_care_high_acuity": 9400,  # Derived: MC + high-acuity increment
}

# In-Home Care hourly rate (national baseline)
# Scaled by regional multiplier, then multiplied by hours/month
# Source: Genworth 2024 Cost of Care Survey
INHOME_HOURLY_BASE = 34.00  # National median for home health aide (Genworth 2024)

# Home Carry Cost baseline (monthly)
# Mortgage/rent + property tax + insurance + maintenance
HOME_CARRY_BASE = 4500.00  # National median home ownership cost


# ==============================================================================
# CARE-TYPE-SPECIFIC MODIFIER TABLES
# ==============================================================================

# Modifier percentages by care type and flag
# Labels are consistent across types; only percentages differ
# Facility types may have different care delivery models than in-home

CARE_TYPE_MODIFIERS = {
    # ASSISTED LIVING
    "assisted_living": {
        "memory_support": {"pct": 0.20, "label": "Memory Care Support"},
        "mobility_limited": {"pct": 0.15, "label": "Mobility/Transfer Assistance"},
        "adl_support_high": {"pct": 0.10, "label": "Extensive ADL Support"},
        "medication_management": {"pct": 0.08, "label": "Medication Management"},
        "behavioral_concerns": {"pct": 0.12, "label": "Behavioral Support"},
        "falls_risk": {"pct": 0.08, "label": "Fall Prevention & Monitoring"},
        "chronic_conditions": {"pct": 0.10, "label": "Chronic Condition Management"},
    },
    # MEMORY CARE
    "memory_care": {
        "memory_support": {"pct": 0.15, "label": "Memory Care Support"},  # Lower - baseline includes memory care
        "mobility_limited": {"pct": 0.12, "label": "Mobility/Transfer Assistance"},
        "adl_support_high": {"pct": 0.08, "label": "Extensive ADL Support"},
        "medication_management": {"pct": 0.06, "label": "Medication Management"},
        "behavioral_concerns": {"pct": 0.10, "label": "Behavioral Support"},
        "falls_risk": {"pct": 0.06, "label": "Fall Prevention & Monitoring"},
        "chronic_conditions": {"pct": 0.08, "label": "Chronic Condition Management"},
    },
    # MEMORY CARE HIGH ACUITY
    "memory_care_high_acuity": {
        "memory_support": {"pct": 0.10, "label": "Memory Care Support"},  # Even lower - high acuity baseline
        "mobility_limited": {"pct": 0.10, "label": "Mobility/Transfer Assistance"},
        "adl_support_high": {"pct": 0.06, "label": "Extensive ADL Support"},
        "medication_management": {"pct": 0.05, "label": "Medication Management"},
        "behavioral_concerns": {"pct": 0.08, "label": "Behavioral Support"},
        "falls_risk": {"pct": 0.05, "label": "Fall Prevention & Monitoring"},
        "chronic_conditions": {"pct": 0.06, "label": "Chronic Condition Management"},
        "high_acuity_tier": {"pct": 0.25, "label": "High-Acuity Intensive Care"},  # Always applied
    },
    # IN-HOME CARE
    "in_home_care": {
        "memory_support": {"pct": 0.25, "label": "Memory Care Support"},  # Higher - requires specialized training
        "mobility_limited": {"pct": 0.20, "label": "Mobility/Transfer Assistance"},  # Higher - equipment/2-person lifts
        "adl_support_high": {"pct": 0.15, "label": "Extensive ADL Support"},
        "medication_management": {"pct": 0.10, "label": "Medication Management"},
        "behavioral_concerns": {"pct": 0.15, "label": "Behavioral Support"},
        "falls_risk": {"pct": 0.10, "label": "Fall Prevention & Monitoring"},
        "chronic_conditions": {"pct": 0.12, "label": "Chronic Condition Management"},
    },
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class BreakdownLine:
    """Single line item in cost breakdown."""
    label: str
    value: float
    pct: float | None = None  # Percentage if applicable (e.g., 0.20 for 20%)
    applied: bool = True  # Whether this line is included in total


@dataclass
class ScenarioBreakdown:
    """Complete breakdown for one care scenario."""
    care_type: str
    location_label: str
    monthly_total: float
    annual_total: float
    three_year_total: float
    lines: list[BreakdownLine]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_home_carry_effective(zip_code: str | None, user_override: float | None = None) -> float:
    """Calculate effective home carry cost with regional scaling.
    
    Args:
        zip_code: ZIP code for regional adjustment
        user_override: User-specified home carry amount (overrides base if provided)
        
    Returns:
        Monthly home carry cost (regionally adjusted)
    """
    # Start with user override or base
    base_amount = user_override if user_override is not None else HOME_CARRY_BASE

    # Apply regional multiplier (same as care costs)
    regional = RegionalDataProvider.get_multiplier(zip_code=zip_code)

    # Home costs scale similarly to care costs but may be less sensitive
    # Use a dampened multiplier (50% of care multiplier deviation from 1.0)
    # Example: If care multiplier is 1.30 (+30%), home multiplier is 1.15 (+15%)
    deviation = regional.multiplier - 1.0
    dampened_multiplier = 1.0 + (deviation * 0.5)

    effective_amount = base_amount * dampened_multiplier

    return round(effective_amount, 2)


def get_active_flags() -> list[str]:
    """Get active flags from GCP recommendation.
    
    Returns:
        List of flag IDs that are currently active
    """
    gcp_rec = MCIP.get_care_recommendation()
    if not gcp_rec or not hasattr(gcp_rec, "flags"):
        return []

    # Extract flag IDs
    flags = []
    for flag in gcp_rec.flags:
        if isinstance(flag, dict):
            flag_id = flag.get("id")
            if flag_id:
                flags.append(flag_id)
        elif isinstance(flag, str):
            flags.append(flag)

    return flags


def get_modifier_pct(care_type: str, flag_id: str) -> float:
    """Get modifier percentage for a specific care type and flag.
    
    Args:
        care_type: Care type (assisted_living, memory_care, memory_care_high_acuity, in_home_care)
        flag_id: Flag identifier
        
    Returns:
        Modifier percentage as decimal (e.g., 0.20 for 20%)
    """
    care_modifiers = CARE_TYPE_MODIFIERS.get(care_type, {})
    modifier_info = care_modifiers.get(flag_id, {})
    return modifier_info.get("pct", 0.0)


def get_modifier_label(care_type: str, flag_id: str) -> str:
    """Get consistent modifier label across care types.
    
    Args:
        care_type: Care type
        flag_id: Flag identifier
        
    Returns:
        Human-readable label for the modifier
    """
    care_modifiers = CARE_TYPE_MODIFIERS.get(care_type, {})
    modifier_info = care_modifiers.get(flag_id, {})
    return modifier_info.get("label", flag_id.replace("_", " ").title())


# ==============================================================================
# CALCULATION FUNCTIONS
# ==============================================================================

def calculate_facility_scenario(
    care_type: str,
    zip_code: str | None,
    keep_home: bool,
    home_carry_override: float | None = None
) -> ScenarioBreakdown:
    """Calculate facility care scenario (AL, MC, MC-HA).
    
    Args:
        care_type: assisted_living, memory_care, or memory_care_high_acuity
        zip_code: ZIP code for regional adjustment
        keep_home: Whether to include home carry cost
        home_carry_override: User-specified home carry amount
        
    Returns:
        ScenarioBreakdown with complete calculation breakdown
    """
    lines = []

    # 1. Base cost
    base_cost = FACILITY_BASE_RATES.get(care_type, 4500)
    lines.append(BreakdownLine(
        label="Base Cost",
        value=base_cost,
        applied=True
    ))

    # 2. Regional adjustment
    regional = RegionalDataProvider.get_multiplier(zip_code=zip_code)
    regional_adj = base_cost * (regional.multiplier - 1.0)
    regional_pct = (regional.multiplier - 1.0) * 100

    if abs(regional_adj) > 0.01:
        sign = "+" if regional_adj > 0 else ""
        lines.append(BreakdownLine(
            label=f"Regional Adjustment ({sign}{regional_pct:.0f}%)",
            value=regional_adj,
            pct=regional.multiplier - 1.0,
            applied=True
        ))

    # Running total after base + regional
    running_total = base_cost * regional.multiplier

    # 3. Care modifiers (cumulative application)
    active_flags = get_active_flags()

    # Standard modifiers
    for flag_id in ["memory_support", "mobility_limited", "adl_support_high",
                    "medication_management", "behavioral_concerns", "falls_risk",
                    "chronic_conditions"]:
        if flag_id in active_flags:
            pct = get_modifier_pct(care_type, flag_id)
            if pct > 0:
                amount = running_total * pct
                label = get_modifier_label(care_type, flag_id)
                lines.append(BreakdownLine(
                    label=f"{label} (+{pct*100:.0f}%)",
                    value=amount,
                    pct=pct,
                    applied=True
                ))
                running_total += amount

    # High-acuity tier adjustment (always applied for memory_care_high_acuity)
    if care_type == "memory_care_high_acuity":
        pct = 0.25
        amount = running_total * pct
        lines.append(BreakdownLine(
            label=f"High-Acuity Intensive Care (+{pct*100:.0f}%)",
            value=amount,
            pct=pct,
            applied=True
        ))
        running_total += amount

    # 4. Home carry cost (optional)
    home_carry_effective = get_home_carry_effective(zip_code, home_carry_override)
    lines.append(BreakdownLine(
        label="Home Carry Cost",
        value=home_carry_effective,
        applied=keep_home
    ))

    if keep_home:
        running_total += home_carry_effective

    # Final totals
    monthly_total = round(running_total, 0)
    annual_total = round(monthly_total * 12, 0)
    three_year_total = round(annual_total * 3, 0)

    return ScenarioBreakdown(
        care_type=care_type,
        location_label=regional.region_name,
        monthly_total=monthly_total,
        annual_total=annual_total,
        three_year_total=three_year_total,
        lines=lines
    )


def calculate_inhome_scenario(
    zip_code: str | None,
    hours_per_day: float = 8.0,
    home_carry_override: float | None = None
) -> ScenarioBreakdown:
    """Calculate in-home care scenario.
    
    Args:
        zip_code: ZIP code for regional adjustment
        hours_per_day: Hours of care per day (default 8)
        home_carry_override: User-specified home carry amount
        
    Returns:
        ScenarioBreakdown with complete calculation breakdown
    """
    lines = []

    # 1. Hourly rate (regionally adjusted)
    regional = RegionalDataProvider.get_multiplier(zip_code=zip_code)
    hourly_rate = INHOME_HOURLY_BASE * regional.multiplier

    # 2. Hours per month (30.4 days average)
    hours_per_month = hours_per_day * 30.4

    # 3. Base care cost
    base_cost = hourly_rate * hours_per_month
    lines.append(BreakdownLine(
        label=f"Base Cost ({hours_per_day}hrs/day × ${hourly_rate:.2f}/hr)",
        value=base_cost,
        applied=True
    ))

    # 4. Regional adjustment (already applied to hourly rate, show for transparency)
    regional_pct = (regional.multiplier - 1.0) * 100
    if abs(regional_pct) > 0.01:
        regional_adj = (INHOME_HOURLY_BASE * hours_per_month) * (regional.multiplier - 1.0)
        sign = "+" if regional_adj > 0 else ""
        lines.append(BreakdownLine(
            label=f"Regional Adjustment ({sign}{regional_pct:.0f}%)",
            value=regional_adj,
            pct=regional.multiplier - 1.0,
            applied=True
        ))

    running_total = base_cost

    # 5. Care modifiers (cumulative application)
    active_flags = get_active_flags()
    care_type = "in_home_care"

    for flag_id in ["memory_support", "mobility_limited", "adl_support_high",
                    "medication_management", "behavioral_concerns", "falls_risk",
                    "chronic_conditions"]:
        if flag_id in active_flags:
            pct = get_modifier_pct(care_type, flag_id)
            if pct > 0:
                amount = running_total * pct
                label = get_modifier_label(care_type, flag_id)
                lines.append(BreakdownLine(
                    label=f"{label} (+{pct*100:.0f}%)",
                    value=amount,
                    pct=pct,
                    applied=True
                ))
                running_total += amount

    # 6. Home carry cost (always included for in-home)
    home_carry_effective = get_home_carry_effective(zip_code, home_carry_override)
    lines.append(BreakdownLine(
        label="Home Carry Cost",
        value=home_carry_effective,
        applied=True
    ))
    running_total += home_carry_effective

    # Final totals
    monthly_total = round(running_total, 0)
    annual_total = round(monthly_total * 12, 0)
    three_year_total = round(annual_total * 3, 0)

    return ScenarioBreakdown(
        care_type="in_home_care",
        location_label=regional.region_name,
        monthly_total=monthly_total,
        annual_total=annual_total,
        three_year_total=three_year_total,
        lines=lines
    )


# ==============================================================================
# BREAKDOWN TO DICT (for UI rendering)
# ==============================================================================

def breakdown_to_dict(breakdown: ScenarioBreakdown) -> dict[str, Any]:
    """Convert ScenarioBreakdown to dict for JSON serialization and UI rendering.
    
    Args:
        breakdown: ScenarioBreakdown object
        
    Returns:
        Dictionary representation
    """
    return {
        "care_type": breakdown.care_type,
        "location_label": breakdown.location_label,
        "monthly_total": breakdown.monthly_total,
        "annual_total": breakdown.annual_total,
        "three_year_total": breakdown.three_year_total,
        "lines": [
            {
                "label": line.label,
                "value": line.value,
                "pct": line.pct,
                "applied": line.applied
            }
            for line in breakdown.lines
        ]
    }
