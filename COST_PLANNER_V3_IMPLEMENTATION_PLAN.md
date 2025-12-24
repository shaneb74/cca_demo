# Cost Planner v3 - Implementation Plan

**Version:** 3.0.0  
**Date:** December 22, 2025  
**Status:** Design Phase  
**Target:** Q1 2026

---

## Executive Summary

This plan replaces Cost Planner v2's additive percentage modifiers with a **tier-based, clinically-informed cost model** that:
- Uses verified 2024 Genworth base costs ($5,900 AL, $34/hr HHA)
- Assigns care tiers based on GCP flags and answers
- Applies fixed dollar increments scaled by region
- Prevents double-counting (e.g., Memory Care base already includes memory support)
- Produces low/likely/high estimates with explanations

**Implementation Timeline:** 8-10 weeks (3 phases)

---

## Phase 1: Core Architecture (Weeks 1-3)

### 1.1 Updated Base Costs

```python
# products/cost_planner_v3/constants.py

BASE_COSTS_2024 = {
    "assisted_living": {
        "monthly": 5900,
        "source": "Genworth Cost of Care Survey 2024",
        "source_url": "https://www.genworth.com/aging-and-you/finances/cost-of-care.html"
    },
    "memory_care": {
        "monthly": 7400,  # Derived: AL × 1.254
        "source": "Derived from Genworth 2024 AL median (1.25x premium)",
        "derived": True
    },
    "memory_care_high_acuity": {
        "monthly": 9400,  # Derived: MC + $2000
        "source": "Derived from MC base + high-acuity increment",
        "derived": True
    },
    "in_home_care": {
        "hourly": 34.00,
        "source": "Genworth Cost of Care Survey 2024 - Home Health Aide",
        "source_url": "https://www.genworth.com/aging-and-you/finances/cost-of-care.html"
    },
    "homemaker_services": {
        "hourly": 33.00,
        "source": "Genworth Cost of Care Survey 2024",
        "source_url": "https://www.genworth.com/aging-and-you/finances/cost-of-care.html"
    },
    "home_carry": {
        "monthly": 4500,
        "source": "National median home ownership cost (input variable)"
    }
}
```

---

### 1.2 Tier-Based Pricing Structure

#### Assisted Living Tiers

```python
AL_TIER_INCREMENTS = {
    "tier_0": {
        "increment": 0,
        "label": "Standard Care",
        "description": "Minimal support, independent with most ADLs"
    },
    "tier_1": {
        "increment": 600,
        "label": "Light Assistance",
        "description": "Medication management OR mild ADL help"
    },
    "tier_2": {
        "increment": 1200,
        "label": "Moderate Assistance",
        "description": "Mobility assistance OR moderate ADL help"
    },
    "tier_3": {
        "increment": 2000,
        "label": "Enhanced Support",
        "description": "Memory support OR behavioral concerns OR extensive ADLs"
    },
    "tier_4": {
        "increment": 3000,
        "label": "Maximum Support",
        "description": "Multiple high-intensity needs"
    }
}
```

#### Memory Care Tiers

```python
MC_TIER_INCREMENTS = {
    "tier_0": {
        "increment": 0,
        "label": "Standard Memory Care",
        "description": "Base secured memory care environment"
    },
    "tier_1": {
        "increment": 400,
        "label": "Light ADL Support",
        "description": "Mild ADL or mobility support"
    },
    "tier_2": {
        "increment": 900,
        "label": "Moderate ADL Support",
        "description": "Moderate ADLs or mobility needs"
    },
    "tier_3": {
        "increment": 1500,
        "label": "Enhanced Behavioral Support",
        "description": "Behavioral concerns or complex ADLs"
    },
    "tier_4": {
        "increment": 2200,
        "label": "High-Acuity Care",
        "description": "Severe behaviors or hands-on care"
    }
}
```

---

### 1.3 Tier Assignment Rules

**Critical: Explicit mapping from GCP flags to care tiers**

