"""
Home equity analysis helpers for Cost Planner v2.

Provides calculation functions for evaluating different home equity strategies:
- Selling the home
- Renting the home
- Reverse mortgage
- Keeping the home

Each strategy returns projected cash flow and months of care that can be funded.
"""

from __future__ import annotations

from typing import Any, TypedDict


class StrategyResult(TypedDict):
    """Result for a single home equity strategy."""
    strategy: str
    net_proceeds: float
    monthly_cash_flow: float
    months_of_care_funded: float
    considerations: list[str]


# Constants for calculations
DEFAULT_SELLING_FEE_PERCENT = 0.08  # 8% for agent fees, closing costs, etc.
DEFAULT_REVERSE_MORTGAGE_PERCENT = 0.50  # 50% of home value (conservative estimate)
DEFAULT_RENTAL_VACANCY_PERCENT = 0.08  # 8% vacancy rate


def calculate_net_sale_proceeds(
    home_value: float,
    mortgage_balance: float,
    selling_fee_percent: float = DEFAULT_SELLING_FEE_PERCENT,
) -> float:
    """
    Calculate net proceeds from selling the home.

    Args:
        home_value: Current market value of the home
        mortgage_balance: Remaining mortgage balance
        selling_fee_percent: Percentage of home value for selling costs (default 8%)

    Returns:
        Net proceeds after paying off mortgage and selling costs
    """
    if home_value <= 0:
        return 0.0

    selling_costs = home_value * selling_fee_percent
    net_proceeds = home_value - mortgage_balance - selling_costs

    return max(0.0, net_proceeds)


def calculate_reverse_mortgage_draw(
    home_value: float,
    mortgage_balance: float,
    reverse_percent: float = DEFAULT_REVERSE_MORTGAGE_PERCENT,
) -> float:
    """
    Calculate available funds from a reverse mortgage.

    Args:
        home_value: Current market value of the home
        mortgage_balance: Remaining mortgage balance
        reverse_percent: Percentage of home value available (default 50%)

    Returns:
        Available cash from reverse mortgage after paying off existing mortgage

    Note:
        This is a simplified calculation. Actual reverse mortgage amounts depend on:
        - Borrower age
        - Interest rates
        - Home value and location
        - Lender requirements
    """
    if home_value <= 0:
        return 0.0

    # Maximum reverse mortgage amount (typically 40-60% of home value)
    max_reverse = home_value * reverse_percent

    # Must pay off existing mortgage first
    available_cash = max_reverse - mortgage_balance

    return max(0.0, available_cash)


def calculate_net_rental_income(
    local_rent: float,
    monthly_carry: float,
    vacancy_percent: float = DEFAULT_RENTAL_VACANCY_PERCENT,
) -> float:
    """
    Calculate net monthly rental income after expenses and vacancy.

    Args:
        local_rent: Expected monthly rental income
        monthly_carry: Monthly carrying costs (taxes, insurance, maintenance)
        vacancy_percent: Vacancy rate percentage (default 8%)

    Returns:
        Net monthly income from renting
    """
    if local_rent <= 0:
        return 0.0

    # Adjust for vacancy rate
    effective_rent = local_rent * (1 - vacancy_percent)

    # Subtract carrying costs
    net_income = effective_rent - monthly_carry

    return net_income


def calculate_months_funded(
    available_funds: float,
    monthly_care_cost: float,
) -> float:
    """
    Calculate how many months of care can be funded with available funds.

    Args:
        available_funds: Total available funds
        monthly_care_cost: Monthly cost of care

    Returns:
        Number of months of care that can be funded (0 if care cost is 0)
    """
    if monthly_care_cost <= 0:
        return 0.0

    return available_funds / monthly_care_cost


