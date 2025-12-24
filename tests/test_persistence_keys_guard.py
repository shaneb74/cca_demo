"""
Guard test for USER_PERSIST_KEYS contract.

This test ensures that changes to the persistence keys are intentional and reviewed.
If the test fails, update the expected list AND include "BYPASS_SESSION_STORE_GUARD"
in your commit message to signal that you've reviewed the migration impact.
"""

import importlib


def test_user_persist_keys_contract():
    """Snapshot test: USER_PERSIST_KEYS must not change without explicit review."""
    ss = importlib.import_module("core.session_store")
    assert hasattr(ss, "USER_PERSIST_KEYS"), "USER_PERSIST_KEYS is missing"

    keys = sorted(list(ss.USER_PERSIST_KEYS))

    # Snapshot: update intentionally with review if the contract changes.
    # These keys represent the persistence contract between app restarts.
    # Renaming or removing keys can cause data loss for existing users.
    expected = sorted([
        "auth",
        "cost_planner_v2_assets",
        "cost_planner_v2_complete",
        "cost_planner_v2_health_insurance",
        "cost_planner_v2_income",
        "cost_planner_v2_life_insurance",
        "cost_planner_v2_published",
        "cost_planner_v2_va_benefits",
        "cost_v2_advisor_notes",
        "cost_v2_current_module",
        "cost_v2_guest_mode",
        "cost_v2_modules",
        "cost_v2_qualifiers",
        "cost_v2_quick_estimate",
        "cost_v2_schedule_advisor",
        "cost_v2_step",
        "cost_v2_triage",
        "flags",
        "gcp_care_recommendation",
        "gcp_v4_complete",
        "gcp_v4_published",
        "mcip_contracts",
        "preferences",
        "product_tiles_v2",
        "profile",
        "progress",
        "tiles",
    ])

    assert keys == expected, (
        f"USER_PERSIST_KEYS changed:\n"
        f"  Expected: {expected}\n"
        f"  Got:      {keys}\n"
        f"If intentional, update the expected list in this test and include "
        f'"BYPASS_SESSION_STORE_GUARD" in the commit message.'
    )


if __name__ == "__main__":
    test_user_persist_keys_contract()
    print("✅ USER_PERSIST_KEYS contract check passed")
