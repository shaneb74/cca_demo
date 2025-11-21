from __future__ import annotations

from collections.abc import Iterable
from html import escape as H
from typing import Any

import streamlit as st

from .schema import FieldDef


def _label(label: str, help_text: str | None = None, a11y: str | None = None) -> None:
    from core.text import personalize_text
    
    # Apply personalization to all text content
    personalized_label = personalize_text(label)
    personalized_help = personalize_text(help_text) if help_text else None
    personalized_a11y = personalize_text(a11y) if a11y else None
    
    st.markdown(f"<div class='mod-label'><span>{H(personalized_label)}</span></div>", unsafe_allow_html=True)
    if personalized_help:
        st.markdown(f"<div class='mod-help'>{H(personalized_help)}</div>", unsafe_allow_html=True)
    if personalized_a11y:
        st.markdown(f"<div class='visually-hidden'>{H(personalized_a11y)}</div>", unsafe_allow_html=True)


def _safe_label(label: str | None, fallback: str) -> str:
    from core.text import personalize_text
    import re
    
    candidate = (label or "").strip()
    safe_label = candidate or fallback
    # Apply personalization to the final label
    personalized_label = personalize_text(safe_label)
    
    # Safety: assert no unresolved tokens remain
    if re.search(r"\{NAME(_POS)?\}", personalized_label):
        raise AssertionError(f"Unresolved name token found in label: '{personalized_label}'")
    
    return personalized_label


def _option_labels(options: list[dict[str, Any]] | None) -> list[str]:
    from core.text import personalize_text
    
    if not options:
        return []
    labels = []
    for opt in options:
        label = str(opt.get("label", opt.get("value", "")))
        personalized_label = personalize_text(label)
        labels.append(personalized_label)
    return labels


def _default_index(options: list[dict[str, Any]] | None, default: Any) -> int:
    if not options or default is None:
        return 0
    for idx, opt in enumerate(options):
        if opt.get("value") == default or opt.get("label") == default:
            return idx
    return 0


def _value_from_label(options: list[dict[str, Any]] | None, label: str) -> Any:
    if not options:
        return label
    for opt in options:
        if str(opt.get("label", opt.get("value"))) == label:
            return opt.get("value", opt.get("label"))
    return label


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(v) for v in value]
    return [str(value)]


def input_radio(field: FieldDef, current: Any = None) -> Any:
    import random
    
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    
    # Randomize option order to prevent answer predictability
    # Use field key as seed for consistent ordering across re-renders
    options = field.options or []
    if options:
        random.seed(hash(field.key))
        options = random.sample(options, len(options))
        random.seed()  # Reset seed for other randomness
        
        # Update field.options temporarily for this render
        field.options = options
    
    labels = _option_labels(field.options)
    choice = st.radio(
        label=label,
        options=labels,
        index=_default_index(field.options, current if current is not None else field.default),
        horizontal=True,
        label_visibility="collapsed",
        key=f"{field.key}_radio",
    )
    return _value_from_label(field.options, choice)