def analyze_home_equity_strategies(
    owns_home: bool | str,
    home_value: float,
    mortgage_balance: float,
    monthly_carry: float,
    local_rent: float,
    care_cost: float,
    care_duration: int,
    return_home: str,
    strategy_selection: list[str],
) -> dict[str, StrategyResult]:
    """
    Analyze selected home equity strategies and return comparison results.

    Args:
        owns_home: Whether the person owns a home (bool or "yes"/"no"/"own")
        home_value: Current market value of the home
        mortgage_balance: Remaining mortgage balance
        monthly_carry: Monthly carrying costs
        local_rent: Potential monthly rental income
        care_cost: Monthly cost of care
        care_duration: Expected duration of care in months
        return_home: Whether returning home is a priority ("yes"/"no"/"unsure")
        strategy_selection: List of selected strategies to evaluate

    Returns:
        Dictionary mapping strategy names to StrategyResult objects
    """
    results: dict[str, StrategyResult] = {}

    # Normalize owns_home to boolean
    if isinstance(owns_home, str):
        owns_home = owns_home.lower() in ("yes", "own")

    if not owns_home:
        return results

    # Ensure strategy_selection is a list
    if not isinstance(strategy_selection, list):
        strategy_selection = [strategy_selection] if strategy_selection else []

    # Analyze each selected strategy
    for strategy in strategy_selection:
        if strategy == "keep":
            results["keep"] = _analyze_keep_strategy(
                monthly_carry, care_cost, care_duration, return_home
            )
        elif strategy == "rent":
            results["rent"] = _analyze_rent_strategy(
                local_rent, monthly_carry, care_cost, care_duration, return_home
            )
        elif strategy == "sell":
            results["sell"] = _analyze_sell_strategy(
                home_value, mortgage_balance, care_cost, return_home
            )
        elif strategy == "reverse_mortgage":
            results["reverse_mortgage"] = _analyze_reverse_mortgage_strategy(
                home_value, mortgage_balance, care_cost, return_home
            )

    return results


def _analyze_keep_strategy(
    monthly_carry: float,
    care_cost: float,
    care_duration: int,
    return_home: str,
) -> StrategyResult:
    """Analyze the 'keep home' strategy."""
    considerations = [
        "Maintains home ownership and option to return",
        f"Ongoing carrying costs: ${monthly_carry:,.0f}/month",
        "No additional funding generated for care costs",
    ]

    if return_home == "yes":
        considerations.append("✓ Aligns with goal to return home")
    else:
        considerations.append("⚠️ Home remains vacant while paying costs")

    return {
        "strategy": "Keep the home",
        "net_proceeds": 0.0,
        "monthly_cash_flow": -monthly_carry,  # Negative = ongoing cost
        "months_of_care_funded": 0.0,
        "considerations": considerations,
    }


def _analyze_rent_strategy(
    local_rent: float,
    monthly_carry: float,
    care_cost: float,
    care_duration: int,
    return_home: str,
) -> StrategyResult:
    """Analyze the 'rent home' strategy."""
    net_rent = calculate_net_rental_income(local_rent, monthly_carry)
    total_rental_income = net_rent * care_duration
    months_funded = calculate_months_funded(total_rental_income, care_cost) if care_cost > 0 else 0.0

    considerations = [
        f"Generates ${net_rent:,.0f}/month after expenses",
        "Maintains home ownership for future return",
        f"Covers ~{months_funded:.1f} months of care costs" if months_funded > 0 else "Rental income available for care costs",
    ]

    if net_rent < 0:
        considerations.append("⚠️ Rental income is less than carrying costs")
    elif return_home == "yes":
        considerations.append("✓ Preserves option to return home later")

    considerations.append("Requires property management and tenant screening")

    return {
        "strategy": "Rent the home",
        "net_proceeds": 0.0,
        "monthly_cash_flow": net_rent,
        "months_of_care_funded": months_funded,
        "considerations": considerations,
    }


def _analyze_sell_strategy(
    home_value: float,
    mortgage_balance: float,
    care_cost: float,
    return_home: str,
) -> StrategyResult:
    """Analyze the 'sell home' strategy."""
    net_proceeds = calculate_net_sale_proceeds(home_value, mortgage_balance)
    months_funded = calculate_months_funded(net_proceeds, care_cost) if care_cost > 0 else 0.0

    considerations = [
        f"One-time proceeds: ${net_proceeds:,.0f}",
        f"Covers ~{months_funded:.1f} months of care" if months_funded > 0 else "Proceeds available for care costs",
        "Eliminates ongoing carrying costs",
        "Liquidates home equity completely",
    ]

    if return_home == "yes":
        considerations.append("⚠️ Conflicts with goal to return home")
    else:
        considerations.append("✓ Provides maximum immediate liquidity")

    return {
        "strategy": "Sell the home",
        "net_proceeds": net_proceeds,
        "monthly_cash_flow": 0.0,
        "months_of_care_funded": months_funded,
        "considerations": considerations,
    }


