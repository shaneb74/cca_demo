# Streamlit Cloud Audio Feature Setup

## Status
✅ All code changes committed and pushed to `origin/dev`
✅ Local testing completed successfully
⏳ Awaiting Streamlit Cloud secrets configuration

## Commits Included (Latest First)
1. `d0386d9` - Initialize audio_cache in session state on page load
2. `e096b3c` - Clear audio validation cache when navigating back to FAQ page
3. `1ef7361` - Prevent empty string submission when toggling voice responses
4. `f53255d` - Improve config persistence and error handling for audio feature
5. `b4338e0` - Strip Markdown formatting before TTS synthesis
6. `d9a3914` - Show expanded warning when ElevenLabs config is missing
7. `7ddaf0a` - Centralize config management to prevent API key loss across reruns
8. `819c83e` - Enable FAQ audio feature by default
9. `43cd7aa` - Add ElevenLabs FAQ audio feature

## Required Streamlit Cloud Secrets

Navigate to: **Streamlit Cloud Dashboard → Your App → Settings → Secrets**

Add the following in TOML format:

```toml
# ElevenLabs Text-to-Speech API
ELEVENLABS_API_KEY = "sk_d1c455c20d569fd2fbbb82ca4821f3d8ef5d203d18ec3dd9"
ELEVENLABS_VOICE_ID = "h8fE15wgH3MZaYwKHXyg"

# Audio Playback Settings
AUDIO_PLAYBACK_SPEED = "0.95"
AUDIO_STABILITY = "0.5"
AUDIO_SIMILARITY = "0.93"
AUDIO_STYLE = "0.15"

# Feature Flag (optional - defaults to "on" in code)
FEATURE_FAQ_AUDIO = "on"
```

## What to Expect After Adding Secrets

1. **App Restart**: Streamlit Cloud will automatically restart your app
2. **Configuration Loading**: Check logs for `[CONFIG] ✓ ElevenLabs API key loaded`
3. **FAQ Page**: 
   - Warning should disappear
   - 🔊 Enable voice responses toggle should appear
   - Audio should work when toggle is enabled

## Testing Checklist

- [ ] Navigate to FAQ page
- [ ] Verify toggle appears (no warning)
- [ ] Enable toggle
- [ ] Ask a question (type or use button)
- [ ] First audio: Click play manually (browser security)
- [ ] Ask second question: Should auto-play
- [ ] Navigate away and return: Verify toggle still works
- [ ] Test recommended question buttons
- [ ] Verify Markdown not read ("asterisk asterisk")

## Troubleshooting

### If Warning Still Appears:
1. Check secrets are saved correctly (no typos)
2. Check logs for `[CONFIG]` messages
3. Click "🔄 Retry Configuration" button
4. Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+R)

### If Audio Says "Unavailable":
1. Check browser console for errors
2. Verify API key in logs: `[FAQ_AUDIO] ✓ API key loaded`
3. Check ElevenLabs account credits/status
4. Try clearing audio cache (refresh page)

## Architecture Notes

- **Centralized Config**: `core/config.py` with `@st.cache_resource`
- **TTS Client**: `shared/audio/tts_client.py`
- **Session Cache**: Audio responses cached per session to save API calls
- **Markdown Stripping**: All formatting removed before synthesis
- **Page Navigation**: Cache cleared and revalidated on return to FAQ

## Voice Settings Explained

- **Playback Speed** (0.95): Slightly slower for clarity
- **Stability** (0.5): Balanced consistency vs expressiveness
- **Similarity** (0.93): Very close to cloned voice
- **Style** (0.15): Subtle natural variation

## Feature Flag Options

- `on`: Feature enabled (default)
- `off`: Feature disabled, toggle hidden
