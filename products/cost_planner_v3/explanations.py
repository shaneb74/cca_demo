"""
Cost Planner v3 - Human-Readable Explanations

Generates transparent, source-cited cost breakdowns for advisors and families.
"""

from typing import Dict, Any, List
from products.cost_planner_v3.constants import (
    get_base_cost_source,
    is_base_cost_derived
)


def generate_cost_explanation(
    calculation_result: Dict[str, Any],
    include_sources: bool = True,
    audience: str = "advisor"
) -> str:
    """
    Generate human-readable cost explanation.
    
    Args:
        calculation_result: Output from calculate_care_costs()
        include_sources: Whether to include data source citations
        audience: "advisor" or "family" (adjusts detail level)
    
    Returns:
        Formatted explanation string with markdown
    """
    
    care_type = calculation_result["care_type"]
    
    if audience == "advisor":
        return generate_advisor_explanation(calculation_result, include_sources)
    else:
        return generate_family_explanation(calculation_result)


def generate_advisor_explanation(result: Dict[str, Any], include_sources: bool) -> str:
    """Generate detailed explanation for Care Advisors."""
    
    sections = []
    
    # Header
    sections.append(generate_header(result))
    
    # Cost breakdown
    sections.append(generate_breakdown_table(result))
    
    # Range explanation
    sections.append(generate_range_section(result))
    
    # Tier explanation
    if result.get("tier_id") not in ["hourly", "hourly_with_carry", "high_acuity"]:
        sections.append(generate_tier_explanation(result))
    
    # Add-ons explanation
    if result.get("addons"):
        sections.append(generate_addons_explanation(result))
    
    # Sources
    if include_sources:
        sections.append(generate_sources_section(result))
    
    # Advisor notes
    sections.append(generate_advisor_notes(result))
    
    return "\n\n".join(sections)


def generate_family_explanation(result: Dict[str, Any]) -> str:
    """Generate simplified explanation for families."""
    
    sections = []
    
    # Simple header
    low = result["low_estimate"]
    high = result["high_estimate"]
    likely = result["likely_estimate"]
    
    sections.append(f"## Estimated Monthly Cost")
    sections.append(
        f"**Range:** ${low:,.0f} - ${high:,.0f}/month\n"
        f"**Most Likely:** ${likely:,.0f}/month"
    )
    
    # What's included
    sections.append("### What This Includes")
    care_type = result["care_type"]
    if care_type in ["assisted_living", "memory_care", "memory_care_high_acuity"]:
        sections.append(
            "- Private or semi-private apartment\n"
            "- Three meals daily plus snacks\n"
            "- Medication management and monitoring\n"
            "- Activities and social engagement\n"
            "- Housekeeping and laundry\n"
            "- Transportation to appointments\n"
            f"- {get_care_type_specific_inclusions(care_type)}"
        )
    else:  # In-home
        hours = result.get("hours_per_week", 0)
        sections.append(
            f"- Professional caregiver support ({hours} hours/week)\n"
            "- Personal care assistance\n"
            "- Light housekeeping\n"
            "- Meal preparation\n"
            "- Medication reminders\n"
            "- Companionship"
        )
    
    # Why this range
    sections.append("### Why This Range?")
    sections.append(result["range_explanation"])
    
    # Next steps
    sections.append("### Next Steps")
    sections.append(
        "Your Care Advisor will:\n"
        "- Match you with communities in your target area\n"
        "- Request actual pricing quotes\n"
        "- Review contracts and fee schedules\n"
        "- Help you compare options side-by-side"
    )
    
    return "\n\n".join(sections)


def generate_header(result: Dict[str, Any]) -> str:
    """Generate explanation header."""
    
    care_type_labels = {
        "assisted_living": "Assisted Living",
        "memory_care": "Memory Care",
        "memory_care_high_acuity": "High-Acuity Memory Care",
        "in_home_care": "In-Home Care",
        "homemaker_care": "Homemaker Services",
        "home_with_carry": "In-Home Care (with Family Support)"
    }
    
    care_label = care_type_labels.get(result["care_type"], result["care_type"])
    total = result["total_monthly"]
    confidence = result["confidence"].capitalize()
    
    return (
        f"# Cost Estimate: {care_label}\n"
        f"**Estimated Monthly Cost:** ${total:,.0f}\n"
        f"**Confidence Level:** {confidence}"
    )