```python
# products/cost_planner_v3/tier_assignment.py

def assign_assisted_living_tier(gcp_flags: set, gcp_answers: dict) -> str:
    """
    Assign AL tier based on GCP flags and answers.
    Returns: "tier_0" | "tier_1" | "tier_2" | "tier_3" | "tier_4"
    """
    
    # TIER 4: Multiple high-intensity needs
    tier_4_conditions = [
        "severe_cognitive_risk" in gcp_flags,
        "high_mobility_dependence" in gcp_flags,
        "behavioral_concerns" in gcp_flags,
        gcp_answers.get("badls_count", 0) >= 3,
        "continuous_supervision" in gcp_flags
    ]
    if sum(tier_4_conditions) >= 2:
        return "tier_4"
    
    # TIER 3: Memory support OR behavioral OR extensive ADLs
    if any([
        "severe_cognitive_risk" in gcp_flags,
        "moderate_cognitive_decline" in gcp_flags and gcp_answers.get("badls_count", 0) >= 2,
        "behavioral_concerns" in gcp_flags,
        gcp_answers.get("badls_count", 0) >= 3,
        "high_dependence" in gcp_flags
    ]):
        return "tier_3"
    
    # TIER 2: Mobility assistance OR moderate ADL help
    if any([
        "high_mobility_dependence" in gcp_flags,
        "transfer_assistance_1person" in gcp_flags,
        gcp_answers.get("badls_count", 0) >= 2,
        "incontinence_management" in gcp_flags,
        "falls_multiple" in gcp_flags
    ]):
        return "tier_2"
    
    # TIER 1: Medication management OR mild ADL help
    if any([
        gcp_answers.get("meds_complexity") in ["moderate", "complex"],
        gcp_answers.get("badls_count", 0) == 1,
        gcp_answers.get("iadls_count", 0) >= 4,
        "mild_cognitive_decline" in gcp_flags
    ]):
        return "tier_1"
    
    # TIER 0: Minimal support (default)
    return "tier_0"


def assign_memory_care_tier(gcp_flags: set, gcp_answers: dict) -> str:
    """
    Assign MC tier based on GCP flags and answers.
    Memory care baseline already includes secured environment + memory support.
    Returns: "tier_0" | "tier_1" | "tier_2" | "tier_3" | "tier_4"
    """
    
    # TIER 4: Severe behaviors or hands-on care
    if any([
        "behavioral_concerns" in gcp_flags and gcp_answers.get("behaviors_count", 0) >= 3,
        "continuous_supervision" in gcp_flags and "high_dependence" in gcp_flags,
        gcp_answers.get("badls_count", 0) >= 4,
        "transfer_lift_required" in gcp_flags
    ]):
        return "tier_4"
    
    # TIER 3: Behavioral concerns or complex ADLs
    if any([
        "behavioral_concerns" in gcp_flags,
        gcp_answers.get("badls_count", 0) >= 3,
        "transfer_assistance_2person" in gcp_flags,
        "high_dependence" in gcp_flags
    ]):
        return "tier_3"
    
    # TIER 2: Moderate ADLs or mobility needs
    if any([
        gcp_answers.get("badls_count", 0) >= 2,
        "high_mobility_dependence" in gcp_flags,
        "incontinence_management" in gcp_flags
    ]):
        return "tier_2"
    
    # TIER 1: Mild ADL or mobility support
    if any([
        gcp_answers.get("badls_count", 0) == 1,
        "transfer_assistance_1person" in gcp_flags,
        "moderate_mobility" in gcp_flags
    ]):
        return "tier_1"
    
    # TIER 0: Standard MC (baseline)
    return "tier_0"


def should_recommend_memory_care_instead_of_al(gcp_flags: set, gcp_answers: dict) -> bool:
    """
    Determine if resident needs Memory Care instead of Assisted Living.
    This is tier overflow logic.
    """
    
    # Diagnosed dementia + any complexity
    if "memory_care_dx" in gcp_flags and any([
        gcp_answers.get("badls_count", 0) >= 2,
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
    if gcp_answers.get("behaviors_count", 0) >= 3:
        return True
    
    return False


def should_recommend_high_acuity_mc(gcp_flags: set, gcp_answers: dict, mc_tier: str) -> bool:
    """
    Determine if High-Acuity Memory Care is needed.
    """
    
    # MC Tier 4 + skilled nursing indicators
    if mc_tier == "tier_4" and any([
        "transfer_lift_required" in gcp_flags,
        gcp_answers.get("incontinence") == "complete",
        "continuous_supervision" in gcp_flags and gcp_answers.get("behaviors_count", 0) >= 2
    ]):
        return True
    
    return False
```