def _analyze_reverse_mortgage_strategy(
    home_value: float,
    mortgage_balance: float,
    care_cost: float,
    return_home: str,
) -> StrategyResult:
    """Analyze the 'reverse mortgage' strategy."""
    available_cash = calculate_reverse_mortgage_draw(home_value, mortgage_balance)
    months_funded = calculate_months_funded(available_cash, care_cost) if care_cost > 0 else 0.0

    considerations = [
        f"Available cash: ${available_cash:,.0f}",
        f"Covers ~{months_funded:.1f} months of care" if months_funded > 0 else "Cash available for care costs",
        "Maintains home ownership",
        "No monthly mortgage payments required",
    ]

    if available_cash <= 0:
        considerations.append("⚠️ Existing mortgage may need to be paid off first")
    elif return_home == "yes":
        considerations.append("✓ Preserves option to return home")

    considerations.append("Interest accrues and reduces home equity over time")
    considerations.append("Requires age 62+ and sufficient home equity")

    return {
        "strategy": "Reverse mortgage",
        "net_proceeds": available_cash,
        "monthly_cash_flow": 0.0,
        "months_of_care_funded": months_funded,
        "considerations": considerations,
    }


def normalize_home_equity_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize home equity assessment data for storage.

    Args:
        data: Raw form data from assessment

    Returns:
        Normalized data dictionary with computed values
    """
    # Extract raw values
    owns_home = data.get("owns_home", "other")
    home_value = _to_float(data.get("home_value", 0))
    mortgage_balance = _to_float(data.get("mortgage_balance", 0))
    monthly_carry = _to_float(data.get("monthly_carry", 0))
    monthly_rent = _to_float(data.get("monthly_rent", 0))
    household_contribution_type = data.get("household_contribution_type", "no")
    monthly_household_contribution = _to_float(data.get("monthly_household_contribution", 0))
    local_rent = _to_float(data.get("local_rent", 0))
    care_cost = _to_float(data.get("care_cost", 0))
    care_duration = int(_to_float(data.get("care_duration", 0)))
    return_home = data.get("return_home", "unsure")
    analyze_strategies = data.get("analyze_strategies", "no")
    strategy_selection = data.get("strategy_selection", [])
    home_plan = data.get("home_plan", "uncertain")
    rental_plan = data.get("rental_plan", "uncertain")

    # Calculate monthly housing cost based on housing type
    monthly_housing_cost = 0.0
    
    if owns_home == "own":
        monthly_housing_cost = monthly_carry
    elif owns_home == "rent":
        # Include rent based on rental plan
        if rental_plan in ("continue", "uncertain"):
            # Conservative: include rent if continuing or unsure
            monthly_housing_cost = monthly_rent
        else:
            # end_lease: exclude rent
            monthly_housing_cost = 0.0
    elif owns_home == "other":
        # Include household contribution if any
        if household_contribution_type != "no":
            monthly_housing_cost = monthly_household_contribution
        else:
            monthly_housing_cost = 0.0

    # Compute home equity (only for homeowners)
    home_equity = 0.0
    equity_available = 0.0
    if owns_home == "own" and home_value > 0:
        home_equity = home_value - mortgage_balance
        equity_available = max(0.0, home_equity)  # Can't have negative equity available

    # Only analyze strategies if user opted in and owns home
    strategies = {}
    if owns_home == "own" and analyze_strategies == "yes" and strategy_selection:
        strategies = analyze_home_equity_strategies(
            owns_home=owns_home,
            home_value=home_value,
            mortgage_balance=mortgage_balance,
            monthly_carry=monthly_carry,
            local_rent=local_rent,
            care_cost=care_cost,
            care_duration=care_duration,
            return_home=return_home,
            strategy_selection=strategy_selection,
        )

    return {
        # Raw inputs
        "owns_home": owns_home,
        "home_value": home_value,
        "mortgage_balance": mortgage_balance,
        "monthly_carry": monthly_carry,
        "monthly_rent": monthly_rent,
        "household_contribution_type": household_contribution_type,
        "monthly_household_contribution": monthly_household_contribution,
        "local_rent": local_rent,
        "care_cost": care_cost,
        "care_duration": care_duration,
        "return_home": return_home,
        "analyze_strategies": analyze_strategies,
        "strategy_selection": strategy_selection,
        "home_plan": home_plan,
        "rental_plan": rental_plan,
        # Computed values
        "monthly_housing_cost": monthly_housing_cost,
        "home_equity": home_equity,
        "equity_available": equity_available,
        "strategies": strategies,
        "has_strategies": len(strategies) > 0,
    }


def _to_float(value: Any) -> float:
    """Convert a value to float with safe fallback."""
    if value in (None, "", False):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
