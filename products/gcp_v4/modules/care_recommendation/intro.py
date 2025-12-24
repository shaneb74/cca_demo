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
    """Render simple, informative intro that sets clear expectations."""
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

    # Simple CSS for clean, content-focused layout
    st.markdown(
        """
        <style>
          .gcp-intro-title {
            font-size: 2rem;
            font-weight: 700;
            color: #0E1E54;
            margin: 0 0 0.75rem;
          }
          
          .gcp-intro-helper {
            font-size: 1rem;
            color: #1f3c88;
            margin: 0 0 2rem;
          }
          
          .gcp-intro-section {
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin: 1.5rem 0;
          }
          
          .gcp-intro-section h3 {
            font-size: 1.1rem;
            font-weight: 600;
            color: #0E1E54;
            margin: 0 0 0.75rem;
          }
          
          .gcp-intro-section p,
          .gcp-intro-section ul {
            font-size: 0.95rem;
            color: #4b4f63;
            line-height: 1.6;
            margin: 0;
          }
          
          .gcp-intro-section ul {
            padding-left: 1.25rem;
            margin-top: 0.5rem;
          }
          
          .gcp-intro-section li {
            margin-bottom: 0.5rem;
          }
          
          .gcp-intro-section li:last-child {
            margin-bottom: 0;
          }
          
          .gcp-cta-box {
            background: #f8f9fe;
            border: 1px solid #e0e7ff;
            border-radius: 8px;
            padding: 1.25rem;
            text-align: center;
            margin: 1.5rem 0 0;
          }
          
          .gcp-cta-box p {
            font-size: 0.9rem;
            color: #6b7280;
            margin: 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Title
    default_title = "Care Recommendation Assessment"
    st.markdown(f'<h1 class="gcp-intro-title">{html_escape(title_text) if title_text else default_title}</h1>', unsafe_allow_html=True)
    
    # Helper text
    if helper_text:
        st.markdown(f'<p class="gcp-intro-helper">{html_escape(helper_text)}</p>', unsafe_allow_html=True)
    
    # What this assessment does
    st.markdown("""
        <div class="gcp-intro-section">
            <h3>What This Assessment Does</h3>
            <p>We'll ask questions about daily activities and care needs to determine the right level of support. Your answers help us recommend:</p>
            <ul>
                <li><strong>Home care</strong> with professional caregivers coming to the home</li>
                <li><strong>Assisted living</strong> for those who need regular help but want independence</li>
                <li><strong>Memory care</strong> for cognitive support in a specialized environment</li>
                <li><strong>Skilled nursing</strong> for complex medical needs requiring 24/7 care</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    
    # What to expect
    st.markdown("""
        <div class="gcp-intro-section">
            <h3>Questions You'll Answer</h3>
            <p>The assessment covers these key areas:</p>
            <ul>
                <li><strong>Daily activities:</strong> Bathing, dressing, eating, mobility, and toileting</li>
                <li><strong>Household tasks:</strong> Cooking, cleaning, shopping, and medication management</li>
                <li><strong>Cognitive health:</strong> Memory, decision-making, and confusion</li>
                <li><strong>Behavioral needs:</strong> Wandering, agitation, or other challenges</li>
                <li><strong>Medical conditions:</strong> Ongoing health issues requiring support</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    
    # CTA
    st.markdown("""
        <div class="gcp-cta-box">
            <p><strong>Takes about 2 minutes</strong> • Progress saves automatically</p>
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