---

### 1.4 Regional Scaling

**Key change: Scale tier increments by regional multiplier**

```python
# products/cost_planner_v3/regional_calc.py

def calculate_tiered_cost(
    care_type: str,
    tier: str,
    regional_multiplier: float,
    gcp_flags: set,
    gcp_answers: dict
) -> dict:
    """
    Calculate total cost with regional scaling and tier increments.
    
    Returns:
        {
            "base_cost": float,
            "regional_base": float,
            "tier_increment": float,
            "add_ons": list[dict],
            "total": float,
            "breakdown": list[dict]
        }
    """
    
    # 1. Get base cost
    base = BASE_COSTS_2024[care_type]["monthly"]
    
    # 2. Apply regional multiplier to base
    regional_base = base * regional_multiplier
    
    # 3. Get tier increment structure
    if care_type == "assisted_living":
        tier_config = AL_TIER_INCREMENTS[tier]
    elif care_type in ["memory_care", "memory_care_high_acuity"]:
        tier_config = MC_TIER_INCREMENTS[tier]
    else:
        tier_config = {"increment": 0, "label": "Standard", "description": ""}
    
    # 4. Scale tier increment by regional multiplier
    tier_increment = tier_config["increment"] * regional_multiplier
    
    # 5. Calculate add-ons (capped)
    add_ons = calculate_add_ons(care_type, gcp_flags, gcp_answers, regional_base)
    add_on_total = sum(a["amount"] for a in add_ons)
    
    # 6. Total
    total = regional_base + tier_increment + add_on_total
    
    # 7. Breakdown for UI
    breakdown = [
        {
            "label": f"Base {care_type.replace('_', ' ').title()}",
            "value": base,
            "category": "base"
        },
        {
            "label": f"Regional Adjustment ({regional_multiplier}x)",
            "value": regional_base - base,
            "category": "regional"
        },
        {
            "label": f"Care Tier: {tier_config['label']}",
            "value": tier_increment,
            "category": "tier",
            "description": tier_config["description"]
        }
    ]
    
    # Add individual add-ons to breakdown
    for add_on in add_ons:
        breakdown.append({
            "label": add_on["label"],
            "value": add_on["amount"],
            "category": "add_on",
            "description": add_on.get("description", "")
        })
    
    return {
        "base_cost": base,
        "regional_base": regional_base,
        "tier_increment": tier_increment,
        "add_ons": add_ons,
        "total": total,
        "breakdown": breakdown
    }
```

---

### 1.5 Add-On Logic (Capped)

```python
# products/cost_planner_v3/add_ons.py

def calculate_add_ons(
    care_type: str,
    gcp_flags: set,
    gcp_answers: dict,
    regional_base: float
) -> list[dict]:
    """
    Calculate capped add-ons for secondary care needs.
    
    Add-ons are used for:
    - Fall monitoring (when not primary tier driver)
    - Chronic condition complexity (when materially affecting care)
    - Incontinence care (when not captured in tier)
    
    Returns: List of {"label": str, "amount": float, "description": str}
    """
    
    add_ons = []
    
    # Maximum single add-on cap
    MAX_ADDON = min(800, regional_base * 0.15)
    
    # Fall monitoring add-on (if falls present but not primary driver)
    if "falls_multiple" in gcp_flags:
        add_ons.append({
            "label": "Fall Prevention Monitoring",
            "amount": min(400, MAX_ADDON * 0.5),
            "description": "Enhanced monitoring and prevention protocols"
        })
    
    # Chronic condition complexity (only when affecting care delivery)
    if should_apply_chronic_addon(gcp_flags, gcp_answers):
        add_ons.append({
            "label": "Chronic Condition Management",
            "amount": min(300, MAX_ADDON * 0.375),
            "description": "Coordination and monitoring for complex chronic conditions"
        })
    
    # Incontinence care (if not already captured in tier)
    if "incontinence_management" in gcp_flags and gcp_answers.get("badls_count", 0) < 2:
        add_ons.append({
            "label": "Incontinence Care",
            "amount": min(250, MAX_ADDON * 0.3125),
            "description": "Regular assistance and supplies"
        })
    
    # Cap total add-ons
    total_addons = sum(a["amount"] for a in add_ons)
    if total_addons > MAX_ADDON:
        # Proportionally reduce all add-ons to fit cap
        scale_factor = MAX_ADDON / total_addons
        for add_on in add_ons:
            add_on["amount"] = add_on["amount"] * scale_factor
    
    return add_ons


def should_apply_chronic_addon(gcp_flags: set, gcp_answers: dict) -> bool:
    """
    Determine if chronic conditions justify cost add-on.
    
    Chronic conditions increase cost when they:
    - Increase ADL support needs
    - Require medication coordination
    - Need active symptom monitoring
    - Affect mobility or safety
    """
    
    chronic_count = len(gcp_answers.get("chronic_conditions", []))
    
    # Multiple chronic conditions + medication complexity
    if chronic_count >= 3 and gcp_answers.get("meds_complexity") in ["moderate", "complex"]:
        return True
    
    # Chronic conditions + falls (indicating instability)
    if chronic_count >= 2 and "falls_multiple" in gcp_flags:
        return True
    
    # Specific high-impact chronic conditions
    high_impact_conditions = [
        "parkinsons",  # Affects mobility, ADLs
        "copd",        # Affects mobility, requires monitoring
        "heart_disease",  # Requires monitoring
        "stroke"       # Often affects ADLs, mobility
    ]
    
    if any(c in gcp_answers.get("chronic_conditions", []) for c in high_impact_conditions):
        if gcp_answers.get("badls_count", 0) >= 1:  # Chronic condition affecting function
            return True
    
    return False
```

