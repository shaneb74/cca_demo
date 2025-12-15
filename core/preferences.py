"""
Customer Preferences System - CRM Matching Enhancement

Collects and manages customer preferences for enhanced community matching.
Integrates with MCIP for persistence and CRM QuickBase integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st


@dataclass
class CustomerPreferences:
    """Streamlined customer preferences for QuickBase community matching."""

    # ESSENTIAL: Person receiving care (for CRM records)
    care_recipient_name: str = ""  # Full name (legacy compatibility)
    first_name: str = ""  # First name for CRM customer creation
    last_name: str = ""   # Last name for CRM customer creation
    
    # ESSENTIAL: Geographic matching (ZIP + radius for precise location)
    zip_code: str = ""  # ZIP code for location-based search
    search_radius: str = "25"  # Search radius in miles ("10", "25", "50", etc.)
    
    # ESSENTIAL: Timeline urgency (QuickBase Field 59 - Vacancy matching)  
    move_timeline: str = "exploring"  # "immediate", "1_2_months", "exploring"
    
    # ESSENTIAL: Care level confirmation (QuickBase Field 21 - Care Type)
    care_environment_preference: str = "assisted_living"  # Confirms GCP recommendation
    
    # DETAILED COMMUNITY FEATURES: QuickBase checkbox field matching
    medical_features: List[str] = field(default_factory=list)  # ["hoyer_lift", "house_doctor", etc.]
    accommodation_features: List[str] = field(default_factory=list)  # ["full_kitchen", "air_conditioning", etc.]
    amenity_features: List[str] = field(default_factory=list)  # ["pool", "water_view", etc.]
    lifestyle_features: List[str] = field(default_factory=list)  # ["allows_pets", "accepts_smokers", etc.]
    
    # LEGACY COMPATIBILITY: Keep preferred_regions for backward compatibility
    preferred_regions: List[str] = field(default_factory=list)  # DEPRECATED - use zip_code + search_radius
    
    # Metadata
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "3.2"  # Schema version - now includes ZIP + radius location
    completion_status: str = "partial"  # "partial", "complete"


class PreferencesManager:
    """Manages customer preferences persistence and integration with MCIP."""
    
    @classmethod
    def get_preferences(cls) -> CustomerPreferences | None:
        """Get current customer preferences from MCIP contracts.
        
        Returns:
            CustomerPreferences object or None if not collected yet
        """
        # Check MCIP contracts first
        contracts = st.session_state.get("mcip_contracts", {})
        pref_data = contracts.get("customer_preferences")
        
        if pref_data:
            return CustomerPreferences(**pref_data)
        
        # Fallback to session state (temporary storage)
        pref_data = st.session_state.get("customer_preferences")
        if pref_data:
            return CustomerPreferences(**pref_data)
        
        return None
    
    @classmethod
    def save_preferences(cls, preferences: CustomerPreferences) -> None:
        """Save customer preferences to MCIP contracts for persistence.
        
        Args:
            preferences: CustomerPreferences object to save
        """
        from dataclasses import asdict
        
        # Update timestamp
        preferences.updated_at = datetime.now().isoformat()
        
        # Save to MCIP contracts (persistent across sessions)
        if "mcip_contracts" not in st.session_state:
            st.session_state["mcip_contracts"] = {}
        
        st.session_state["mcip_contracts"]["customer_preferences"] = asdict(preferences)
        
        # Also save to session state for immediate access
        st.session_state["customer_preferences"] = asdict(preferences)
        
        # Log event for tracking
        from core.events import log_event
        log_event(
            "preferences.updated",
            {
                "completion_status": preferences.completion_status,
                "move_timeline": preferences.move_timeline,
                "care_environment": preferences.care_environment_preference,
                "regions_count": len(preferences.preferred_regions),
            }
        )
    
    @classmethod
    def create_default_preferences(cls, care_recommendation: str = None) -> CustomerPreferences:
        """Create default preferences based on care recommendation.
        
        Args:
            care_recommendation: Care tier from GCP assessment
            
        Returns:
            CustomerPreferences with smart defaults
        """
        # Set care environment based on GCP recommendation
        care_env = "assisted_living"  # Default
        if care_recommendation:
            care_env = care_recommendation
        
        # Set default ZIP code from cost planner if available
        default_zip = ""
        cost_data = st.session_state.get("cost", {})
        cost_inputs = cost_data.get("inputs", {})
        cost_zip = cost_inputs.get("zip") or st.session_state.get("cost.inputs", {}).get("zip")
        if cost_zip:
            default_zip = cost_zip
        
        return CustomerPreferences(
            care_environment_preference=care_env,
            zip_code=default_zip,
            search_radius="25",  # Default 25 mile radius
            completion_status="partial",
        )
    
    @classmethod
    def get_crm_matching_data(cls) -> dict:
        """Get preferences data optimized for CRM community matching.
        
        Returns:
            Dictionary with essential matching criteria for QuickBase CRM
        """
        preferences = cls.get_preferences()
        if not preferences:
            return {}
        
        # Base data for all care types
        base_data = {
            "care_recipient_name": preferences.care_recipient_name,
            "care_environment": preferences.care_environment_preference,
            "completion_status": preferences.completion_status,
            "last_updated": preferences.last_updated.isoformat() if preferences.last_updated else None,
        }
        
        # Add type-specific data
        if preferences.care_environment_preference == "in_home":
            # In-home care specific data
            import streamlit as st
            in_home_details = st.session_state.get("in_home_care_details", {})
            
            base_data.update({
                "current_living_situation": in_home_details.get("current_living_situation"),
                "care_start_timeline": in_home_details.get("care_start_timeline"),
                "primary_care_needs": in_home_details.get("primary_care_needs", []),
                "care_type": "in_home"
            })
        else:
            # Community care specific data  
            base_data.update({
                "zip_code": preferences.zip_code,
                "search_radius": preferences.search_radius,
                "move_timeline": preferences.move_timeline,
                "care_type": "community",
                # Detailed QuickBase community features for matching
                "medical_features": getattr(preferences, 'medical_features', []),
                "accommodation_features": getattr(preferences, 'accommodation_features', []),
                "amenity_features": getattr(preferences, 'amenity_features', []),
                "lifestyle_features": getattr(preferences, 'lifestyle_features', []),
                # Legacy compatibility
                "preferred_regions": getattr(preferences, 'preferred_regions', []),
            })
        
        return base_data
    
    @classmethod
    def get_completion_percentage(cls) -> int:
        """Calculate completion percentage of essential preferences.
        
        Returns:
            Percentage (0-100) of essential preferences completed
        """
        preferences = cls.get_preferences()
        if not preferences:
            return 0
        
        # Determine care type from environment preference
        is_community_care = preferences.care_environment_preference in [
            "assisted_living", "memory_care", "memory_care_high_acuity", "independent"
        ]
        is_in_home_care = preferences.care_environment_preference == "in_home"
        
        # Count completed essential fields (4 total for both types)
        completed = 0
        total = 4
        
        # 1. Care recipient name (universal)
        if preferences.care_recipient_name.strip():
            completed += 1
        
        if is_community_care:
            # Community care completion logic
            
            # 2. Geographic preferences (ZIP code)
            if preferences.zip_code.strip():
                completed += 1
            
            # 3. Timeline 
            if preferences.move_timeline != "exploring":
                completed += 1
                
            # 4. Care environment confirmation
            if preferences.care_environment_preference in ["assisted_living", "memory_care", "memory_care_high_acuity", "independent"]:
                completed += 1
                
        elif is_in_home_care:
            # In-home care completion logic (check session state for in-home details)
            import streamlit as st
            in_home_details = st.session_state.get("in_home_care_details", {})
            
            # 2. Living situation
            if in_home_details.get("current_living_situation"):
                completed += 1
            
            # 3. Care timeline
            if in_home_details.get("care_start_timeline", "exploring") != "exploring":
                completed += 1
            
            # 4. Care needs
            if in_home_details.get("primary_care_needs"):
                completed += 1
        
        return int((completed / total) * 100)


# Integration functions for other modules
def get_preferences_for_crm() -> Dict[str, Any]:
    """Get preferences data formatted for CRM matching.
    
    Returns:
        Dictionary suitable for CRM community matching algorithms
    """
    return PreferencesManager.get_crm_matching_data()


def is_preferences_collection_complete() -> bool:
    """Check if customer has completed preferences collection.
    
    Returns:
        True if preferences are marked as complete
    """
    preferences = PreferencesManager.get_preferences()
    return preferences and preferences.completion_status == "complete"


def get_preferences_completion_percentage() -> int:
    """Get completion percentage for UI progress indicators.
    
    Returns:
        Percentage (0-100) of preferences completed
    """
    return PreferencesManager.get_completion_percentage()