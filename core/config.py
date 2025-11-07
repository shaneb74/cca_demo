"""
Centralized Configuration Management

Single source of truth for all environment variables and API keys.
Uses Streamlit's resource caching to persist configuration across reruns
and page navigations, preventing intermittent key loss.

This module should be imported once at app startup and provides cached
access to all configuration values throughout the application lifecycle.
"""

import os
import streamlit as st
from typing import Optional


class ConfigurationError(Exception):
    """Raised when critical configuration is missing or invalid."""
    pass


@st.cache_resource
def load_configuration():
    """
    Load and cache all environment variables and Streamlit secrets.
    
    This function is cached at the resource level, meaning it runs once
    per Streamlit worker process and persists across all reruns and page
    navigations within that process.
    
    Returns:
        dict: Cached configuration dictionary with all environment values
    """
    print("[CONFIG] Loading application configuration...")
    
    # Try to load .env file if it exists (for local development)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("[CONFIG] ✓ .env file loaded")
    except ImportError:
        print("[CONFIG] ⚠️  python-dotenv not available (OK in production)")
    except Exception as e:
        print(f"[CONFIG] ⚠️  Error loading .env: {e}")
    
    config = {}
    
    # Helper function to get value from env or secrets
    def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get value from environment or Streamlit secrets, with fallback."""
        # Try environment variable first
        value = os.getenv(key)
        
        # Try Streamlit secrets if env var not found
        if value is None:
            try:
                value = st.secrets.get(key)
            except (AttributeError, FileNotFoundError):
                pass
        
        # Use default if still not found
        if value is None:
            value = default
        
        return value
    
    # ==============================================================================
    # OpenAI Configuration
    # ==============================================================================
    config["OPENAI_API_KEY"] = get_value("OPENAI_API_KEY")
    config["OPENAI_MODEL"] = get_value("OPENAI_MODEL", "gpt-4o-mini")
    
    if config["OPENAI_API_KEY"]:
        print("[CONFIG] ✓ OpenAI API key loaded")
    else:
        print("[CONFIG] ⚠️  OpenAI API key missing")
    
    # ==============================================================================
    # ElevenLabs Configuration (Text-to-Speech)
    # ==============================================================================
    config["ELEVENLABS_API_KEY"] = get_value("ELEVENLABS_API_KEY")
    config["ELEVENLABS_VOICE_ID"] = get_value("ELEVENLABS_VOICE_ID", "h8fE15wgH3MZaYwKHXyg")
    
    # Audio playback settings with defaults
    config["AUDIO_PLAYBACK_SPEED"] = float(get_value("AUDIO_PLAYBACK_SPEED", "0.95"))
    config["AUDIO_STABILITY"] = float(get_value("AUDIO_STABILITY", "0.5"))
    config["AUDIO_SIMILARITY"] = float(get_value("AUDIO_SIMILARITY", "0.93"))
    config["AUDIO_STYLE"] = float(get_value("AUDIO_STYLE", "0.15"))
    
    if config["ELEVENLABS_API_KEY"]:
        print(f"[CONFIG] ✓ ElevenLabs API key loaded (length: {len(config['ELEVENLABS_API_KEY'])})")
        print(f"[CONFIG] ✓ Voice ID: {config['ELEVENLABS_VOICE_ID']}")
    else:
        print("[CONFIG] ⚠️  ElevenLabs API key missing - audio features will be unavailable")
    
    # ==============================================================================
    # Feature Flags
    # ==============================================================================
    config["FEATURE_LLM_NAVI"] = get_value("FEATURE_LLM_NAVI", "off")
    config["FEATURE_LLM_GCP"] = get_value("FEATURE_LLM_GCP", "off")
    config["FEATURE_FAQ_AUDIO"] = get_value("FEATURE_FAQ_AUDIO", "on")
    config["FEATURE_NAVI_INTELLIGENCE"] = get_value("FEATURE_NAVI_INTELLIGENCE", "on")
    config["FEATURE_ADVISOR_SUMMARY_LLM"] = get_value("FEATURE_ADVISOR_SUMMARY_LLM", "off")
    
    print(f"[CONFIG] ✓ Feature flags loaded: FAQ_AUDIO={config['FEATURE_FAQ_AUDIO']}")
    
    # ==============================================================================
    # Database/Storage Configuration
    # ==============================================================================
    config["QUICKBASE_API_KEY"] = get_value("QUICKBASE_API_KEY")
    config["QUICKBASE_REALM"] = get_value("QUICKBASE_REALM")
    
    print("[CONFIG] Configuration loading complete")
    print(f"[CONFIG] Total keys loaded: {len(config)}")
    
    return config


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a configuration value by key.
    
    This is the main API for accessing configuration throughout the app.
    Values are cached at the resource level and persist across reruns.
    
    Args:
        key: Configuration key to retrieve
        default: Default value if key not found
        
    Returns:
        Configuration value or default
        
    Example:
        >>> api_key = get_config("ELEVENLABS_API_KEY")
        >>> if not api_key:
        >>>     st.error("ElevenLabs API key not configured")
    """
    config = load_configuration()
    return config.get(key, default)


def validate_elevenlabs_config() -> tuple[bool, str]:
    """
    Validate that ElevenLabs configuration is properly loaded.
    
    Returns:
        (is_valid, message) tuple
        
    Example:
        >>> is_valid, msg = validate_elevenlabs_config()
        >>> if not is_valid:
        >>>     st.warning(msg)
    """
    api_key = get_config("ELEVENLABS_API_KEY")
    voice_id = get_config("ELEVENLABS_VOICE_ID")
    
    if not api_key:
        return False, "ElevenLabs API key not configured. Please set ELEVENLABS_API_KEY in environment or Streamlit secrets."
    
    if not voice_id:
        return False, "ElevenLabs Voice ID not configured. Please set ELEVENLABS_VOICE_ID in environment or Streamlit secrets."
    
    # Basic validation of key format
    if not api_key.startswith("sk_"):
        return False, "ElevenLabs API key appears invalid (should start with 'sk_')"
    
    return True, "ElevenLabs configuration valid"


def reload_configuration():
    """
    Force reload of configuration (useful for testing or recovery).
    
    This clears the cache and forces a fresh read of environment variables
    and secrets. Should rarely be needed in production.
    """
    print("[CONFIG] Forcing configuration reload...")
    load_configuration.clear()
    config = load_configuration()
    print(f"[CONFIG] Configuration reloaded: {len(config)} keys")
    return config


def get_elevenlabs_config() -> dict:
    """
    Get all ElevenLabs configuration as a single dict.
    
    Returns:
        dict with keys: api_key, voice_id, playback_speed, stability, similarity, style
    """
    return {
        "api_key": get_config("ELEVENLABS_API_KEY"),
        "voice_id": get_config("ELEVENLABS_VOICE_ID"),
        "playback_speed": get_config("AUDIO_PLAYBACK_SPEED"),
        "stability": get_config("AUDIO_STABILITY"),
        "similarity": get_config("AUDIO_SIMILARITY"),
        "style": get_config("AUDIO_STYLE"),
    }


# Initialize configuration on module import
# This ensures config is loaded once when the app starts
_config = load_configuration()
print(f"[CONFIG] Module initialized with {len(_config)} configuration keys")
