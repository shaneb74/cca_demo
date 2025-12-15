# Cost Estimation Logical Matrix - Concierge Care Advisors

## Base Rates (National Baseline - Monthly)

| Care Type | Base Cost | Source |
|-----------|-----------|--------|
| **Assisted Living** | $4,500 | Genworth 2024 |
| **Memory Care** | $6,500 | Genworth 2024 |
| **Memory Care High Acuity** | $9,000 | Genworth 2024 |
| **In-Home Care** | $30.00/hour | Genworth 2024 (National median) |
| **Home Carry Cost** | $4,500 | Mortgage/rent + tax + insurance + maintenance |

---

## Step 1: Regional Adjustment

All base costs are multiplied by a **regional multiplier** based on ZIP code:

**Precedence:** ZIP → ZIP3 → State → Default (1.0)

**Example Multipliers:**
- Seattle, WA: ~1.30 (+30%)
- Rural areas: ~0.85 (-15%)
- National average: 1.0 (no adjustment)

**Formula:**
```
Regional Adjusted Cost = Base Cost × Regional Multiplier
```

---

## Step 2: Care Modifier Application (Cumulative)

Modifiers are applied **cumulatively** to the running total based on active care flags from GCP. Each care type has different modifier percentages:

### Assisted Living Modifiers

| Flag | Modifier % | Label |
|------|------------|-------|
| `memory_support` | +20% | Memory Care Support |
| `mobility_limited` | +15% | Mobility/Transfer Assistance |
| `adl_support_high` | +10% | Extensive ADL Support |
| `medication_management` | +8% | Medication Management |
| `behavioral_concerns` | +12% | Behavioral Support |
| `falls_risk` | +8% | Fall Prevention & Monitoring |
| `chronic_conditions` | +10% | Chronic Condition Management |

### Memory Care Modifiers

| Flag | Modifier % | Label | Notes |
|------|------------|-------|-------|
| `memory_support` | +15% | Memory Care Support | Lower - baseline includes memory care |
| `mobility_limited` | +12% | Mobility/Transfer Assistance | |
| `adl_support_high` | +8% | Extensive ADL Support | |
| `medication_management` | +6% | Medication Management | |
| `behavioral_concerns` | +10% | Behavioral Support | |
| `falls_risk` | +6% | Fall Prevention & Monitoring | |
| `chronic_conditions` | +8% | Chronic Condition Management | |

### Memory Care High Acuity Modifiers

| Flag | Modifier % | Label | Notes |
|------|------------|-------|-------|
| `memory_support` | +10% | Memory Care Support | Lowest - high acuity baseline |
| `mobility_limited` | +10% | Mobility/Transfer Assistance | |
| `adl_support_high` | +6% | Extensive ADL Support | |
| `medication_management` | +5% | Medication Management | |
| `behavioral_concerns` | +8% | Behavioral Support | |
| `falls_risk` | +5% | Fall Prevention & Monitoring | |
| `chronic_conditions` | +6% | Chronic Condition Management | |
| **`high_acuity_tier`** | **+25%** | **High-Acuity Intensive Care** | **Always applied** |

### In-Home Care Modifiers

| Flag | Modifier % | Label | Notes |
|------|------------|-------|-------|
| `memory_support` | +25% | Memory Care Support | Higher - specialized training required |
| `mobility_limited` | +20% | Mobility/Transfer Assistance | Higher - equipment/2-person lifts |
| `adl_support_high` | +15% | Extensive ADL Support | |
| `medication_management` | +10% | Medication Management | |
| `behavioral_concerns` | +15% | Behavioral Support | |
| `falls_risk` | +10% | Fall Prevention & Monitoring | |
| `chronic_conditions` | +12% | Chronic Condition Management | |

**Formula (Cumulative):**
```
Running Total = Regional Adjusted Cost

For each active flag:
    Modifier Amount = Running Total × Modifier %
    Running Total += Modifier Amount
```

**Important:** Modifiers compound on each other. If 3 modifiers apply, each applies to the result of the previous calculation.

---

## Step 3: Home Carry Cost (Optional)

### For Facility Care (AL, MC, MC-HA):
- **Optional** - only if user plans to keep home
- Uses dampened regional multiplier (50% of deviation from 1.0)