def generate_breakdown_table(result: Dict[str, Any]) -> str:
    """Generate cost breakdown table."""
    
    lines = ["## Cost Breakdown", "", "| Component | Amount |", "|-----------|--------|"]
    
    for item in result["breakdown"]:
        label = item["label"]
        amount = item["amount"]
        if amount == 0:
            lines.append(f"| {label} | — |")
        else:
            lines.append(f"| {label} | ${amount:,.2f} |")
    
    # Total line
    total = result["total_monthly"]
    lines.append(f"| **Total Monthly** | **${total:,.2f}** |")
    
    return "\n".join(lines)


def generate_range_section(result: Dict[str, Any]) -> str:
    """Generate range explanation section."""
    
    low = result["low_estimate"]
    likely = result["likely_estimate"]
    high = result["high_estimate"]
    confidence = result["confidence"]
    pct = result["range_pct"] * 100
    
    lines = [
        "## Cost Range",
        f"- **Low:** ${low:,.0f}/month",
        f"- **Most Likely:** ${likely:,.0f}/month",
        f"- **High:** ${high:,.0f}/month",
        "",
        f"**Range Width:** ±{pct:.0f}% ({confidence} confidence)",
        "",
        result["range_explanation"]
    ]
    
    if result.get("widening_factors"):
        lines.append("")
        lines.append("**Factors Affecting Range:**")
        for factor in result["widening_factors"]:
            lines.append(f"- {factor}")
    
    return "\n".join(lines)


def generate_tier_explanation(result: Dict[str, Any]) -> str:
    """Generate tier assignment explanation."""
    
    tier = result["tier"]
    tier_desc = result["tier_description"]
    tier_increment = result["tier_increment"]
    
    lines = [
        f"## Care Tier: {tier}",
        tier_desc
    ]
    
    if tier_increment > 0:
        lines.append(f"\n**Tier Cost:** ${tier_increment:,.2f}/month")
        lines.append(
            "This reflects the additional staffing, training, and resources "
            "required to support the assessed care needs."
        )
    
    return "\n".join(lines)


def generate_addons_explanation(result: Dict[str, Any]) -> str:
    """Generate add-ons explanation."""
    
    addons = result["addons"]
    addon_cap = result["addon_cap"]
    
    lines = [
        "## Additional Services",
        f"*(Capped at ${addon_cap:,.0f} or 15% of regional base, whichever is lower)*",
        ""
    ]
    
    for addon in addons:
        label = addon["label"]
        amount = addon["amount"]
        desc = addon["description"]
        lines.append(f"### {label} (+${amount:,.2f}/month)")
        lines.append(desc)
        lines.append("")
    
    # Total
    addon_total = result["addon_total"]
    lines.append(f"**Total Additional Services:** ${addon_total:,.2f}/month")
    
    return "\n".join(lines)


def generate_sources_section(result: Dict[str, Any]) -> str:
    """Generate data sources section."""
    
    care_type = result["care_type"]
    base_cost = result.get("base_cost") or result.get("hourly_base")
    
    source = get_base_cost_source(care_type)
    is_derived = is_base_cost_derived(care_type)
    
    lines = [
        "## Data Sources",
        f"**Base Cost:** ${base_cost:,.2f}/month"
    ]
    
    if is_derived:
        lines.append(f"*Source:* {source['name']} (derived)")
        lines.append(f"*Notes:* {source['notes']}")
    else:
        lines.append(f"*Source:* [{source['name']}]({source['url']})")
    
    lines.append("")
    lines.append("**Regional Multiplier:** Based on local market analysis and community surveys")
    lines.append("**Tier Increments:** Based on industry staffing cost analysis and provider fee schedules")
    
    return "\n".join(lines)


