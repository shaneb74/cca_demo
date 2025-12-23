"""
Cost Planner v3 - Base Costs and Tier Structures

Source: Genworth/CareScout Cost of Care Survey 2024
Updated: December 2025
"""

from typing import Dict, Any

# ==============================================================================
# BASE COSTS (2024 GENWORTH DATA)
# ==============================================================================

BASE_COSTS_2024: Dict[str, Dict[str, Any]] = {
    "assisted_living": {
        "monthly": 5900,
        "source": "Genworth Cost of Care Survey 2024",
        "source_url": "https://investor.genworth.com/news-events/press-releases/detail/982/",
        "annual": 70800,
        "derived": False,
        "notes": "National median for assisted living facility"
    },
    "memory_care": {
        "monthly": 7400,
        "source": "Derived from Genworth 2024 AL median (1.254x premium)",
        "derived": True,
        "derivation": "assisted_living × 1.254",
        "notes": "Typical memory care premium over AL baseline"
    },
    "memory_care_high_acuity": {
        "monthly": 9400,
        "source": "Derived from MC base + high-acuity increment",
        "derived": True,
        "derivation": "memory_care + 2000",
        "notes": "High-acuity memory care with skilled nursing"
    },
    "in_home_care": {
        "hourly": 34.00,
        "source": "Genworth Cost of Care Survey 2024 - Home Health Aide",
        "source_url": "https://investor.genworth.com/news-events/press-releases/detail/982/",
        "derived": False,
        "notes": "National median for home health aide"
    },
    "homemaker_services": {
        "hourly": 33.00,
        "source": "Genworth Cost of Care Survey 2024",
        "source_url": "https://investor.genworth.com/news-events/press-releases/detail/982/",
        "derived": False,
        "notes": "National median for homemaker services"
    },
    "home_carry": {
        "monthly": 4500,
        "source": "National median home ownership cost estimate",
        "derived": False,
        "notes": "Mortgage/rent + property tax + insurance + maintenance (user input)"
    }
}


# ==============================================================================
# ASSISTED LIVING TIER STRUCTURE
# ==============================================================================

AL_TIER_INCREMENTS = {
    "tier_0": {
        "increment": 0,
        "label": "Standard Care",
        "description": "Minimal support, independent with most ADLs",
        "typical_profile": "Independent resident needing minimal assistance"
    },
    "tier_1": {
        "increment": 600,
        "label": "Light Assistance",
        "description": "Medication management OR mild ADL help",
        "typical_profile": "Needs help with 1 ADL or medication management"
    },
    "tier_2": {
        "increment": 1200,
        "label": "Moderate Assistance",
        "description": "Mobility assistance OR moderate ADL help",
        "typical_profile": "Uses walker/wheelchair or needs help with 2+ ADLs"
    },
    "tier_3": {
        "increment": 2000,
        "label": "Enhanced Support",
        "description": "Memory support OR behavioral concerns OR extensive ADLs",
        "typical_profile": "Cognitive decline, behaviors, or 3+ ADLs"
    },
    "tier_4": {
        "increment": 3000,
        "label": "Maximum Support",
        "description": "Multiple high-intensity needs",
        "typical_profile": "Complex care with multiple dependencies"
    }
}


# ==============================================================================
# MEMORY CARE TIER STRUCTURE
# ==============================================================================

MC_TIER_INCREMENTS = {
    "tier_0": {
        "increment": 0,
        "label": "Standard Memory Care",
        "description": "Base secured memory care environment",
        "typical_profile": "Mild-moderate memory decline, secured environment"
    },
    "tier_1": {
        "increment": 400,
        "label": "Light ADL Support",
        "description": "Mild ADL or mobility support",
        "typical_profile": "Memory care + 1 ADL or mobility assistance"
    },
    "tier_2": {
        "increment": 900,
        "label": "Moderate ADL Support",
        "description": "Moderate ADLs or mobility needs",
        "typical_profile": "Memory care + 2 ADLs or significant mobility needs"
    },
    "tier_3": {
        "increment": 1500,
        "label": "Enhanced Behavioral Support",
        "description": "Behavioral concerns or complex ADLs",
        "typical_profile": "Challenging behaviors or 3+ ADLs"
    },
    "tier_4": {
        "increment": 2200,
        "label": "High-Acuity Care",
        "description": "Severe behaviors or hands-on care",
        "typical_profile": "Intensive supervision, severe behaviors, or total ADL dependence"
    }
}


