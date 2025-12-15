"""
ElevenLabs Text-to-Speech Client for FAQ Audio
Provides simple wrapper for synthesizing FAQ answers to speech.

Uses centralized configuration from core.config to ensure API keys
persist across Streamlit reruns and page navigations.
"""

import time
import hashlib
import re
from typing import Optional
import streamlit as st

# Check if requests is available
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Import logging
from core.logging import get_logger
logger = get_logger("audio")

# Import centralized configuration
from core.config import get_elevenlabs_config, validate_elevenlabs_config

# Constants
MAX_TEXT_LENGTH = 2000  # Character limit for synthesis
TIMEOUT_SECONDS = 15
MAX_RETRIES = 1

# Session cache for audio to avoid re-generating same content
if "audio_cache" not in st.session_state:
    st.session_state["audio_cache"] = {}


def _get_cache_key(text: str, voice_id: str) -> str:
    """Generate cache key from text and voice ID"""
    combined = f"{text}|{voice_id}"
    return hashlib.md5(combined.encode()).hexdigest()


def _strip_markdown(text: str) -> str:
    """
    Remove Markdown formatting from text before TTS synthesis
    
    Handles:
    - Bold: **text** or __text__
    - Italic: *text* or _text_
    - Links: [text](url)
    - Code: `code` or ```code```
    - Headers: # Header
    - Lists: - item or * item or 1. item
    - Blockquotes: > quote
    - Strikethrough: ~~text~~
    - HTML tags: <tag>
    """
    # Remove code blocks first (multi-line)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    
    # Convert links to just text (keep link text, discard URL)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove bold/italic (keep text content)
    text = re.sub(r'\*\*\*([^\*]+)\*\*\*', r'\1', text)  # Bold+italic
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)      # Bold
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)          # Italic
    text = re.sub(r'___([^_]+)___', r'\1', text)         # Bold+italic
    text = re.sub(r'__([^_]+)__', r'\1', text)           # Bold
    text = re.sub(r'_([^_]+)_', r'\1', text)             # Italic
    
    # Remove strikethrough
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # Remove headers (keep text)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove blockquote markers
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def synthesize(text: str, voice_id: Optional[str] = None, format: str = "mp3_44100_128") -> Optional[bytes]:
    """
    Synthesize text to speech using ElevenLabs API
    
    Args:
        text: Text to synthesize (max 2000 chars)
        voice_id: ElevenLabs voice ID (defaults to configured voice)
        format: Audio format (default: mp3_44100_128)
    
    Returns:
        MP3 audio bytes or None on failure
    """
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available for audio synthesis")
        return None
    
    # Get configuration from centralized config with retry
    try:
        config = get_elevenlabs_config()
        api_key = config.get("api_key")
    except Exception as e:
        logger.error(f"[FAQ_AUDIO] ❌ Failed to load configuration: {e}")
        return None
    
    # Validate configuration
    if not api_key:
        logger.error("[FAQ_AUDIO] ❌ ElevenLabs API key not loaded from configuration")
        try:
            is_valid, msg = validate_elevenlabs_config()
            if not is_valid:
                logger.error(f"[FAQ_AUDIO] Config validation failed: {msg}")
        except Exception as e:
            logger.error(f"[FAQ_AUDIO] Config validation error: {e}")
        return None
    
    if api_key.startswith("your_"):
        logger.warning("[FAQ_AUDIO] ElevenLabs API key not configured (placeholder detected)")
        return None
    
    # Log successful key load for debugging
    logger.info(f"[FAQ_AUDIO] ✓ API key loaded (length: {len(api_key)})")
    
    # Use configured voice if not specified
    if not voice_id:
        voice_id = config.get("voice_id") or "h8fE15wgH3MZaYwKHXyg"
    
    # Strip Markdown formatting before synthesis
    clean_text = _strip_markdown(text)
    logger.info(f"[FAQ_AUDIO] Stripped Markdown: {len(text)} -> {len(clean_text)} chars")
    
    # Truncate if too long
    if len(clean_text) > MAX_TEXT_LENGTH:
        logger.warning(f"Text truncated from {len(clean_text)} to {MAX_TEXT_LENGTH} chars")
        clean_text = clean_text[:MAX_TEXT_LENGTH] + "..."
    
    # Check cache first (using cleaned text)
    # Ensure cache exists (defensive programming)
    if "audio_cache" not in st.session_state:
        st.session_state["audio_cache"] = {}
    
    cache_key = _get_cache_key(clean_text, voice_id)
    if cache_key in st.session_state["audio_cache"]:
        logger.info(f"[FAQ_AUDIO] Cache hit for {len(clean_text)} chars")
        return st.session_state["audio_cache"][cache_key]
    
    # Prepare API request
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    # Get voice settings from config
    payload = {
        "text": clean_text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": float(config.get("stability", 0.5)),
            "similarity_boost": float(config.get("similarity", 0.93)),
            "style": float(config.get("style", 0.15)),
            "use_speaker_boost": True
        }
    }
    
    # Attempt synthesis with retry
    start_time = time.time()
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.info(f"[FAQ_AUDIO] Synthesizing {len(clean_text)} chars (attempt {attempt + 1}/{MAX_RETRIES + 1})")
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=TIMEOUT_SECONDS
            )
            
            if response.status_code == 200:
                audio_bytes = response.content
                duration = time.time() - start_time
                
                # Log success
                word_count = len(clean_text.split())
                logger.info(
                    f"[FAQ_AUDIO] faq_audio_synth | "
                    f"len={word_count} words | "
                    f"voice_id={voice_id} | "
                    f"duration={duration:.2f}s"
                )
                
                # Cache result (ensure cache exists)
                if "audio_cache" not in st.session_state:
                    st.session_state["audio_cache"] = {}
                st.session_state["audio_cache"][cache_key] = audio_bytes
                
                return audio_bytes
            
            elif response.status_code >= 500 and attempt < MAX_RETRIES:
                # Retry on server errors
                logger.warning(f"[FAQ_AUDIO] Server error {response.status_code}, retrying...")
                time.sleep(1)
                continue
            
            else:
                # Client error or final retry failure
                logger.error(
                    f"[FAQ_AUDIO] audio_synth_fail | "
                    f"status={response.status_code} | "
                    f"error={response.text[:200]}"
                )
                return None
        
        except requests.Timeout:
            logger.error(f"[FAQ_AUDIO] audio_synth_fail | error=timeout after {TIMEOUT_SECONDS}s")
            return None
        
        except Exception as e:
            logger.error(f"[FAQ_AUDIO] audio_synth_fail | error={str(e)}")
            return None
    
    return None


def clear_audio_cache():
    """Clear the audio cache (useful for memory management)"""
    if "audio_cache" in st.session_state:
        cache_size = len(st.session_state["audio_cache"])
        st.session_state["audio_cache"].clear()
        logger.info(f"[FAQ_AUDIO] Cleared {cache_size} cached audio clips")
