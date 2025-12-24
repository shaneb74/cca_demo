"""
Testing Tools Hub

Internal hub for testing, validation, and refinement tools.
Designed for advisors and developers to validate algorithms and workflows.

TODO: Remove this hub by 2025-12-15 after validation phase complete.
"""

import streamlit as st

from core.product_tile import ProductTileHub
from core.ui import render_navi_panel_v2
from ui.header_simple import render_header_simple
from ui.footer_simple import render_footer_simple


def _build_testing_tiles() -> list[ProductTileHub]:
    """Build testing tool tiles.
    
    Returns:
        List of testing tool tiles
    """
    tiles = []
    
    # GCP Test Tool
    tiles.append(
        ProductTileHub(
            key="gcp_test_tool",
            title="GCP Test Tool",
            desc="Test complete Guided Care Plan logic",
            blurb="Internal tool to validate GCP tier recommendations, cognitive gates, "
                  "behavior gates, and scoring. Uses exact GCP v4 logic for accurate testing. "
                  "Compare deterministic vs LLM recommendations.",
            image_square=None,
            meta_lines=["🎯 Tier validation", "🚪 Gate testing", "📊 Full GCP logic"],
            primary_label="Open GCP Tester",
            primary_route="?page=gcp_test_tool",
            progress=0,
            variant="purple",
            badges=["Testing", "Internal"],
            order=5,
            visible=True,
            locked=False,
        )
    )
    
    # Care Hours Calculator
    tiles.append(
        ProductTileHub(
            key="care_hours_calculator",
            title="Care Hours Calculator",
            desc="Test care hours calculation with direct inputs",
            blurb="Internal tool for advisors to validate hours recommendations. "
                  "Input ADLs, IADLs, cognitive status, and see instant calculations. "
                  "Compare baseline vs LLM recommendations.",
            image_square=None,
            meta_lines=["⚡ Instant calculation", "🧪 Testing tool", "📊 LLM comparison"],
            primary_label="Open Calculator",
            primary_route="?page=care_hours_calculator",
            progress=0,
            variant="purple",
            badges=["Testing", "Internal"],
            order=10,
            visible=True,
            locked=False,
        )
    )
    
    # Cost Planner v3 Test Tool
    tiles.append(
        ProductTileHub(
            key="cost_planner_v3_test",
            title="Cost Planner v3 Test",
            desc="Test tier-based cost calculation engine",
            blurb="Test Cost Planner v3 with GCP outcomes. Input flags, see tier assignments, "
                  "add-on calculations, and confidence ranges. Compare v2 vs v3 side-by-side. "
                  "Validate tier overflow logic (AL→MC→MC-HA).",
            image_square=None,
            meta_lines=["💰 Tier calculation", "📊 v2 vs v3 compare", "🎯 Range confidence"],
            primary_label="Open v3 Tester",
            primary_route="?page=cost_v3_test",
            progress=0,
            variant="blue",
            badges=["Testing", "Phase 1"],
            order=15,
            visible=True,
            locked=False,
        )
    )
    
    return tiles


def render(ctx=None) -> None:
    """Render Testing Tools Hub.
    
    Args:
        ctx: Optional context (unused, for hub interface compatibility)
    """
    # Render header
    render_header_simple(active_route="testing_tools")
    
    # Warning banner
    st.markdown(
        """
        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 16px; margin: 24px 0;">
            <strong>⚠️ Internal Testing Tools</strong><br>
            These tools are for validation and refinement purposes only. 
            They will be removed after validation is complete (target: December 15, 2025).
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Use callback pattern to render Navi AFTER header
    def render_content():
        # Navi panel
        render_navi_panel_v2(
            title="Testing & Validation Tools",
            reason="Use these tools to test algorithms, validate calculations, and refine workflows before deploying to production.",
            encouragement={
                "icon": "🧪",
                "text": "Internal tools for quality assurance",
                "status": "info"
            },
            context_chips=[
                {"label": "Testing Tools"},
                {"label": "Phase 1 Validation", "variant": "muted"},
            ],
            primary_action={"label": "", "route": ""},
            variant="hub"
        )
        
        # Build tiles
        tiles = _build_testing_tiles()
        
        # Render tiles manually using ProductTileHub.render()
        st.markdown("## 🧪 Available Testing Tools")
        st.markdown("")
        
        # Render each tile
        cols = st.columns(min(len(tiles), 3))
        for idx, tile in enumerate(tiles):
            with cols[idx % 3]:
                tile.render()
    
    # Render content with Navi
    render_content()
    
    # Render footer
    render_footer_simple()
