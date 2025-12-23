# Care Costs - Base Rates & Modifiers

**Source:** `products/cost_planner_v2/comparison_calcs.py`  
**Data Source:** Genworth 2024 Cost of Care Survey (National Median)  
**Date:** December 22, 2025

---

## Base Monthly Costs (National Median)

| Care Type | Base Cost | Description |
|-----------|-----------|-------------|
| **Assisted Living** | $5,900/month | National median (Genworth 2024: $70,800/year) |
| **Memory Care** | $7,400/month | Derived: AL × 1.254 (typical MC premium) |
| **Memory Care - High Acuity** | $9,400/month | Derived: MC + high-acuity increment |

**Note:** All base costs are scaled by regional multipliers from `RegionalDataProvider`.

---

## Cost Modifiers by Care Type

### Assisted Living Modifiers

| Flag | Multiplier | Description |
|------|-----------|-------------|
| `memory_support` | **+20%** | Memory Care Support |
| `mobility_limited` | **+15%** | Mobility/Transfer Assistance |
| `adl_support_high` | **+10%** | Extensive ADL Support |
| `medication_management` | **+8%** | Medication Management |
| `behavioral_concerns` | **+12%** | Behavioral Support |
| `falls_risk` | **+8%** | Fall Prevention & Monitoring |
| `chronic_conditions` | **+10%** | Chronic Condition Management |

**Example Calculation:**
```
Base: $5,900
+ Regional adjustment (e.g., 1.3x for high-cost area): $1,770
+ Memory support (20%): $1,534
+ Mobility limited (15%): $1,150.50
= Total: $10,354.50/month
```

---

### Memory Care Modifiers

| Flag | Multiplier | Description |
|------|-----------|-------------|
| `memory_support` | **+15%** | Memory Care Support |
| `mobility_limited` | **+12%** | Mobility/Transfer Assistance |
| `adl_support_high` | **+8%** | Extensive ADL Support |
| `medication_management` | **+6%** | Medication Management |
| `behavioral_concerns` | **+10%** | Behavioral Support |
| `falls_risk` | **+6%** | Fall Prevention & Monitoring |
| `chronic_conditions` | **+8%** | Chronic Condition Management |

**Note:** Memory Care modifiers are **lower than Assisted Living** because the $6,500 base cost already includes specialized memory care services, secured environment, and trained staff.

**Example Calculation:**
```
Base: $7,400
+ Regional adjustment (e.g., 1.3x): $2,220
+ Behavioral concerns (10%): $1,258
+ Falls risk (6%): $754.80
= Total: $11,632.80/month
```

---

### Memory Care - High Acuity Modifiers

| Flag | Multiplier | Description |
|------|-----------|-------------|
| `memory_support` | **+10%** | Memory Care Support |
| `mobility_limited` | **+10%** | Mobility/Transfer Assistance |
| `adl_support_high` | **+6%** | Extensive ADL Support |
| `medication_management` | **+5%** | Medication Management |
| `behavioral_concerns` | **+8%** | Behavioral Support |
| `falls_risk` | **+5%** | Fall Prevention & Monitoring |
| `chronic_conditions` | **+6%** | Chronic Condition Management |
| `high_acuity_tier` | **+25%** | High-Acuity Intensive Care (always applied) |

**Note:** High Acuity modifiers are lowest because the $9,000 base includes skilled nursing, 24/7 supervision, and intensive care delivery.

---

## In-Home Care Rates

### Hourly Base Rate
- **National Median:** $34.00/hour (Genworth 2024)
- **Calculation:** `hourly_rate × hours_per_day × 30 days`

### In-Home Care Modifiers

| Flag | Multiplier | Description |
|------|-----------|-------------|
| `memory_support` | **+25%** | Memory Care Support (higher - requires specialized training) |
| `mobility_limited` | **+20%** | Mobility/Transfer Assistance (higher - equipment/2-person lifts) |
| `adl_support_high` | **+15%** | Extensive ADL Support |
| `medication_management` | **+10%** | Medication Management |
| `behavioral_concerns` | **+15%** | Behavioral Support |
| `falls_risk` | **+10%** | Fall Prevention & Monitoring |
| `chronic_conditions` | **+12%** | Chronic Condition Management |

**Note:** In-home modifiers are **highest** because caregivers work 1-on-1 and require specialized skills for complex care needs.

---

## Regional Multipliers

Regional adjustments are applied to base costs **before** care modifiers. Examples:

| Region | Multiplier | Example (AL Base) |
|--------|-----------|-------------------|
| Low-cost | 0.8x | $4,720/month |
| National average | 1.0x | $5,900/month |
| High-cost urban | 1.3x | $7,670/month |
| Very high-cost | 1.5x | $8,850/month |

---

## Flag Mapping (GCP → Cost Planner)

These flags are set by the Guided Care Plan (GCP) and trigger cost modifiers:

| GCP Flag | Cost Modifier Flag | Set By |
|----------|-------------------|--------|
| `severe_cognitive_risk` | `memory_support` | Q14 (memory_changes = "severe") |
| `high_mobility_dependence` | `mobility_limited` | Q7, Q8 (wheelchair/bedbound/2-person transfer) |
| `high_dependence` | `adl_support_high` | Q10, Q11, Q19 (extensive help) |
| `moderate_dependence` + `meds_complexity` | `medication_management` | Q5 (moderate/complex medications) |
| Behavior flags | `behavioral_concerns` | Q16 (any behavior selected) |
| `falls_multiple` | `falls_risk` | Q9 (multiple falls) |
| `chronic_present` | `chronic_conditions` | Q5, Q6 (chronic conditions present) |

---

## Home Carry Cost

**Base:** $4,500/month (national median)  
**Includes:** Mortgage/rent + property tax + insurance + maintenance  
**Regional scaling:** Applied via regional multiplier

Used in cost comparisons to show total housing cost when comparing facility vs staying home with in-home care.

---

**Last Updated:** December 22, 2025  
**Maintained By:** Cost Planner v2 Module
