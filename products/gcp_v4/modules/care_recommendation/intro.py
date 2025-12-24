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
    """Render the custom intro step with clean card-based layout matching app aesthetic."""
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
    lead_text = copy.get("lead", "")

    points = [point for point in copy.get("points", []) if point]

    # Inject clean CSS matching Discovery Learning and Hub aesthetic
    st.markdown(
        """
        <style>
          /* === Page Container === */
          #gcp-intro {
            max-width: 900px;
            margin: 0 auto;
            padding: 0 24px 32px;
          }
          
          /* === Main Title === */
          .gcp-page-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #0E1E54;
            text-align: center;
            margin: 1rem 0 1rem;
            line-height: 1.2;
          }
          
          /* === Helper Text === */
          .gcp-helper-text {
            font-size: 1rem;
            color: #1f3c88;
            font-weight: 600;
            text-align: center;
            margin: 0 0 2rem;
          }
          
          /* === Info Cards Grid === */
          .gcp-info-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin: 0 0 2rem;
          }
          
          .gcp-info-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 1.5rem;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
            text-align: center;
          }
          
          .gcp-info-card:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            transform: translateY(-2px);
          }
          
          .gcp-info-icon {
            font-size: 2rem;
            margin-bottom: 0.75rem;
          }
          
          .gcp-info-text {
            font-size: 0.95rem;
            color: #4b4f63;
            line-height: 1.5;
            margin: 0;
          }
          
          /* === CTA Section === */
          .gcp-cta-section {
            background: linear-gradient(135deg, #f8f9fe 0%, #f0f4ff 100%);
            border: 1px solid #e0e7ff;
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            margin: 2rem 0 0;
          }
          
          .gcp-cta-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #0E1E54;
            margin: 0 0 0.5rem;
          }
          
          .gcp-cta-subtitle {
            font-size: 0.95rem;
            color: #6b7280;
            margin: 0;
          }
          
          /* === Mobile Responsive === */
          @media (max-width: 768px) {
            .gcp-page-title {
              font-size: 2rem;
            }
            .gcp-info-cards {
              grid-template-columns: 1fr;
              gap: 1rem;
            }
            .gcp-info-card {
              padding: 1.25rem;
            }
            .gcp-cta-section {
              padding: 1.5rem;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Build title
    st.markdown(f'<h1 class="gcp-page-title">{html_escape(title_text) if title_text else "Let\'s get you the right support"}</h1>', unsafe_allow_html=True)
    
    # Helper text
    if helper_text:
        st.markdown(f'<p class="gcp-helper-text">{html_escape(helper_text)}</p>', unsafe_allow_html=True)
    
    # Build info cards using columns for better rendering
    if points:
        card_icons = ["🎯", "💬", "⏱️"]
        
        st.markdown('<div class="gcp-info-cards">', unsafe_allow_html=True)
        
        cols = st.columns(len(points[:3]))
        for i, point in enumerate(points[:3]):
            icon = card_icons[i] if i < len(card_icons) else "✓"
            with cols[i]:
                st.markdown(f"""
                    <div class="gcp-info-card">
                        <div class="gcp-info-icon">{icon}</div>
                        <p class="gcp-info-text">{html_escape(point)}</p>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # CTA section
    st.markdown("""
        <div class="gcp-cta-section">
            <h3 class="gcp-cta-title">Ready to begin?</h3>
            <p class="gcp-cta-subtitle">This assessment takes about 2 minutes and saves automatically.</p>
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


