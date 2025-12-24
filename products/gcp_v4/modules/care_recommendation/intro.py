"""
GCP v4 Intro Page - Custom centered layout with refreshed copy

Goals:
- Keep Navi header from product shell untouched
- Introduce warmer, context-aware lead copy with bullet reminders
- Maintain hero image on the right with subtle tilt
"""

import json
from html import escape as html_escape
from typing import Any

import streamlit as st

from core.content_contract import build_token_context, resolve_content


@st.cache_resource
def _load_planning_bytes() -> bytes | None:
    try:
        with open("assets/images/planning.png", "rb") as f:
            return f.read()
    except Exception:
        return None


def load_intro_overrides() -> dict[str, Any]:
    """Load intro copy overrides from config, supporting legacy filename."""
    paths = [
        "config/gcp_intro.overrides.json",
        "config/gcp_intro_overrides.json",
    ]
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return {}


def render_intro_step() -> None:
    """Render simple intro matching Discovery Learning aesthetic - hero title, Navi box, brief text, CTA."""
    # Resolve content (overrides + tokens) using current session context
    ctx = build_token_context(st.session_state, snapshot=None)
    overrides = load_intro_overrides()
    resolved = resolve_content({"copy": overrides.get("copy", {})}, context=ctx)
    copy = resolved.get("copy", {})

    # Determine helper copy based on who the plan is for
    relationship = st.session_state.get("planning_for_relationship", "")
    relationship_type = st.session_state.get("relationship_type", "")
    is_self = relationship == "self" or relationship_type == "Myself"

    helper_text = copy.get("helper_self") if is_self else copy.get("helper_supporter")
    if not helper_text:
        helper_text = copy.get("helper")

    title_text = copy.get("page_title", "")
    person_name = st.session_state.get("person_name", "")

    # Clean CSS matching Discovery Learning style
    st.markdown(
        """
        <style>
          /* Page Title */
          .gcp-page-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #0E1E54;
            text-align: center;
            margin: 2rem 0 1rem;
            line-height: 1.2;
          }
          
          /* Hero Subtitle */
          .gcp-hero-subtitle {
            font-size: 1.1rem;
            color: #4b4f63;
            text-align: center;
            max-width: 700px;
            margin: 0 auto 2rem;
            line-height: 1.6;
          }
          
          /* Navi Card at Top */
          .gcp-navi-card {
            background: linear-gradient(135deg, #f0f4ff 0%, #f8f9fe 100%);
            border: 2px solid #e0e7ff;
            border-radius: 12px;
            padding: 1.5rem;
            margin: 0 0 2rem;
            box-shadow: 0 2px 8px rgba(124, 92, 255, 0.1);
          }
          
          .gcp-navi-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
          }
          
          .gcp-navi-greeting {
            font-size: 1.25rem;
            font-weight: 600;
            color: #0E1E54;
          }
          
          .gcp-navi-intro {
            font-size: 1rem;
            color: #4b4f63;
            line-height: 1.6;
            margin: 0;
          }
          
          /* Simple text paragraphs */
          .gcp-text-section {
            font-size: 1rem;
            color: #4b4f63;
            line-height: 1.7;
            margin: 1.5rem 0;
            max-width: 680px;
            margin-left: auto;
            margin-right: auto;
          }
          
          .gcp-text-section strong {
            color: #0E1E54;
          }
          
          /* CTA Box */
          .gcp-cta-box {
            background: #f8f9fe;
            border: 1px solid #e0e7ff;
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            margin: 2rem auto 0;
            max-width: 500px;
          }
          
          .gcp-cta-title {
            font-size: 1.15rem;
            font-weight: 600;
            color: #0E1E54;
            margin: 0 0 0.5rem;
          }
          
          .gcp-cta-subtitle {
            font-size: 0.95rem;
            color: #6b7280;
            margin: 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Hero title
    default_title = "Let's Find the Right Level of Care"
    st.markdown(f'<h1 class="gcp-page-title">{html_escape(title_text) if title_text else default_title}</h1>', unsafe_allow_html=True)
    
    # Subtitle
    if helper_text:
        st.markdown(f'<p class="gcp-hero-subtitle">{html_escape(helper_text)}</p>', unsafe_allow_html=True)
    
    # Navi intro box
    name_display = f", {person_name}" if person_name else ""
    st.markdown(f"""
        <div class="gcp-navi-card">
            <div class="gcp-navi-header">
                <span style="font-size: 1.5rem;">✨</span>
                <span class="gcp-navi-greeting">What to Expect</span>
            </div>
            <p class="gcp-navi-intro">Hi{name_display}! I'll guide you through a quick assessment about daily activities, cognitive health, and care needs. Your answers help us recommend the right level of support—whether that's home care, assisted living, memory care, or skilled nursing.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Simple explanatory text
    st.markdown("""
        <div class="gcp-text-section">
            <p><strong>This assessment takes about 2 minutes.</strong> We'll ask about things like bathing, dressing, mobility, memory, and any behavioral challenges. Be as honest as possible—there are no wrong answers, and your responses help us find the best care match.</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="gcp-text-section">
            <p>After we understand the needs, you'll receive a personalized care recommendation. From there, we'll help you explore costs, understand your options, and connect with verified providers.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # CTA box
    st.markdown("""
        <div class="gcp-cta-box">
            <div class="gcp-cta-title">Ready to begin?</div>
            <p class="gcp-cta-subtitle">Your progress saves automatically as you go</p>
        </div>
    """, unsafe_allow_html=True)


def render_custom_intro_if_needed() -> bool:
    """Render custom intro - called by engine.py when on intro step.
    
    Engine already verified we're on the right step, so just render.
    """
    print("[GCP_INTRO] render_custom_intro_if_needed() called")
    try:
        render_intro_step()
        print("[GCP_INTRO] render_intro_step() completed successfully")
        return True
    except Exception as e:
        print(f"[GCP_INTRO] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


