"""
Senior Trivia & Brain Games Product Router

A gamified learning and engagement product for seniors in the Waiting Room.
Offers multiple trivia modules covering care knowledge, entertainment, Medicare,
healthy habits, and family-friendly challenges.

Features:
- Points and badges for completing modules
- Instant feedback on each question
- Progress tracking across modules
- Fun, accessible, educational content
"""

import streamlit as st

from core.modules.engine import run_module
from core.modules.schema import FieldDef, ModuleConfig, StepDef
from core.navi import render_navi_panel
from ui.product_shell import product_shell_end, product_shell_start


def render():
    """Render Senior Trivia & Brain Games product.

    Flow:
    1. Show module selection hub
    2. User selects a trivia game
    3. Run selected module via module engine
    4. Custom results page with score, breakdown, badges
    5. Return to module hub or waiting room
    """

    product_shell_start()

    try:
        # Check if a specific module is selected
        module_key = st.session_state.get("senior_trivia_current_module")

        if module_key:
            # Load module config
            config = _load_module_config(module_key)

            # Check if we're on results step
            state_key = config.state_key
            current_step_index = st.session_state.get(f"{state_key}._step", 0)
            current_step = (
                config.steps[current_step_index] if current_step_index < len(config.steps) else None
            )
            is_results = (
                current_step
                and config.results_step_id
                and current_step.id == config.results_step_id
            )

            # Only render Navi panel if NOT on results (results will render its own)
            if not is_results:
                render_navi_panel(
                    location="product", product_key="senior_trivia", module_config=config
                )

            # Run module engine (will call custom results if on results step)
            module_state = run_module(config)

            # If on results, render custom trivia results page
            if is_results:
                outcome_key = f"{state_key}._outcomes"
                outcome = st.session_state.get(outcome_key)
                if outcome:
                    _render_trivia_results(module_key, config, module_state, outcome)
        else:
            # Show module selection hub
            _render_module_hub()

    finally:
        product_shell_end()


def _render_trivia_results(
    module_key: str, config: ModuleConfig, module_state: dict, outcome: dict
):
    """Render custom trivia results page.

    Args:
        module_key: Module identifier
        config: Module configuration
        module_state: Module state with answers
        outcome: Outcome dict from scoring function
    """
    from core.events import log_event
    from core.ui import render_navi_panel_v2

    summary = outcome.get("summary", {})
    score_pct = summary.get("score_percentage", "0")
    correct_count = summary.get("correct_count", 0)
    total_questions = summary.get("total_questions", 0)
    badge_name = summary.get("badge_name", "")
    badge_level = summary.get("badge_level", "")
    question_breakdown = outcome.get("question_breakdown", [])

    # ========================================
    # 1. SINGLE NAVI PANEL WITH SCORE
    # ========================================
    navi_title = "Quiz Complete!"
    navi_reason = f"You scored {score_pct}%! {_get_score_encouragement(float(score_pct))}"

    render_navi_panel_v2(
        title=navi_title,
        reason=navi_reason,
        encouragement={
            "icon": "👍",
            "text": "You're doing great—keep going!",
            "status": "complete",
        },
        context_chips=[],
        primary_action={"label": "", "route": ""},
        variant="module",
    )

    st.markdown("<div style='margin: 32px 0;'></div>", unsafe_allow_html=True)

    # ========================================
    # 2. SCORE CALLOUT
    # ========================================
    st.markdown(f"### You scored {score_pct}%")
    st.markdown(
        f"**{correct_count}** out of **{total_questions}** correct • Badge earned: **{badge_name}**"
    )
    st.markdown("<div style='margin: 24px 0;'></div>", unsafe_allow_html=True)

    # ========================================
    # 3. QUESTION BREAKDOWN - "Why You Got This Score"
    # ========================================
    with st.expander("🔍 Why You Got This Score", expanded=False):
        st.markdown("**Question-by-question breakdown** (wrong answers first):")
        st.markdown("")

        for idx, q in enumerate(question_breakdown, 1):
            is_correct = q.get("is_correct", False)
            icon = "✅" if is_correct else "❌"

            st.markdown(f"**{idx}. {q.get('question_text', '')}**")
            st.markdown(f"{icon} Your answer: **{q.get('user_answer', 'Not answered')}**")

            if not is_correct:
                st.markdown(f"✔️ Correct answer: **{q.get('correct_answer', 'Unknown')}**")

            feedback = q.get("feedback", "")
            if feedback:
                st.markdown(f"💡 {feedback}")

            st.markdown("---")

    st.markdown("<div style='margin: 32px 0;'></div>", unsafe_allow_html=True)

    # ========================================
    # 4. AWARD AND PERSIST BADGE
    # ========================================
    _award_and_persist_badge(module_key, badge_name, badge_level, score_pct)

    # ========================================
    # 5. TELEMETRY
    # ========================================
    log_event(
        "trivia_complete",
        {
            "module_id": module_key,
            "score_percent": score_pct,
            "correct_count": correct_count,
            "total_questions": total_questions,
            "badge_level": badge_level,
        },
    )

    # ========================================
    # 6. ACTION BUTTONS (no duplicates)
    # ========================================
    st.markdown("<div style='margin: 32px 0;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Try Again", key="retry_quiz", type="primary", use_container_width=True):
            # Emit telemetry
            log_event("trivia_retry", {"module_id": module_key})

            # Clear module state to restart fresh
            _clear_module_state(module_key)

            st.rerun()

    with col2:
        if st.button("🏠 Back to Trivia Hub", key="back_to_trivia_hub", use_container_width=True):
            st.session_state["senior_trivia_current_module"] = None
            st.rerun()

    # Tertiary action - back to lobby
    st.markdown("<div style='margin: 16px 0;'></div>", unsafe_allow_html=True)
    if st.button("← Return to Lobby", key="back_to_lobby", use_container_width=False):
        st.session_state["senior_trivia_current_module"] = None
        # Navigate to lobby (preserve UID to maintain session)
        from core.nav import route_to

        route_to("hub_lobby")


