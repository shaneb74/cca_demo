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
    if helper_text:
        helper_text = html_escape(helper_text)

    title_text = html_escape(copy.get("page_title", ""))
    lead_text = html_escape(copy.get("lead", ""))

    points = [point for point in copy.get("points", []) if point]
    
    # Build clean info cards for key points
    cards_html = ""
    if points:
        card_icons = ["🎯", "💬", "⏱️"]  # Icons for different points
        cards = ""
        for i, point in enumerate(points[:3]):  # Limit to 3 cards
            icon = card_icons[i] if i < len(card_icons) else "✓"
            cards += f"""
                <div class="info-card">
                    <div class="info-icon">{icon}</div>
                    <p class="info-text">{html_escape(point)}</p>
                </div>
            """
        cards_html = f'<div class="info-cards">{cards}</div>'

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
          
          /* === Navi Intro Card (Compact) === */
          .navi-intro-card {
            background: linear-gradient(135deg, #f0f4ff 0%, #f8f9fe 100%);
            border: 2px solid #e0e7ff;
            border-radius: 12px;
            padding: 1.25rem;
            margin: 0 0 2rem;
            box-shadow: 0 2px 8px rgba(124, 92, 255, 0.1);
          }
          .navi-intro-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
          }
          .navi-intro-icon {
            font-size: 1.25rem;
          }
          .navi-intro-title {
            font-size: 1rem;
            font-weight: 600;
            color: #0E1E54;
            margin: 0;
          }
          .navi-intro-message {
            font-size: 0.95rem;
            color: #4b4f63;
            line-height: 1.5;
            margin: 0;
          }
          
          /* === Main Title === */
          .page-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #0E1E54;
            text-align: center;
            margin: 2rem 0 1rem;
            line-height: 1.2;
          }
          
          /* === Lead Text === */
          .lead-text {
            font-size: 1.1rem;
            color: #4b4f63;
            text-align: center;
            max-width: 700px;
            margin: 0 auto 1.5rem;
            line-height: 1.6;
          }
          
          /* === Helper Text === */
          .helper-text {
            font-size: 1rem;
            color: #1f3c88;
            font-weight: 600;
            text-align: center;
            margin: 0 0 2rem;
          }
          
          /* === Info Cards Grid === */
          .info-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin: 0 0 2rem;
          }
          
          .info-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 1.5rem;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
            text-align: center;
          }
          
          .info-card:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            transform: translateY(-2px);
          }
          
          .info-icon {
            font-size: 2rem;
            margin-bottom: 0.75rem;
          }
          
          .info-text {
            font-size: 0.95rem;
            color: #4b4f63;
            line-height: 1.5;
            margin: 0;
          }
          
          /* === CTA Section === */
          .cta-section {
            background: linear-gradient(135deg, #f8f9fe 0%, #f0f4ff 100%);
            border: 1px solid #e0e7ff;
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            margin: 2rem 0 0;
          }
          
          .cta-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #0E1E54;
            margin: 0 0 0.5rem;
          }
          
          .cta-subtitle {
            font-size: 0.95rem;
            color: #6b7280;
            margin: 0 0 1.5rem;
          }
          
          /* === Mobile Responsive === */
          @media (max-width: 768px) {
            .page-title {
              font-size: 2rem;
            }
            .lead-text {
              font-size: 1rem;
            }
            .info-cards {
              grid-template-columns: 1fr;
              gap: 1rem;
            }
            .info-card {
              padding: 1.25rem;
            }
            .cta-section {
              padding: 1.5rem;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Build layout HTML
    navi_intro = f"""
        <div class="navi-intro-card">
            <div class="navi-intro-header">
                <span class="navi-intro-icon">✨</span>
                <span class="navi-intro-title">NAVI</span>
            </div>
            <p class="navi-intro-message">{lead_text if lead_text else "Answer these questions to match the right level of support."}</p>
        </div>
    """

    layout_html = f"""
        <div id="gcp-intro">
          {navi_intro}
          <h1 class="page-title">{title_text if title_text else "Let's get you the right support"}</h1>
          {f'<p class="helper-text">{helper_text}</p>' if helper_text else ''}
          {cards_html}
          <div class="cta-section">
            <h3 class="cta-title">Ready to begin?</h3>
            <p class="cta-subtitle">This assessment takes about 2 minutes and saves automatically.</p>
          </div>
        </div>
    """

    st.markdown(layout_html, unsafe_allow_html=True)


def should_use_custom_intro() -> bool:
    current_step_id = st.session_state.get("gcp_current_step_id", "")
    return current_step_id == "intro"


def render_custom_intro_if_needed() -> bool:
    if should_use_custom_intro():
        render_intro_step()
        return True
    return False
