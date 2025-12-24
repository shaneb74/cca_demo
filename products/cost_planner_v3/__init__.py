"""
Cost Planner v3 - Tier-Based Clinical Cost Modeling

Version 3.0 introduces:
- Tier-based pricing (replaces additive percentage stacking)
- Updated 2024 Genworth base costs
- Clinically-informed chronic condition logic
- Regional-scaled tier increments
- Cost ranges with confidence levels
- Comprehensive explanations with source citations

Module Structure:
- constants.py: Base costs, tier structures, data sources
- tier_assignment.py: GCP flag → tier mapping logic
- calculator.py: Main cost calculation engine
- ranges.py: Confidence-based cost ranges
- explanations.py: Human-readable cost breakdowns
- add_ons.py: Capped secondary cost modifiers
"""

__version__ = "3.0.0"

from products.cost_planner_v3.calculator import calculate_care_costs
from products.cost_planner_v3.explanations import (
    generate_cost_explanation,
    generate_comparison_table,
    generate_quick_summary
)

__all__ = [
    "calculate_care_costs",
    "generate_cost_explanation",
    "generate_comparison_table",
    "generate_quick_summary"
]