def _get_score_encouragement(score: float) -> str:
    """Get encouraging message based on score.

    Args:
        score: Score percentage (0-100)

    Returns:
        Encouraging message
    """
    if score >= 90:
        return "Outstanding! You're a trivia master! 🎯"
    elif score >= 70:
        return "Great job! You really know your stuff! 🌟"
    elif score >= 50:
        return "Nice work! You're learning a lot! 💪"
    else:
        return "Thanks for playing! Every question teaches something new! 📚"


def _award_and_persist_badge(module_key: str, badge_name: str, badge_level: str, score_pct: str):
    """Award and persist a badge to the user's trivia progress.

    Stores badges in product_tiles_v2 for cross-session persistence.
    Also updates the legacy "tiles" structure for MCIP/Navi compatibility.

    Args:
        module_key: Module identifier
        badge_name: Badge display name
        badge_level: Badge level (bronze/silver/gold/platinum)
        score_pct: Score percentage string
    """
    from core.events import log_event

    # Initialize product_tiles_v2 if not exists
    if "product_tiles_v2" not in st.session_state:
        st.session_state["product_tiles_v2"] = {}

    tiles_v2 = st.session_state["product_tiles_v2"]

    # Initialize senior_trivia_hub tile state if not exists
    if "senior_trivia_hub" not in tiles_v2:
        tiles_v2["senior_trivia_hub"] = {
            "badges_earned": {},  # {module_key: {name, level, score}}
            "total_points": 0,
            "modules_completed": [],
        }

    progress = tiles_v2["senior_trivia_hub"]

    # Check if badge already exists or is an upgrade
    existing_badge = progress["badges_earned"].get(module_key)
    is_new_badge = existing_badge is None
    is_upgrade = False

    if existing_badge:
        level_hierarchy = ["bronze", "silver", "gold", "platinum"]
        old_level_idx = level_hierarchy.index(existing_badge.get("level", "bronze"))
        new_level_idx = level_hierarchy.index(badge_level)
        is_upgrade = new_level_idx > old_level_idx

    # Award or upgrade badge
    if is_new_badge or is_upgrade:
        progress["badges_earned"][module_key] = {
            "name": badge_name,
            "level": badge_level,
            "score": score_pct,
        }

        # Add to modules completed if new
        if module_key not in progress["modules_completed"]:
            progress["modules_completed"].append(module_key)

        # Calculate points
        score_float = float(score_pct)
        points = int(score_float)  # 1 point per percent
        progress["total_points"] = sum(
            float(b.get("score", 0)) for b in progress["badges_earned"].values()
        )

        # Update legacy tiles structure for MCIP/Navi compatibility
        tiles_legacy = st.session_state.setdefault("tiles", {})
        trivia_hub_tile = tiles_legacy.setdefault("senior_trivia", {})

        # Calculate aggregate progress (quizzes completed / total quizzes)
        # Note: Condition-triggered quizzes (diabetes, COPD, etc.) are tracked but not required for 100%
        total_quizzes = (
            5  # truths_myths, music_trivia, medicare_quiz, healthy_habits, community_challenge
        )
        completed_count = len(progress["badges_earned"])
        progress_pct = int((completed_count / total_quizzes) * 100)

        trivia_hub_tile["progress"] = progress_pct
        trivia_hub_tile["status"] = (
            "done" if progress_pct >= 100 else ("doing" if progress_pct > 0 else "new")
        )
        trivia_hub_tile["badges_earned"] = progress["badges_earned"].copy()
        trivia_hub_tile["last_updated"] = st.session_state.get("_timestamp", "")

        # Emit telemetry
        log_event(
            "trivia_badge_awarded",
            {
                "module_id": module_key,
                "badge": badge_name,
                "level": badge_level,
                "is_upgrade": is_upgrade,
                "total_progress": progress_pct,
            },
        )

        # Show success message
        if is_upgrade:
            st.success(f"🎉 Badge upgraded to **{badge_name}**!")
        else:
            st.success(f"🎉 You earned the **{badge_name}** badge!")