def generate_advisor_notes(result: Dict[str, Any]) -> str:
    """Generate advisor-specific notes."""
    
    care_type = result["care_type"]
    confidence = result["confidence"]
    
    lines = ["## Advisor Notes"]
    
    # Confidence guidance
    if confidence == "high":
        lines.append(
            "✓ **High confidence estimate:** Care needs are stable. Most communities "
            "should fall within the likely range (±7%)."
        )
    elif confidence == "medium":
        lines.append(
            "⚠️ **Moderate confidence estimate:** Some variability expected. Get quotes from "
            "3-5 communities to narrow the range."
        )
    else:  # low
        lines.append(
            "⚠️ **Lower confidence estimate:** Significant market variation exists. "
            "Recommend getting quotes from 5+ specialized communities and discussing specific "
            "care plans to understand pricing."
        )
    
    # Care type specific notes
    lines.append("")
    if care_type == "memory_care_high_acuity":
        lines.append(
            "**High-Acuity Memory Care:** Few communities offer this level of care. "
            "Focus on communities with specialized dementia units, secured environments, "
            "and 24/7 clinical staffing."
        )
    elif care_type == "in_home_care":
        hours = result.get("hours_per_week", 0)
        if hours >= 40:
            lines.append(
                f"**High-Hour In-Home Care ({hours} hrs/week):** Consider comparing "
                "with assisted living/memory care costs. Facility care may provide "
                "better value at this hour level."
            )
    
    return "\n".join(lines)


def get_care_type_specific_inclusions(care_type: str) -> str:
    """Get care type specific inclusions for family explanation."""
    
    if care_type == "assisted_living":
        return "Personal care assistance based on needs"
    elif care_type == "memory_care":
        return "Specialized memory care programming and secured environment"
    elif care_type == "memory_care_high_acuity":
        return "24/7 specialized dementia care with intensive clinical oversight"
    else:
        return ""


def generate_comparison_table(results: List[Dict[str, Any]]) -> str:
    """
    Generate side-by-side comparison table for multiple care options.
    
    Args:
        results: List of calculation results from calculate_care_costs()
    
    Returns:
        Formatted comparison table
    """
    
    if not results:
        return ""
    
    lines = ["# Care Cost Comparison", ""]
    
    # Header
    header = "| Care Type | Monthly Cost | Range | Confidence |"
    separator = "|-----------|--------------|-------|------------|"
    lines.extend([header, separator])
    
    # Rows
    for result in results:
        care_type = result["care_type"].replace("_", " ").title()
        monthly = result["total_monthly"]
        low = result["low_estimate"]
        high = result["high_estimate"]
        confidence = result["confidence"].capitalize()
        
        row = f"| {care_type} | ${monthly:,.0f} | ${low:,.0f} - ${high:,.0f} | {confidence} |"
        lines.append(row)
    
    lines.append("")
    lines.append("*All estimates based on same regional multiplier and assessment data*")
    
    return "\n".join(lines)


def generate_quick_summary(result: Dict[str, Any]) -> str:
    """
    Generate 2-3 sentence quick summary for hub display.
    
    Args:
        result: Calculation result from calculate_care_costs()
    
    Returns:
        Brief summary text
    """
    
    care_type = result["care_type"].replace("_", " ").title()
    likely = result["likely_estimate"]
    low = result["low_estimate"]
    high = result["high_estimate"]
    confidence = result["confidence"]
    
    summary = (
        f"{care_type} costs are estimated at ${likely:,.0f}/month, "
        f"with a range of ${low:,.0f} to ${high:,.0f}. "
    )
    
    if confidence == "high":
        summary += "This is a high-confidence estimate based on stable, predictable care needs."
    elif confidence == "medium":
        summary += "Range reflects some variability in how communities price these care needs."
    else:
        summary += "Range is wider due to market variation for complex care requirements."
    
    return summary