### For In-Home Care:
- **Always included** (person stays at home)

**Formula:**
```
Deviation = Regional Multiplier - 1.0
Dampened Multiplier = 1.0 + (Deviation × 0.5)
Home Carry Effective = Home Carry Base × Dampened Multiplier
```

**Example:** If care multiplier is 1.30 (+30%), home multiplier is 1.15 (+15%)

---

## Step 4: In-Home Care Hours Calculation

For in-home care only:

```
Hourly Rate = $30.00 × Regional Multiplier
Hours Per Month = Hours Per Day × 30.4
Base Care Cost = Hourly Rate × Hours Per Month
```

Then apply modifiers (Step 2) and home carry cost (Step 3).

---

## Step 5: Final Totals

```
Monthly Total = Running Total (after all modifiers + home carry if applicable)
Annual Total = Monthly Total × 12
Three Year Total = Annual Total × 3
Five Year Total = Annual Total × 5
```

---

## Example Calculation: Assisted Living with Modifiers

**Inputs:**
- Care Type: Assisted Living
- ZIP: Seattle, WA (multiplier 1.30)
- Active Flags: `memory_support`, `mobility_limited`, `falls_risk`
- Keep Home: No

**Calculation:**
1. **Base Cost:** $4,500
2. **Regional Adjustment:** $4,500 × 1.30 = $5,850
3. **Modifiers (cumulative):**
   - Memory Support (+20%): $5,850 × 0.20 = $1,170 → Running: $7,020
   - Mobility Limited (+15%): $7,020 × 0.15 = $1,053 → Running: $8,073
   - Falls Risk (+8%): $8,073 × 0.08 = $646 → Running: $8,719
4. **Home Carry:** $0 (not keeping home)
5. **Monthly Total: $8,719**
6. **Annual Total: $104,628**
7. **Three Year Total: $313,884**

---

## Example Calculation: In-Home Care

**Inputs:**
- Care Type: In-Home Care
- Hours Per Day: 8
- ZIP: Seattle, WA (multiplier 1.30)
- Active Flags: `mobility_limited`, `medication_management`
- Home Carry: User override $3,000/month

**Calculation:**
1. **Hourly Rate:** $30.00 × 1.30 = $39.00
2. **Hours Per Month:** 8 × 30.4 = 243.2 hours
3. **Base Care Cost:** $39.00 × 243.2 = $9,485
4. **Modifiers (cumulative):**
   - Mobility Limited (+20%): $9,485 × 0.20 = $1,897 → Running: $11,382
   - Medication Management (+10%): $11,382 × 0.10 = $1,138 → Running: $12,520
5. **Home Carry (dampened):**
   - Deviation: 1.30 - 1.0 = 0.30
   - Dampened Multiplier: 1.0 + (0.30 × 0.5) = 1.15
   - Home Carry: $3,000 × 1.15 = $3,450
6. **Monthly Total: $12,520 + $3,450 = $15,970**
7. **Annual Total: $191,640**
8. **Three Year Total: $574,920**

---

## Key Design Principles

1. **Regional First**: All calculations start with regional adjustment
2. **Cumulative Modifiers**: Each modifier applies to the running total (compounds)
3. **Care-Type-Specific**: Same flag has different percentages for different care types
4. **Transparency**: Every line item is tracked for UI breakdown display
5. **Authoritative Sources**: Base rates from Genworth 2024 Cost of Care Survey
6. **Deterministic**: Same inputs always produce same outputs (no randomness)

---

## Implementation Files

- **Primary Logic**: `products/cost_planner_v2/comparison_calcs.py`
- **Quick Estimates**: `products/cost_planner_v2/utils/cost_calculator.py`
- **Regional Data**: `products/cost_planner_v2/utils/regional_data.py`
- **Configuration**: `config/regional_cost_config.json`

---

## Flag Sources

Care flags are derived from the **Guided Care Plan (GCP v4)** module:
- `products/gcp_v4/modules/care_recommendation/logic.py`
- Stored in MCIP: `core/mcip.py`
- Retrieved via: `MCIP.get_care_recommendation()`

---

## Version History

- **v2.0** (2024-Q4): Care-type-specific modifiers, cumulative application
- **v1.0** (2024-Q3): Initial base rates + regional adjustment

---

*Last Updated: December 1, 2025*