def _has_diabetes_condition() -> bool:
    """Check if user has diabetes as a chronic condition.

    Checks:
    1. Primary: medical.conditions.chronic[] contains diabetes
    2. Alternate: chronic_present flag + diabetes in conditions

    Returns:
        True if diabetes condition is present
    """
    try:
        from core.flag_manager import get_active, get_chronic_conditions

        # Check chronic conditions list for diabetes
        conditions = get_chronic_conditions()
        for condition in conditions:
            if condition.get("code") == "diabetes":
                return True

        # Alternate: check if chronic_present flag active AND diabetes in list
        # (handles edge case where flag exists but condition list not yet synced)
        active_flags = get_active()
        if "chronic_present" in active_flags:
            # Recheck conditions list in case of race condition
            for condition in conditions:
                code = condition.get("code", "").lower()
                if "diabetes" in code or "diabetic" in code:
                    return True

        return False
    except Exception:
        # Graceful degradation if flag_manager unavailable
        return False


def _clear_module_state(module_key: str):
    """Clear all state for a specific trivia module to allow fresh start.

    Args:
        module_key: Module identifier (e.g., "truths_myths")
    """
    # Build state key (matches ModuleConfig.state_key pattern: "trivia_{module_id}")
    # Note: module JSON files have "id" field that matches module_key
    state_key = f"trivia_{module_key}"

    # Clear module engine state
    keys_to_clear = [
        state_key,
        f"{state_key}._step",
        f"{state_key}._outcomes",
        f"{state_key}._timestamp",
    ]

    for key in keys_to_clear:
        st.session_state.pop(key, None)

    # Clear tile state for this specific module (from ENGINE tile system)
    # Product key uses "senior_trivia_" prefix for tile storage
    # NOTE: Module engine uses "tiles" (old system), not "product_tiles_v2"
    tiles = st.session_state.get("tiles", {})
    product_key = f"senior_trivia_{module_key}"
    if product_key in tiles:
        tiles[product_key].pop("saved_state", None)
        tiles[product_key].pop("last_step", None)


