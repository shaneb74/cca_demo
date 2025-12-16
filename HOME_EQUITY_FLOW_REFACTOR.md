# Home Equity Flow Refactor

## Summary
Completed major UX refactor of the Housing Profile assessment to remove upfront strategy opt-in and implement progressive disclosure based on housing type.

## Key Changes

### 1. Flow Reorganization
**Before:** Started with "Would you like to evaluate strategies?" opt-in question
**After:** Starts with housing type selection, progressively reveals based on user choices

### 2. New Question Flow

#### All Users
1. **Housing Type** (`owns_home`): own / rent / other

#### Homeowners Path
2. **Home Value** (`home_value`)
3. **Mortgage Balance** (`mortgage_balance`)
4. **Monthly Carrying Costs** (`monthly_carry`)
5. **What are you considering?** (`home_plan`):
   - Keep the home (baseline)
   - Sell the home
   - Rent out the home
   - Get a reverse mortgage
   - Not sure / exploring options
6. **Local Rent** (`local_rent`) - Only if home_plan = "rent_out"

#### Renters Path
2. **Monthly Rent** (`monthly_rent`)
3. **How should we treat this during care?** (`rental_plan`):
   - Continue paying (include in costs)
   - End lease (exclude from costs)
   - Not sure (conservative: include)

#### Other Housing Path
2. **Do you contribute to household costs?** (`household_contribution_type`):
   - No
   - Fixed monthly amount
   - Variable/other
3. **Monthly Contribution** (`monthly_household_contribution`) - Only if contribution_type != "no"

### 3. Strategy Comparison Section

**Visibility:** Only shows for homeowners when `home_plan` in ["sell", "rent_out", "reverse_mortgage", "not_sure"]

**Contents:**
- Care cost and duration inputs
- Whether they plan to return home
- Multi-select for strategies to compare (optional)
- Results section with comparison cards

### 4. Field Naming Changes
- `analyze_strategies` → Removed (no longer needed)
- `home_plan` options: `"uncertain"` → `"not_sure"`, `"stay"` → `"keep"`
- `rental_plan` options: `"uncertain"` → `"not_sure"`

### 5. Cost Calculation Logic

#### Homeowners
- **Keep:** `monthly_housing_cost = monthly_carry`
- **Sell:** `monthly_housing_cost = 0` (will get new housing later)
- **Rent out / Reverse / Not sure:** `monthly_housing_cost = monthly_carry`

#### Renters
- **Continue / Not sure:** `monthly_housing_cost = monthly_rent` (conservative)
- **End lease:** `monthly_housing_cost = 0`

#### Other
- **No contribution:** `monthly_housing_cost = 0`
- **Fixed/Variable:** `monthly_housing_cost = monthly_household_contribution`

### 6. Strategy-Specific Calculations

The helper now computes strategy-specific outputs based on `home_plan`:

#### Keep
- Shows potential sale proceeds (baseline comparison)
- No equity used in plan
- Monthly cost = carrying costs

#### Sell
- Net sale proceeds after 8% fees
- Months of care funded
- No ongoing monthly cost

#### Rent Out
- Net rental income (rent - carry - 8% vacancy)
- Total rental contribution over care duration
- Months of care funded from rental income

#### Reverse Mortgage
- Estimated draw (50% of value - mortgage)
- Months of care funded
- Monthly cost = carrying costs

#### Not Sure
- Shows all potential values:
  - Potential sale proceeds
  - Potential reverse mortgage draw
  - Potential net rental income (if local_rent provided)
- Monthly cost = carrying costs

### 7. Rendering Updates

**assessments.py** now checks:
```python
if owns_home != "own" or home_plan not in ["sell", "rent_out", "reverse_mortgage", "not_sure"]:
    return  # Don't render strategy section
```

Strategy comparison cards only appear for actionable plans, not for "keep" baseline.

## Benefits

1. **Better UX:** Users don't see abstract opt-in question; flow follows their actual situation
2. **Progressive Disclosure:** Questions appear based on relevant context
3. **Clearer Intent:** `home_plan` explicitly captures what user is considering
4. **Baseline Comparison:** "Keep" option shows potential without applying funds
5. **Conservative Defaults:** "Not sure" options include costs to avoid underestimation
6. **Simpler Logic:** Removed dual purpose of `analyze_strategies` field

## Testing Checklist

- [ ] Homeowner flow: own → value/mortgage/carry → home_plan → strategy section
- [ ] Local rent field appears only when home_plan = "rent_out"
- [ ] Strategy section hidden when home_plan = "keep"
- [ ] Renter flow: rent → monthly_rent → rental_plan
- [ ] Other housing flow: other → contribution_type → monthly_contribution
- [ ] Cost calculations correct for all paths
- [ ] Strategy comparison renders correctly when multiple strategies selected
- [ ] "Keep" baseline shows potential proceeds without applying
- [ ] Summary card shows appropriate info based on home_plan

## Files Modified

1. `/products/cost_planner_v2/modules/assessments/home_equity.json`
   - Removed `analyze_strategies` from top
   - Reordered to start with `owns_home`
   - Added `home_plan` field with 5 options
   - Made `local_rent` conditional on `home_plan = "rent_out"`
   - Changed `strategy_comparison` section visibility to check `home_plan` values
   - Updated value names for consistency

2. `/products/cost_planner_v2/utils/home_equity_helpers.py`
   - Updated `normalize_home_equity_data()` to handle new field structure
   - Removed `analyze_strategies` checks
   - Added `strategy_outputs` dict with plan-specific calculations
   - Updated cost logic to handle `home_plan` values
   - Changed strategy analysis trigger to check `home_plan` instead of opt-in

3. `/products/cost_planner_v2/assessments.py`
   - Updated `_render_home_equity_results()` visibility check
   - Changed from `analyze_strategies == "yes"` to `home_plan in [actionable_values]`
   - Strategy section now only renders for homeowners with actionable plans
