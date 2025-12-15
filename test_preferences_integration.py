#!/usr/bin/env python3
"""
Test Customer Preferences Integration

Quick test to verify the complete flow:
1. PFMA appointment booking
2. Preferences collection 
3. CRM matching enhancement
"""

from core.preferences import PreferencesManager, CustomerPreferences
from core.mcip import MCIP
import streamlit as st

def test_preferences_flow():
    """Test the complete preferences flow"""
    print("🔄 Testing customer preferences integration...")
    
    # Initialize session state for testing
    if "mcip_contracts" not in st.session_state:
        st.session_state["mcip_contracts"] = {}
    
    # Test 1: Create default preferences
    print("\n📋 Test 1: Creating default preferences...")
    default_prefs = PreferencesManager.create_default_preferences("assisted_living")
    print(f"   Default care environment: {default_prefs.care_environment_preference}")
    print(f"   Default completion status: {default_prefs.completion_status}")
    
    # Test 2: Save preferences
    print("\n💾 Test 2: Saving preferences...")
    test_prefs = CustomerPreferences(
        preferred_regions=["bellevue_area", "eastside"],
        max_distance_miles=15,
        care_environment_preference="assisted_living",
        move_timeline="2_3_months",
        budget_comfort_level="comfortable",
        activity_preferences=["fitness", "social", "arts"],
        primary_family_contact="Sarah (daughter)",
        family_location="nearby",
        current_support_level="family_help",
        move_triggers=["safety_concern", "family_worry"],
        completion_status="complete"
    )
    
    PreferencesManager.save_preferences(test_prefs)
    print("   ✅ Preferences saved successfully")
    
    # Test 3: Retrieve preferences
    print("\n📖 Test 3: Retrieving preferences...")
    retrieved_prefs = PreferencesManager.get_preferences()
    if retrieved_prefs:
        print(f"   Care environment: {retrieved_prefs.care_environment_preference}")
        print(f"   Preferred regions: {retrieved_prefs.preferred_regions}")
        print(f"   Timeline: {retrieved_prefs.move_timeline}")
        print(f"   Family contact: {retrieved_prefs.primary_family_contact}")
        print("   ✅ Preferences retrieved successfully")
    else:
        print("   ❌ Failed to retrieve preferences")
    
    # Test 4: Get CRM matching data
    print("\n🎯 Test 4: Getting CRM matching data...")
    crm_data = PreferencesManager.get_crm_matching_data()
    if crm_data:
        print(f"   Preferred regions: {crm_data.get('preferred_regions')}")
        print(f"   Timeline: {crm_data.get('timeline')}")
        print(f"   Budget level: {crm_data.get('budget_level')}")
        print(f"   Activity preferences: {crm_data.get('activity_preferences')}")
        print("   ✅ CRM matching data formatted successfully")
    else:
        print("   ❌ No CRM matching data available")
    
    # Test 5: Completion percentage
    print("\n📊 Test 5: Checking completion percentage...")
    completion = PreferencesManager.get_completion_percentage()
    print(f"   Completion percentage: {completion}%")
    
    # Test 6: MCIP persistence check
    print("\n🔄 Test 6: Checking MCIP persistence...")
    contracts = st.session_state.get("mcip_contracts", {})
    if "customer_preferences" in contracts:
        stored_prefs = contracts["customer_preferences"]
        print(f"   Stored in MCIP contracts: ✅")
        print(f"   Care environment: {stored_prefs.get('care_environment_preference')}")
        print(f"   Completion status: {stored_prefs.get('completion_status')}")
    else:
        print("   ❌ Preferences not found in MCIP contracts")
    
    print(f"\n✅ Customer preferences integration test complete!")
    return True

if __name__ == "__main__":
    # Mock streamlit session state for testing
    if "session_state" not in globals():
        class MockSessionState:
            def __init__(self):
                self.data = {}
            
            def get(self, key, default=None):
                return self.data.get(key, default)
            
            def __getitem__(self, key):
                return self.data[key]
            
            def __setitem__(self, key, value):
                self.data[key] = value
            
            def __contains__(self, key):
                return key in self.data
        
        st.session_state = MockSessionState()
    
    test_preferences_flow()