def _render_module_hub():
    """Render the trivia module selection hub with earned badges."""
    st.markdown("## 🎯 Senior Trivia & Brain Games")
    st.markdown(
        "Choose a trivia game to play. Each game takes 3-5 minutes and earns you points and badges!"
    )

    # Return to Lobby button
    if st.button("← Return to Lobby", key="return_to_lobby", use_container_width=False):
        # Clear current module selection
        st.session_state.pop("senior_trivia_current_module", None)
        # Navigate to lobby (preserve UID to maintain session)
        from core.nav import route_to

        route_to("hub_lobby")

    st.markdown("<div style='margin: 24px 0;'></div>", unsafe_allow_html=True)

    # Get earned badges from persisted tile state
    tiles = st.session_state.get("product_tiles_v2", {})
    progress = tiles.get("senior_trivia_hub", {})
    badges_earned = progress.get("badges_earned", {})

    # Check for condition-triggered modules (diabetes)
    has_diabetes = _has_diabetes_condition()

    # Module cards
    modules = [
        {
            "key": "truths_myths",
            "title": "🏡 Truths & Myths about Senior Living",
            "desc": "Test your knowledge about assisted living, memory care, and financial planning",
            "time": "4 min",
            "questions": 8,
        },
        {
            "key": "music_trivia",
            "title": "🎵 Music & Entertainment (1950s-1980s)",
            "desc": "Classic songs, artists, TV shows, and cultural touchstones",
            "time": "5 min",
            "questions": 8,
        },
        {
            "key": "medicare_quiz",
            "title": "🏥 Medicare Enrollment Know-How",
            "desc": "Learn about enrollment periods, coverage, and common mistakes",
            "time": "4 min",
            "questions": 8,
        },
        {
            "key": "healthy_habits",
            "title": "💪 Healthy Habits & Longevity",
            "desc": "Evidence-based tips for mobility, nutrition, and mental well-being",
            "time": "5 min",
            "questions": 8,
        },
        {
            "key": "community_challenge",
            "title": "👨‍👩‍👧‍👦 Community Challenge / Family Trivia",
            "desc": "Play together with family! Fun questions for all generations",
            "time": "4 min",
            "questions": 8,
        },
    ]

    # Add condition-triggered modules at the TOP of the list
    if has_diabetes:
        # Check if badge earned to determine badge status
        diabetes_badge = badges_earned.get("diabetes_knowledge")
        diabetes_module = {
            "key": "diabetes_knowledge",
            "title": "🩸 Diabetes Knowledge Check",
            "desc": "Quick, fun questions to help you stay sharp about managing diabetes",
            "time": "4 min",
            "questions": 6,
            "badge_status": "🆕 New" if not diabetes_badge else None,
            "condition_triggered": True,
        }
        # Insert at the TOP of the list (index 0) to make it prominent
        modules.insert(0, diabetes_module)

    for module in modules:
        # Check if badge earned for this module
        badge_info = badges_earned.get(module["key"])

        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                # Title with badge status if condition-triggered and new
                title = module["title"]
                if module.get("condition_triggered") and module.get("badge_status"):
                    title += f" {module['badge_status']}"
                st.markdown(f"### {title}")
                st.markdown(module["desc"])

                # Show badge if earned
                if badge_info:
                    badge_name = badge_info.get("name", "")
                    score = badge_info.get("score", "0")
                    st.markdown(
                        f"⏱️ {module['time']} • {module['questions']} questions • **{badge_name}** ({score}%)"
                    )
                else:
                    st.markdown(f"⏱️ {module['time']} • {module['questions']} questions")

            with col2:
                button_label = "Play Again" if badge_info else "Play"
                if st.button(button_label, key=f"play_{module['key']}", use_container_width=True):
                    # Clear any existing state for this module before starting/restarting
                    _clear_module_state(module["key"])

                    # Set current module and restart
                    st.session_state["senior_trivia_current_module"] = module["key"]
                    st.rerun()
            st.markdown("---")