---

### 1.6 Range Calculation (Confidence Intervals)

```python
# products/cost_planner_v3/ranges.py

def calculate_cost_range(
    total: float,
    gcp_flags: set,
    gcp_answers: dict,
    care_type: str
) -> dict:
    """
    Calculate low/likely/high estimates with confidence.
    
    Returns:
        {
            "low": float,
            "likely": float,
            "high": float,
            "confidence": "high" | "medium" | "low",
            "range_explanation": str
        }
    """
    
    # Determine base range percentage
    if has_high_uncertainty(gcp_flags, gcp_answers, care_type):
        range_pct = 0.20  # ±20%
        confidence = "low"
    elif has_moderate_uncertainty(gcp_flags, gcp_answers, care_type):
        range_pct = 0.12  # ±12%
        confidence = "medium"
    else:
        range_pct = 0.07  # ±7%
        confidence = "high"
    
    low = total * (1 - range_pct)
    likely = total
    high = total * (1 + range_pct)
    
    # Generate explanation
    explanation = generate_range_explanation(gcp_flags, gcp_answers, care_type, confidence)
    
    return {
        "low": round(low, 2),
        "likely": round(likely, 2),
        "high": round(high, 2),
        "confidence": confidence,
        "range_explanation": explanation
    }


def has_high_uncertainty(gcp_flags: set, gcp_answers: dict, care_type: str) -> bool:
    """Wide ranges (±20%) applied when:"""
    
    # Severe behavioral concerns
    if "behavioral_concerns" in gcp_flags and gcp_answers.get("behaviors_count", 0) >= 3:
        return True
    
    # High-acuity memory care
    if care_type == "memory_care_high_acuity":
        return True
    
    # 2-person transfer + multiple ADLs
    if "transfer_assistance_2person" in gcp_flags and gcp_answers.get("badls_count", 0) >= 3:
        return True
    
    # In-home with continuous supervision
    if care_type == "in_home_care" and "continuous_supervision" in gcp_flags:
        return True
    
    return False


def has_moderate_uncertainty(gcp_flags: set, gcp_answers: dict, care_type: str) -> bool:
    """Medium ranges (±12%) applied when:"""
    
    # Memory care with behaviors
    if care_type in ["memory_care", "memory_care_high_acuity"] and "behavioral_concerns" in gcp_flags:
        return True
    
    # Multiple falls + mobility concerns
    if "falls_multiple" in gcp_flags and "high_mobility_dependence" in gcp_flags:
        return True
    
    # Chronic instability (multiple conditions + falls)
    if len(gcp_answers.get("chronic_conditions", [])) >= 3 and "falls_multiple" in gcp_flags:
        return True
    
    return False


def generate_range_explanation(gcp_flags: set, gcp_answers: dict, care_type: str, confidence: str) -> str:
    """Generate human-readable explanation for range width."""
    
    if confidence == "high":
        return "Cost range is narrow because care needs are stable and predictable."
    
    elif confidence == "medium":
        reasons = []
        if "behavioral_concerns" in gcp_flags:
            reasons.append("behavioral needs may vary")
        if "falls_multiple" in gcp_flags:
            reasons.append("fall risk requires enhanced monitoring")
        if len(gcp_answers.get("chronic_conditions", [])) >= 3:
            reasons.append("multiple chronic conditions may require additional oversight")
        
        return f"Cost range is moderate because {' and '.join(reasons)}."
    
    else:  # low confidence
        reasons = []
        if gcp_answers.get("behaviors_count", 0) >= 3:
            reasons.append("significant behavioral needs require intensive support")
        if care_type == "memory_care_high_acuity":
            reasons.append("high-acuity care varies by provider")
        if "transfer_assistance_2person" in gcp_flags:
            reasons.append("2-person transfers require specialized staffing")
        if "continuous_supervision" in gcp_flags and care_type == "in_home_care":
            reasons.append("24/7 in-home care has wide market variation")
        
        return f"Cost range is wide because {' and '.join(reasons)}."
```