# ==============================================================================
# ADD-ON CAPS
# ==============================================================================

# Maximum single add-on as percentage of regional base
MAX_ADDON_PCT = 0.15  # 15% of regional base

# Absolute maximum add-on (safety cap)
MAX_ADDON_ABSOLUTE = 800

# Individual add-on amounts (as fractions of max)
ADDON_AMOUNTS = {
    "fall_monitoring": 0.50,      # 50% of max addon
    "chronic_complexity": 0.375,  # 37.5% of max addon
    "incontinence_care": 0.3125   # 31.25% of max addon
}


# ==============================================================================
# CONFIDENCE RANGES
# ==============================================================================

CONFIDENCE_RANGES = {
    "high": 0.07,     # ±7%
    "medium": 0.12,   # ±12%
    "low": 0.20       # ±20%
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_base_cost(care_type: str, cost_type: str = "monthly") -> float:
    """
    Get base cost for a care type.
    
    Args:
        care_type: "assisted_living", "memory_care", "memory_care_high_acuity", 
                   "in_home_care", "homemaker_services", "home_carry"
        cost_type: "monthly" or "hourly"
    
    Returns:
        Base cost in dollars
    """
    if care_type not in BASE_COSTS_2024:
        raise ValueError(f"Unknown care type: {care_type}")
    
    cost_data = BASE_COSTS_2024[care_type]
    
    if cost_type not in cost_data:
        raise ValueError(f"Care type {care_type} does not have {cost_type} cost")
    
    return cost_data[cost_type]


def get_tier_increment(care_type: str, tier: str, regional_multiplier: float = 1.0) -> float:
    """
    Get tier increment scaled by regional multiplier.
    
    Args:
        care_type: "assisted_living" or "memory_care"
        tier: "tier_0" through "tier_4"
        regional_multiplier: Regional cost adjustment multiplier
    
    Returns:
        Tier increment in dollars (scaled)
    """
    if care_type == "assisted_living":
        tier_config = AL_TIER_INCREMENTS.get(tier)
    elif care_type in ["memory_care", "memory_care_high_acuity"]:
        tier_config = MC_TIER_INCREMENTS.get(tier)
    else:
        raise ValueError(f"Tier increments not defined for care type: {care_type}")
    
    if not tier_config:
        raise ValueError(f"Unknown tier: {tier}")
    
    # Scale increment by regional multiplier
    return tier_config["increment"] * regional_multiplier


def get_tier_config(care_type: str, tier: str) -> dict:
    """Get tier configuration details."""
    if care_type == "assisted_living":
        return AL_TIER_INCREMENTS.get(tier, {})
    elif care_type in ["memory_care", "memory_care_high_acuity"]:
        return MC_TIER_INCREMENTS.get(tier, {})
    else:
        return {}


def is_base_cost_derived(care_type: str) -> bool:
    """Check if base cost is derived vs published."""
    return BASE_COSTS_2024.get(care_type, {}).get("derived", False)


def get_base_cost_source(care_type: str) -> dict:
    """
    Get source citation for base cost.
    
    Returns:
        {
            "name": str,
            "url": str,
            "notes": str (optional)
        }
    """
    cost_data = BASE_COSTS_2024.get(care_type, {})
    return {
        "name": cost_data.get("source", "Unknown"),
        "url": cost_data.get("source_url", ""),
        "notes": cost_data.get("notes", "")
    }