def _load_module_config(module_key: str) -> ModuleConfig:
    """Load module configuration for the specified trivia game.

    Converts trivia JSON format to ModuleConfig for module engine.

    Args:
        module_key: Key of the trivia module (e.g., "truths_myths")

    Returns:
        ModuleConfig object for module engine
    """
    import json
    from pathlib import Path

    module_path = Path(__file__).parent / "modules" / f"{module_key}.json"

    with open(module_path) as f:
        data = json.load(f)

    module_meta = data.get("module", {})
    sections = data.get("sections", [])

    # Convert sections to steps
    steps = []
    for section in sections:
        step = _convert_section_to_step(section)
        if step:
            steps.append(step)

    return ModuleConfig(
        product=f"senior_trivia_{module_key}",  # Unique product key per quiz module
        version=module_meta.get("version", "v2025.10"),
        steps=steps,
        state_key=f"trivia_{module_meta.get('id', module_key)}",
        outcomes_compute="products.senior_trivia.scoring:compute_trivia_outcome",
        results_step_id=module_meta.get("results_step_id", "results"),
        skip_default_results=True,  # Use custom trivia results renderer
    )


def _convert_section_to_step(section: dict) -> StepDef:
    """Convert a trivia JSON section to a StepDef.

    Args:
        section: Section dict from trivia JSON

    Returns:
        StepDef object for module engine
    """
    section_type = section.get("type", "questions")
    section_id = section["id"]
    title = section.get("title", "")
    description = section.get("description", "")

    # Handle info sections (intro pages)
    if section_type == "info":
        return StepDef(
            id=section_id,
            title=title,
            subtitle=description,
            icon=None,
            fields=[],
            content=section.get("content"),
            next_label="Start Quiz" if section_id == "intro" else "Continue",
            skip_label=None,
            show_progress=False,
            show_bottom_bar=True,
            summary_keys=None,
        )

    # Handle results section
    if section_type == "results":
        return StepDef(
            id=section_id,
            title=title,
            subtitle=description,
            icon="🎯",
            fields=[],
            next_label="Continue",
            skip_label=None,
            show_progress=True,
            show_bottom_bar=True,
            summary_keys=None,
        )

    # Handle question sections
    questions = section.get("questions", [])
    fields = [_convert_question_to_field(q) for q in questions]

    return StepDef(
        id=section_id,
        title=title,
        subtitle=description,
        icon=None,
        fields=fields,
        next_label="Continue",
        skip_label=None,
        show_progress=True,
        show_bottom_bar=True,
        summary_keys=None,
    )


def _convert_question_to_field(question: dict) -> FieldDef:
    """Convert a trivia question to a FieldDef.

    Args:
        question: Question dict from trivia JSON

    Returns:
        FieldDef object for module engine
    """
    question_id = question["id"]
    question_type = question.get("type", "string")
    select_type = question.get("select", "single")
    ui_config = question.get("ui", {})

    return FieldDef(
        key=question_id,
        label=question.get("label", ""),
        type=_convert_type(question_type, select_type, ui_config),
        help=question.get("help"),
        required=question.get("required", False),
        options=question.get("options", []),
        min=question.get("min"),
        max=question.get("max"),
        step=question.get("step"),
        placeholder=question.get("placeholder"),
        default=question.get("default"),
        visible_if=None,
        write_key=None,
        a11y_hint=None,
        prefill_from=None,
        ask_if_missing=False,
        ui=ui_config,
        effects=[],
    )


def _convert_type(question_type: str, select_type: str, ui: dict = None) -> str:
    """Convert trivia type to FieldDef type.

    Args:
        question_type: Type from JSON ("string", "number", etc.)
        select_type: Select type ("single", "multi")
        ui: UI configuration dict with widget preference

    Returns:
        FieldDef type string matching component renderer names
    """
    widget = (ui or {}).get("widget", "")

    # Single-select types - use chip widget for trivia
    if question_type == "string" and select_type == "single":
        if widget == "chip":
            return "pill"  # Chip widget uses pill renderer
        elif widget == "dropdown":
            return "dropdown"
        else:
            return "radio"

    # Multi-select types
    elif question_type == "string" and select_type == "multi":
        if widget == "multi_chip":
            return "chip_multi"
        return "multiselect"

    # Number types
    elif question_type == "number":
        return "number"

    # Boolean types
    elif question_type == "boolean":
        return "yesno"

    # Default to text
    else:
        return "text"