---

## Phase 2: Integration & Testing (Weeks 4-7)

### 2.1 GCP Integration

```python
# products/cost_planner_v3/gcp_integration.py

def prepare_gcp_context(gcp_outcome: dict) -> dict:
    """
    Extract and normalize GCP data for cost calculation.
    
    Args:
        gcp_outcome: Raw GCP outcome from derive_outcome()
    
    Returns:
        {
            "flags": set,
            "answers": dict,
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
    
    # Normalize answers for tier logic
    normalized = {
        "badls_count": len(badls_list) if isinstance(badls_list, list) else 0,
        "iadls_count": len(iadls_list) if isinstance(iadls_list, list) else 0,
        "behaviors_count": len(behaviors_list) if isinstance(behaviors_list, list) else 0,
        "chronic_conditions": answers.get("chronic_conditions", []),
        "meds_complexity": answers.get("meds_complexity"),
        "incontinence": answers.get("incontinence"),
        "safe_alone": answers.get("safe_alone"),
        "transfers": answers.get("transfers"),
        "mobility": answers.get("mobility")
    }
    
    return {
        "flags": flags,
        "answers": normalized,
        "tier": gcp_outcome.get("tier"),
        "score": gcp_outcome.get("score", 0)
    }
```

### 2.2 Main Cost Calculator

```python
# products/cost_planner_v3/calculator.py

def calculate_care_costs(
    gcp_outcome: dict,
    regional_multiplier: float,
    location: dict
) -> dict:
    """
    Main entry point for v3 cost calculation.
    
    Args:
        gcp_outcome: GCP derive_outcome() result
        regional_multiplier: From RegionalDataProvider
        location: {"city": str, "state": str, "zip": str}
    
    Returns:
        {
            "care_type": str,
            "tier": str,
            "base_cost": float,
            "regional_base": float,
            "tier_increment": float,
            "add_ons": list,
            "total": float,
            "range": dict,
            "breakdown": list,
            "explanation": str,
            "recommendations": list
        }
    """
    
    # 1. Prepare GCP context
    context = prepare_gcp_context(gcp_outcome)
    
    # 2. Determine care type and tier
    gcp_tier = context["tier"]
    
    # Handle tier overflow (AL → MC)
    if gcp_tier == "assisted_living":
        if should_recommend_memory_care_instead_of_al(context["flags"], context["answers"]):
            care_type = "memory_care"
            tier = assign_memory_care_tier(context["flags"], context["answers"])
        else:
            care_type = "assisted_living"
            tier = assign_assisted_living_tier(context["flags"], context["answers"])
    
    elif gcp_tier == "memory_care":
        tier = assign_memory_care_tier(context["flags"], context["answers"])
        
        # Check for high-acuity escalation
        if should_recommend_high_acuity_mc(context["flags"], context["answers"], tier):
            care_type = "memory_care_high_acuity"
        else:
            care_type = "memory_care"
    
    elif gcp_tier == "memory_care_high_acuity":
        care_type = "memory_care_high_acuity"
        tier = assign_memory_care_tier(context["flags"], context["answers"])
    
    elif gcp_tier == "in_home":
        # In-home uses different calculation (hourly-based)
        return calculate_in_home_costs(context, regional_multiplier, location)
    
    else:
        # No care needed / aging in place
        return {
            "care_type": "no_care_needed",
            "total": 0,
            "explanation": "No formal care services recommended at this time."
        }
    
    # 3. Calculate tiered cost
    cost_result = calculate_tiered_cost(
        care_type=care_type,
        tier=tier,
        regional_multiplier=regional_multiplier,
        gcp_flags=context["flags"],
        gcp_answers=context["answers"]
    )
    
    # 4. Calculate range
    cost_range = calculate_cost_range(
        total=cost_result["total"],
        gcp_flags=context["flags"],
        gcp_answers=context["answers"],
        care_type=care_type
    )
    
    # 5. Generate explanation
    explanation = generate_cost_explanation(
        care_type=care_type,
        tier=tier,
        cost_result=cost_result,
        cost_range=cost_range,
        location=location,
        context=context
    )
    
    # 6. Generate recommendations
    recommendations = generate_recommendations(context, care_type, tier)
    
    return {
        "care_type": care_type,
        "tier": tier,
        "base_cost": cost_result["base_cost"],
        "regional_base": cost_result["regional_base"],
        "tier_increment": cost_result["tier_increment"],
        "add_ons": cost_result["add_ons"],
        "total": cost_result["total"],
        "range": cost_range,
        "breakdown": cost_result["breakdown"],
        "explanation": explanation,
        "recommendations": recommendations
    }
```

