# core/base_hub.py
from __future__ import annotations

from html import escape as html_escape
from pathlib import Path
from typing import Any

import streamlit as st

from layout import render_page


def _inject_hub_css_once() -> None:
    """Load global + hub + product styles once per Streamlit session."""
    key = "_sn_hub_css_loaded_v4"
    if st.session_state.get(key):
        return

    here = Path(__file__).resolve().parent
    groups = [
        [Path("assets/css/global.css"), here.parents[1] / "assets" / "css" / "global.css"],
        [Path("assets/css/hubs.css"), here.parents[1] / "assets" / "css" / "hubs.css"],
        [Path("assets/css/products.css"), here.parents[1] / "assets" / "css" / "products.css"],
        [Path("assets/css/modules.css"), here.parents[1] / "assets" / "css" / "modules.css"],
    ]

    ordered_paths: list[Path] = []
    for group in groups:
        for css_path in group:
            if css_path not in ordered_paths:
                ordered_paths.append(css_path)

    seen: set[str] = set()
    for css_path in ordered_paths:
        try:
            if not css_path.is_file():
                continue
            resolved = str(css_path.resolve())
            if resolved in seen:
                continue
            css = css_path.read_text(encoding="utf-8")
            if "</style>" in css.lower():
                continue
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
            seen.add(resolved)
        except Exception:
            continue

    st.session_state[key] = True


# -----------------------------
# Primary hub renderer (namespaced shell)
# -----------------------------
def render_dashboard_body(
    *,
    title: str = "",
    subtitle: str | None = None,
    chips: list[dict[str, str]] | None = None,
    hub_guide_block: Any | None = None,
    hub_order: dict[str, Any] | None = None,
    cards: list[Any] | None = None,
    cards_html: str | None = None,
    series_steps: list[dict[str, Any]] | None = None,
    additional_services: list[dict[str, Any]] | None = None,
) -> str:
    _inject_hub_css_once()

    chips = chips or []
    series_steps = series_steps or []
    card_items = list(cards or [])

    head_segments: list[str] = []
    if any([title, subtitle, chips, series_steps]):
        head_segments.append('<div class="dashboard-head">')
        if title:
            head_segments.append(f'<h1 class="dashboard-title">{html_escape(str(title))}</h1>')
        if subtitle:
            head_segments.append(f'<p class="dashboard-subtitle">{html_escape(str(subtitle))}</p>')
        if series_steps:
            head_segments.append('<div class="series-steps" role="list">')

            def _sanitize_modifier(value: str) -> str:
                return "".join(
                    ch for ch in value.lower().replace(" ", "-") if ch.isalnum() or ch in {"-", "_"}
                )

            for idx, item in enumerate(series_steps, start=1):
                label = html_escape(str(item.get("label", "")))
                step_value = item.get("step")
                try:
                    number = int(step_value)
                except (TypeError, ValueError):
                    number = idx
                number_html = html_escape(str(number))
                state = item.get("state") or item.get("variant") or ""
                modifier = _sanitize_modifier(str(state)) if state else ""
                cls = "series-chip"
                if modifier:
                    cls += f" is-{modifier}"
                head_segments.append(
                    f'<span class="{cls}" role="listitem">'
                    f'<span class="series-chip__number">{number_html}</span>'
                    f'<span class="series-chip__label">{label}</span>'
                    "</span>"
                )
            head_segments.append("</div>")
        if chips:
            head_segments.append('<div class="dashboard-breadcrumbs">')
            for chip in chips:
                cls = "dashboard-chip" + (" is-muted" if chip.get("variant") == "muted" else "")
                head_segments.append(
                    f'<span class="{cls}">{html_escape(str(chip.get("label", "")))}</span>'
                )
            head_segments.append("</div>")
        head_segments.append("</div>")
    head_html = "".join(head_segments)

    guide_html = ""
    if isinstance(hub_guide_block, str):
        guide_html = hub_guide_block
    elif hub_guide_block:
        # Legacy dict support: render simple eyebrow/title/body/actions structure.
        if isinstance(hub_guide_block, dict) and "html" in hub_guide_block:
            guide_html = str(hub_guide_block.get("html") or "")
        else:
            eyebrow = html_escape(str(hub_guide_block.get("eyebrow", "")))
            title_text = html_escape(str(hub_guide_block.get("title", "")))
            body_text = html_escape(str(hub_guide_block.get("body", "")))
            actions = hub_guide_block.get("actions") or []
            action_html: list[str] = []
            for action in actions:
                label = html_escape(str(action.get("label", "Open")))
                go = html_escape(str(action.get("route") or action.get("go") or ""))
                action_html.append(f'<a href="?go={go}" class="btn btn--secondary">{label}</a>')
            guide_html = "".join(
                [
                    '<section class="hub-guide">',
                    f'<div class="hub-guide__eyebrow">{eyebrow}</div>' if eyebrow else "",
                    f'<h2 class="hub-guide__title">{title_text}</h2>' if title_text else "",
                    f'<p class="hub-guide__text">{body_text}</p>' if body_text else "",
                    (
                        '<div class="hub-guide__actions">' + "".join(action_html) + "</div>"
                        if action_html
                        else ""
                    ),
                    "</section>",
                ]
            )

    # Cards grid (ordered)
    sorted_cards: list[tuple[int, str, Any]] = []
    for c in card_items:
        vis = getattr(c, "visible", True) if hasattr(c, "visible") else c.get("visible", True)
        if not vis:
            continue
        order = getattr(c, "order", 100) if hasattr(c, "order") else int(c.get("order", 100))
        t = getattr(c, "title", "") if hasattr(c, "title") else c.get("title", "")
        sorted_cards.append((int(order), str(t).casefold(), c))
    sorted_cards.sort(key=lambda x: (x[0], x[1]))

    card_html_chunks: list[str] = []
    for _, __, card in sorted_cards:
        if hasattr(card, "render_html"):
            chunk = card.render_html()
            if chunk:
                card_html_chunks.append(chunk)
        elif isinstance(card, dict) and card.get("html"):
            card_html_chunks.append(str(card["html"]))

    grid_html = ""
    if card_html_chunks:
        grid_html = '<div class="dashboard-grid">' + "".join(card_html_chunks) + "</div>"
    elif cards_html:
        grid_html = cards_html

    # Additional services (optional) - Build as HTML string, don't render with st.markdown
    additional_html = ""

    # Check if GCP is complete
    gcp_prog = float(st.session_state.get("tiles", {}).get("gcp_v4", {}).get("progress", 0))
    if gcp_prog == 0:
        # Fallback to legacy gcp key
        gcp_prog = float(st.session_state.get("tiles", {}).get("gcp", {}).get("progress", 0))

    if additional_services:
        # Initialize expanded partner tracking
        if "expanded_partner" not in st.session_state:
            st.session_state.expanded_partner = None

        # Build section header
        additional_chunks = [
            '<section class="dashboard-additional">',
            '<header class="dashboard-additional__head">',
            '<h3 class="dashboard-additional__title">Additional services</h3>',
            '<p class="dashboard-muted">Curated partner solutions that complement your plan.</p>',
            "</header>",
            '<div class="dashboard-additional__grid">',
        ]

        # Build each service card as pure HTML
        for idx, s in enumerate(additional_services):
            partner_id = s.get("id")
            is_expanded = st.session_state.get("expanded_partner") == partner_id

            subtitle_val = s.get("subtitle")
            cta_label = html_escape(str(s.get("cta", "Open")))
            cta_route = html_escape(str(s.get("go", "")))

            # Check if partner has connection config (for inline expansion)
            partner_data = s.get("_raw_partner_data")
            has_connection = (
                partner_data and partner_data.get("connection") if partner_data else False
            )

            # Apply personalization styling
            personalization = s.get("personalization")
            card_class = "dashboard-additional__card"
            label_html = ""

            if personalization == "personalized":
                card_class += " service-tile-personalized"
                label_html = '<div class="personalized-label">✨ Navi Recommended</div>'

            if is_expanded:
                card_class += " is-expanded"

            # Build card HTML
            additional_chunks.append(f'<div class="{card_class}" id="service-{partner_id}">')
            if label_html:
                additional_chunks.append(label_html)
            additional_chunks.append(f"<h4>{html_escape(str(s.get('title', '')))}</h4>")
            if subtitle_val:
                additional_chunks.append(f"<p>{html_escape(str(subtitle_val))}</p>")

            # CTA link - always use HTML link for consistency
            additional_chunks.append(
                f'<a class="dashboard-additional__cta" href="?go={cta_route}">{cta_label}</a>'
            )

            additional_chunks.append("</div>")  # Close card

        # Close grid and section
        additional_chunks.append("</div>")  # Close grid
        additional_chunks.append("</section>")  # Close section

        additional_html = "".join(additional_chunks)
    elif gcp_prog >= 100:
        # GCP complete but no services (user didn't trigger any flags)
        # Don't show anything - the partner-powered services section will still appear below
        additional_html = ""
    # If GCP not complete, don't show anything (section will appear after completion)

    shell = "".join(
        [
            '<section class="sn-hub dashboard-shell">',
            '<div class="container dashboard-shell__inner">',
            head_html,
            guide_html,
            grid_html,
            additional_html,
            "</div>",
            "</section>",
        ]
    )

    return shell