def input_pill(field: FieldDef, current: Any = None) -> Any:
    """Render pill-style radio buttons (uses st.radio with custom CSS)."""
    import random
    
    label = _safe_label(field.label, field.key)
    options = field.options or []
    if not options:
        return current if current is not None else field.default

    # Filter out options with empty labels to prevent gray pills
    options = [opt for opt in options if opt.get("label", "").strip()]
    if not options:
        return current if current is not None else field.default

    # Randomize option order to prevent answer predictability
    # Use field key as seed for consistent ordering across re-renders
    random.seed(hash(field.key))
    options = random.sample(options, len(options))
    random.seed()  # Reset seed for other randomness

    # Build value mapping
    labels = [opt.get("label", "") for opt in options]
    label_to_value = {
        opt.get("label", ""): opt.get("value", opt.get("label", "")) for opt in options
    }

    # Get current value and find its label
    current_value = current if current is not None else field.default
    current_label = next(
        (lab for lab, val in label_to_value.items() if val == current_value),
        labels[0] if labels else "",
    )

    # Render with wrapper for custom styling
    st.markdown('<div class="sn-app mod-field mod-radio-pills">', unsafe_allow_html=True)
    
    st.markdown(f"<div class='mod-label'><span>{H(label)}</span></div>", unsafe_allow_html=True)
    if field.help:
        st.markdown(f"<div class='mod-help'>{H(field.help)}</div>", unsafe_allow_html=True)
    if field.a11y_hint:
        st.markdown(
            f"<div class='visually-hidden'>{H(field.a11y_hint)}</div>", unsafe_allow_html=True
        )

    radio_key = f"{field.key}_pill"

    # Calculate index - use current value if available, otherwise default to first option
    # Note: st.radio requires a valid integer index, not None
    if current_label in labels:
        default_index = labels.index(current_label)
    else:
        # No current value - default to first option
        # This ensures single-click selection works for all options
        default_index = 0

    # Use native st.radio with horizontal layout
    choice_label = st.radio(
        label=label,
        options=labels,
        index=default_index,  # Must be valid integer for single-click selection
        horizontal=True,
        label_visibility="collapsed",
        key=radio_key,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    return label_to_value.get(choice_label, choice_label)


def input_dropdown(field: FieldDef, current: Any = None) -> Any:
    import random
    
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    
    # Randomize option order to prevent answer predictability
    # Use field key as seed for consistent ordering across re-renders
    options = field.options or []
    if options:
        random.seed(hash(field.key))
        options = random.sample(options, len(options))
        random.seed()  # Reset seed for other randomness
        
        # Update field.options temporarily for this render
        field.options = options
    
    labels = _option_labels(field.options)
    choice = st.selectbox(
        label=label,
        options=labels,
        index=_default_index(field.options, current if current is not None else field.default),
        label_visibility="collapsed",
        key=f"{field.key}_dropdown",
    )
    return _value_from_label(field.options, choice)


def input_slider(field: FieldDef, current: Any = None) -> Any:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    min_value = float(field.min if field.min is not None else 0.0)
    max_value = float(field.max if field.max is not None else 10.0)
    step = float(field.step if field.step is not None else 1.0)
    default = float(current if current is not None else field.default or min_value)
    return st.slider(
        label=label,
        min_value=min_value,
        max_value=max_value,
        step=step,
        value=default,
        label_visibility="collapsed",
        key=f"{field.key}_slider",
    )


def input_money(field: FieldDef, current: Any = None) -> float:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    default = current if current is not None else field.default or ""
    raw = st.text_input(
        label=label,
        value=str(default),
        placeholder=field.placeholder or "$ 0.00",
        label_visibility="collapsed",
        key=f"{field.key}_money",
    )
    try:
        cleaned = str(raw).replace("$", "").replace(",", "").strip()
        return float(cleaned or 0)
    except Exception:
        return 0.0


def input_yesno(field: FieldDef, current: Any = None) -> bool:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    default_idx = (
        0 if (current is True or (current is None and field.default in (True, "yes", "Yes"))) else 1
    )
    choice = st.radio(
        label=label,
        options=["Yes", "No"],
        index=default_idx,
        horizontal=True,
        label_visibility="collapsed",
        key=f"{field.key}_yesno",
    )
    return choice == "Yes"


def input_text(field: FieldDef, current: Any = None) -> str:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    default = current if current is not None else field.default or ""
    return st.text_input(
        label=label,
        value=str(default),
        placeholder=field.placeholder or "",
        label_visibility="collapsed",
        key=f"{field.key}_text",
    )


def input_textarea(field: FieldDef, current: Any = None) -> str:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    default = current if current is not None else field.default or ""
    return st.text_area(
        label=label,
        value=str(default),
        placeholder=field.placeholder or "",
        label_visibility="collapsed",
        key=f"{field.key}_textarea",
    )


def input_chip_multi(field: FieldDef, current: Any = None) -> list[str]:
    """Render pill-style multi-select (uses st.multiselect with custom CSS)."""
    import random
    
    label = _safe_label(field.label, field.key)
    options = field.options or []
    if not options:
        return _normalize_list(current if current is not None else field.default)

    # Randomize option order to prevent answer predictability
    # Use field key as seed for consistent ordering across re-renders
    random.seed(hash(field.key))
    options = random.sample(options, len(options))
    random.seed()  # Reset seed for other randomness

    # Build value mapping
    labels = [opt.get("label", "") for opt in options]
    label_to_value = {
        opt.get("label", ""): opt.get("value", opt.get("label", "")) for opt in options
    }

    # Get current selected values
    current_values = set(_normalize_list(current if current is not None else field.default))
    default_labels = [lab for lab in labels if label_to_value.get(lab) in current_values]

    # Render with wrapper for custom styling
    st.markdown('<div class="sn-app mod-field mod-multi-pills">', unsafe_allow_html=True)
    st.markdown(f"<div class='mod-label'><span>{H(label)}</span></div>", unsafe_allow_html=True)
    if field.help:
        st.markdown(f"<div class='mod-help'>{H(field.help)}</div>", unsafe_allow_html=True)
    if field.a11y_hint:
        st.markdown(
            f"<div class='visually-hidden'>{H(field.a11y_hint)}</div>", unsafe_allow_html=True
        )

    # Use native st.multiselect
    chosen_labels = st.multiselect(
        label=label,
        options=labels,
        default=default_labels,
        label_visibility="collapsed",
        key=f"{field.key}_chips",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    return [label_to_value[label] for label in chosen_labels]


def input_multi_dropdown(field: FieldDef, current: Any = None) -> list[str]:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)

    options = field.options or []
    labels = [opt.get("label", "") for opt in options]
    label_to_value = {
        opt.get("label", ""): opt.get("value", opt.get("label", "")) for opt in options
    }
    value_to_label = {v: k for k, v in label_to_value.items()}

    selected_values = _normalize_list(current if current is not None else field.default)
    default_labels = [
        value_to_label.get(val, val) for val in selected_values if val in value_to_label
    ]

    chosen_labels = st.multiselect(
        label=label,
        options=labels,
        default=default_labels,
        label_visibility="collapsed",
        key=f"{field.key}_multi",
    )

    return [label_to_value[label] for label in chosen_labels]


def input_pill_list(field: FieldDef, current: Any = None) -> list[str]:
    label = _safe_label(field.label, field.key)
    _label(label, field.help, field.a11y_hint)
    values: list[str] = [str(v) for v in (current or field.default or [])]

    new_value = st.text_input(
        label=label,
        value="",
        placeholder=field.placeholder or "Type an item and press Add",
        label_visibility="collapsed",
        key=f"{field.key}_input",
    )
    add_label = field.ui or "Add"
    if st.button(add_label, key=f"{field.key}_add") and new_value.strip():
        candidate = new_value.strip()
        if candidate not in values:
            values.append(candidate)

    if values:
        chips = " ".join(f"<span class='mod-chip is-active'>{H(v)}</span>" for v in values)
        st.markdown(f"<div class='mod-help'>{chips}</div>", unsafe_allow_html=True)

    return values


RENDERERS = {
    "radio": input_radio,
    "pill": input_pill,
    "dropdown": input_dropdown,
    "slider": input_slider,
    "money": input_money,
    "yesno": input_yesno,
    "text": input_text,
    "textarea": input_textarea,
    "chip_multi": input_chip_multi,
    "pill_list": input_pill_list,
    "multi_dropdown": input_multi_dropdown,
}

RENDERERS["multiselect"] = RENDERERS.get("chip_multi", RENDERERS.get("multi_dropdown"))


__all__ = ["RENDERERS"]