### 2.3 Explanation Generator

```python
# products/cost_planner_v3/explanations.py

def generate_cost_explanation(
    care_type: str,
    tier: str,
    cost_result: dict,
    cost_range: dict,
    location: dict,
    context: dict
) -> str:
    """
    Generate clear, advisor-friendly cost explanation.
    """
    
    base_info = BASE_COSTS_2024[care_type]
    
    explanation = []
    
    # 1. Base cost and source
    if base_info.get("derived"):
        explanation.append(
            f"**Base Cost:** ${cost_result['base_cost']:,.0f}/month "
            f"(derived estimate - {base_info['source']})"
        )
    else:
        explanation.append(
            f"**Base Cost:** ${cost_result['base_cost']:,.0f}/month "
            f"(national median from {base_info['source']})"
        )
    
    # 2. Regional adjustment
    regional_adj = cost_result['regional_base'] - cost_result['base_cost']
    if regional_adj != 0:
        explanation.append(
            f"**Regional Adjustment:** ${regional_adj:,.0f} "
            f"for {location['city']}, {location['state']}"
        )
    
    # 3. Care tier
    tier_config = AL_TIER_INCREMENTS.get(tier) if care_type == "assisted_living" else MC_TIER_INCREMENTS.get(tier)
    if tier_config and cost_result['tier_increment'] > 0:
        explanation.append(
            f"**Care Tier:** {tier_config['label']} (+${cost_result['tier_increment']:,.0f}) - "
            f"{tier_config['description']}"
        )
    
    # 4. Add-ons
    if cost_result['add_ons']:
        explanation.append("**Additional Services:**")
        for addon in cost_result['add_ons']:
            explanation.append(f"  - {addon['label']}: +${addon['amount']:,.0f}")
    
    # 5. Total and range
    explanation.append(
        f"\n**Estimated Cost Range:** "
        f"${cost_range['low']:,.0f} - ${cost_range['high']:,.0f}/month "
        f"(most likely: ${cost_range['likely']:,.0f})"
    )
    
    # 6. Range explanation
    explanation.append(f"\n{cost_range['range_explanation']}")
    
    # 7. Important notes
    explanation.append(
        f"\n**Note:** These estimates are based on 2024 national data and may vary "
        f"significantly by community. Actual costs should be confirmed with specific providers."
    )
    
    return "\n\n".join(explanation)
```

---

## Phase 3: Production Rollout (Weeks 8-10)

### 3.1 Migration Strategy