# -----------------------------
# Back-compat helpers
# -----------------------------
def status_label(progress: float | int | None, locked: bool = False) -> str:
    """Legacy helper that returns a simple status string."""
    if locked:
        return "Locked"
    if progress is None:
        return ""
    try:
        p = float(progress)
    except Exception:
        p = 0.0
    if p >= 100:
        return "Complete"
    if p > 0:
        return "In progress"
    return "New"


class BaseHub:
    """
    Legacy wrapper so old hubs that did:

        from core.base_hub import BaseHub
        hub = BaseHub()
        hub.render(title=..., cards=[...])

    still work. Internally delegates to render_dashboard.
    """

    def __init__(self, **default_kwargs):
        self._default_kwargs = dict(default_kwargs or {})

    def render(self, **kwargs) -> None:
        payload: dict[str, Any] = {}
        if hasattr(self, "build_dashboard"):
            try:
                payload = self.build_dashboard() or {}
            except Exception:
                payload = {}

        merged = {**self._default_kwargs, **payload, **kwargs}

        show_header = merged.pop("show_header", True)
        show_footer = merged.pop("show_footer", True)
        active_route = merged.pop("active_route", None)

        body_keys = {
            "title",
            "subtitle",
            "chips",
            "hub_guide_block",
            "hub_order",
            "cards",
            "cards_html",
            "series_steps",
            "additional_services",
        }

        # Legacy aliases
        if "guide" in merged and "hub_guide_block" not in merged:
            merged["hub_guide_block"] = merged["guide"]
        if "additional" in merged and "additional_services" not in merged:
            merged["additional_services"] = merged["additional"]

        body_kwargs = {k: merged.get(k) for k in body_keys if k in merged}
        body_html = render_dashboard_body(**body_kwargs)

        render_page(
            body_html=body_html,
            show_header=show_header,
            show_footer=show_footer,
            active_route=active_route,
        )


__all__ = ["render_dashboard_body", "BaseHub", "status_label", "_inject_hub_css_once"]