```python
# products/cost_planner_v3/migration.py

def migrate_v2_to_v3(v2_result: dict) -> dict:
    """
    Migrate existing v2 cost results to v3 format for comparison.
    Used during dual-calculation pilot period.
    """
    pass  # Implementation details


def compare_v2_v3_estimates(v2_result: dict, v3_result: dict) -> dict:
    """
    Generate comparison report for validation.
    
    Returns:
        {
            "v2_total": float,
            "v3_total": float,
            "difference": float,
            "difference_pct": float,
            "explanation_of_difference": str
        }
    """
    pass  # Implementation details
```

### 3.2 Feature Flag

```python
# core/flags.py

FEATURE_COST_PLANNER_V3 = Flag(
    name="cost_planner_v3",
    default="off",
    values=["off", "shadow", "full"],
    description=(
        "Cost Planner v3 tier-based pricing model. "
        "off: Use v2 only. "
        "shadow: Calculate v3 but show v2 (log comparison). "
        "full: Use v3 for all cost calculations."
    )
)
```

### 3.3 Testing Checklist

#### Unit Tests
- [ ] Tier assignment logic (all scenarios)
- [ ] Regional scaling (all multipliers)
- [ ] Add-on calculation and capping
- [ ] Range calculation (confidence levels)
- [ ] Explanation generation

#### Integration Tests
- [ ] GCP → Cost Planner v3 data flow
- [ ] All care types (AL, MC, MC-HA, in-home)
- [ ] All tier levels (0-4)
- [ ] Edge cases (overflow, high-acuity escalation)

#### Validation Tests (Real Data)
- [ ] 50 real assessments: v2 vs v3 comparison
- [ ] Market validation: 20 community rate sheets
- [ ] Advisor feedback: Does v3 feel accurate?
- [ ] Range accuracy: Are ranges defensible?

---

## Implementation Priorities

### Critical Path Items
1. **Tier assignment rules** - Blocks all testing
2. **Regional scaling** - Affects all calculations
3. **Base cost updates** - v2 using outdated data
4. **GCP integration** - Data pipeline

### Quick Wins
1. **Update v2 base costs** - Immediate accuracy improvement ($4,500 → $5,900)
2. **Add explanation generator** - Works with v2 or v3
3. **Range calculator** - Can add to v2 while building v3

### Deferred to v3.1
- LLM cost explanation enhancement
- Provider-specific pricing (partner integrations)
- Dynamic base cost updates (API integration)
- Historical cost tracking

---

## Success Metrics

### Accuracy
- [ ] v3 estimates within ±15% of actual community pricing (validated with 20 rate sheets)
- [ ] 90% of range estimates contain actual community cost
- [ ] Advisor confidence: "v3 feels more accurate than v2" (survey)

### Technical
- [ ] Zero breaking changes to existing MCIP contracts
- [ ] v3 calculation time < 100ms (same as v2)
- [ ] All tier assignment rules covered by unit tests

### Strategic
- [ ] Explainability: 100% of estimates include source citations
- [ ] Transparency: All derived estimates clearly labeled
- [ ] Foundation for partner negotiations and monetization

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tier rules produce unexpected results | High | High | Extensive unit tests + shadow mode validation |
| v3 estimates deviate significantly from v2 | Medium | High | Dual calculation for 4 weeks, advisor feedback |
| Market data validation fails | Medium | High | Gather 30+ rate sheets before launch |
| Regional scaling introduces bugs | Low | Medium | Test all regional multipliers |
| Backward compatibility breaks | Low | High | Feature flag with full v2 fallback |

---

## Next Steps

### Week 1
1. Finalize tier assignment rules (review with clinical team)
2. Update v2 base costs to $5,900/$6,500/$9,000 (quick fix)
3. Set up v3 module structure

### Week 2-3
1. Implement tier assignment logic
2. Build regional scaling calculator
3. Create add-on calculator with capping
4. Write unit tests

### Week 4
1. Integrate with GCP
2. Build explanation generator
3. Deploy shadow mode (v3 calculates but v2 shown)
4. Gather 50 real assessments for comparison

### Week 5-7
1. Analyze v2 vs v3 discrepancies
2. Refine tier increments based on market data
3. Advisor feedback sessions
4. Iterate on range calculations

### Week 8-10
1. Full production rollout (feature flag)
2. Monitor for 2 weeks
3. Cut over to v3 default
4. Deprecate v2

---

**Document Status:** Ready for review and approval  
**Next Review Date:** January 2026  
**Owner:** Cost Planner Team
