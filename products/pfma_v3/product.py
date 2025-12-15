"""
PFMA v3 - Plan with My Advisor (Booking-First Model)

Enhanced appointment booking with preferences collection:
1. Check prerequisites via MCIP (requires Cost Planner)
2. Show friendly gate if prerequisites missing
3. Single booking form with strict validation
4. Collect customer preferences for CRM matching
5. Publish AdvisorAppointment to MCIP when complete
6. Route to Waiting Room for optional Advisor Prep

Key changes from v2:
- Single step (booking only) vs 5 steps
- Added "More About {Name}" preferences collection
- No verification sections (moved to optional Advisor Prep)
- Enhanced CRM matching data collection
- Booking = complete (no multi-step progress tracking)
"""

import uuid
from datetime import datetime

import streamlit as st

from core.crm_ids import create_lead, convert_to_customer, get_crm_status

from core.events import log_event
from core.mcip import MCIP, AdvisorAppointment
from core.nav import route_to
from core.navi import render_navi_panel
from core.preferences import PreferencesManager, CustomerPreferences


def render():
    """Main entry point for PFMA v3."""

    # Log mount with Cost Planner state
    cost = st.session_state.get("cost", {})
    g = st.session_state.get("gcp", {})

    chosen_path = cost.get("path_choice")
    zip_code = cost.get("inputs", {}).get("zip")
    home_hours = cost.get("home_hours_scalar")
    published_tier = g.get("published_tier")

    print(
        f"[FA_MOUNT] chosen_path={chosen_path} zip={zip_code} "
        f"hours={home_hours} tier={published_tier}"
    )

    # Step 1: Check prerequisites via MCIP
    if not _check_prerequisites():
        # Render Navi for gate screen
        render_navi_panel(location="product", product_key="pfma_v3", module_config=None)
        _render_gate()
        return

    # Step 2: Check appointment and preferences status
    appt = MCIP.get_advisor_appointment()
    preferences = PreferencesManager.get_preferences()
    
    # Check for force booking parameter to show the new booking form
    force_booking = st.query_params.get("force_booking") == "true"
    
    # Check what screen to show based on state
    show_preferences = (
        appt and appt.scheduled and  # Appointment is booked
        not st.session_state.get("pfma_preferences_complete", False) and  # Preferences not marked complete
        not st.session_state.get("pfma_skip_preferences", False) and  # User hasn't chosen to skip
        not force_booking  # Not forcing booking view
    )
    
    if show_preferences:
        # Show preferences collection screen
        render_navi_panel(location="product", product_key="pfma_v3", module_config=None)
        _render_preferences_collection(appt)
        return
    elif appt and appt.scheduled:
        # Already booked and preferences handled - show confirmation
        render_navi_panel(location="product", product_key="pfma_v3", module_config=None)
        _render_confirmation(appt)
        return

    # Step 3: Render Navi panel (single intelligence layer)
    render_navi_panel(location="product", product_key="pfma_v3", module_config=None)

    # Step 4: Render booking form
    _render_booking_form()


# =============================================================================
# PREREQUISITE CHECKING (MCIP Integration)
# =============================================================================


def _check_prerequisites() -> bool:
    """Check if user has completed required products via MCIP.

    Returns:
        True if prerequisites met, False otherwise
    """
    # Require Cost Planner completion
    financial = MCIP.get_financial_profile()
    return financial is not None


def _render_gate():
    """Show friendly gate requiring Cost Planner completion."""
    st.markdown("## 📅 Plan with My Advisor")

    st.info(
        "**Ready to talk to a live advisor?**\n\n"
        "Before scheduling your appointment, please complete the **Cost Planner** "
        "so we can help you have the most productive conversation possible."
    )

    # Show what user has completed
    st.markdown("#### Your Progress")

    care_rec = MCIP.get_care_recommendation()
    financial = MCIP.get_financial_profile()

    col1, col2 = st.columns(2)

    with col1:
        if care_rec:
            st.success("✓ **Guided Care Plan** complete")
        else:
            st.warning("○ Guided Care Plan not started")

    with col2:
        if financial:
            st.success("✓ **Cost Planner** complete")
        else:
            st.error("✗ **Cost Planner required**")

    st.markdown("---")

    if st.button("← Return to Lobby", type="secondary"):
        route_to("hub_lobby")

    if st.button("Go to Cost Planner →", type="primary"):
        # Navigate to Cost Planner v2 auth step (will show fake auth page)
        st.session_state.cost_v2_step = "auth"
        st.query_params["page"] = "cost_v2"
        st.rerun()


# =============================================================================
# BOOKING FORM
# =============================================================================


def _render_booking_form():
    """Render single-step appointment booking form."""

    # Apply clean CSS with proper width constraint
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## 📅 Schedule Your Consultation")

    st.markdown(
        "Book a **free 30-minute consultation** with a care advisor who will help you "
        "navigate options, coordinate benefits, and connect with trusted partners."
    )

    # Initialize form state with contextual prefill from Welcome/Audience
    if "pfma_v3_form" not in st.session_state:
        # Get context from session state
        relationship_type = st.session_state.get("relationship_type", "")
        person_name = st.session_state.get("person_name") or st.session_state.get("planning_for_name", "")
        planning_for = st.session_state.get("planning_for_relationship", "")
        
        # Determine if planning for self
        is_self = (
            relationship_type == "Myself" or 
            planning_for == "self" or
            relationship_type == "Self"
        )
        
        # Set defaults based on context
        if is_self:
            # User is care recipient
            default_relation = "Self"
            default_attendee = person_name if person_name else ""
            default_care_recipient = person_name if person_name else ""
        else:
            # User is helping someone else
            default_relation = relationship_type if relationship_type and relationship_type != "Myself" else "Daughter/Son"
            default_attendee = ""  # We don't know attendee name yet
            default_care_recipient = person_name if person_name else ""
        
        st.session_state["pfma_v3_form"] = {
            "attendee_name": default_attendee,
            "relation": default_relation,
            "care_recipient_name": default_care_recipient,
            "email": "",
            "phone": "",
            "timezone": "America/New_York",
            "type": "video",
            "preferred_time": "Morning (8am-12pm)",
            "notes": "",
        }
        log_event("pfma.booking.started", {"is_self": is_self, "prefilled": bool(person_name)})

    form_data = st.session_state["pfma_v3_form"]

    # Form fields
    st.markdown("### Your Information")
    
    st.caption("💡 *Pre-filled from earlier answers — you can edit if this isn't right.*")
    
    # Debug: Show current form data and option to clear
    if st.checkbox("🔧 Debug: Show form data", help="Developer option to inspect form state"):
        st.json(form_data)
        if st.button("Clear Form Data", help="Clear cached form data for testing"):
            st.session_state["pfma_v3_form"] = {}
            st.rerun()

    # Who will attend the appointment?
    st.markdown("**Who will we be talking to during this appointment?** *")
    col1, col2 = st.columns(2)
    
    with col1:
        attendee_first = st.text_input(
            "First Name",
            value=form_data.get("attendee_first", ""),
            placeholder="First name",
            help="Attendee's first name",
            key="attendee_first"
        )
        if name != form_data.get("name"):
            form_data["name"] = name
            # Generate lead_id on first meaningful form interaction
            lead_id = create_lead(name=name, source="pfma")
            log_event("pfma.booking.field_edited", {"field": "name", "lead_id": lead_id})

    with col2:
        attendee_last = st.text_input(
            "Last Name",
            value=form_data.get("attendee_last", ""),
            placeholder="Last name",
            help="Attendee's last name",
            key="attendee_last"
        )
        if attendee_last != form_data.get("attendee_last"):
            form_data["attendee_last"] = attendee_last
            log_event("pfma.booking.field_edited", {"field": "attendee_last"})
    
    # Combine for display
    attendee_name = f"{attendee_first} {attendee_last}".strip()
    form_data["attendee_name"] = attendee_name
    
    relation = st.selectbox(
        "Relation to the person needing care *",
        options=["Self", "Spouse/Partner", "Daughter/Son", "Other Family", "Friend/Advocate", "Professional"],
        index=["Self", "Spouse/Partner", "Daughter/Son", "Other Family", "Friend/Advocate", "Professional"].index(
            form_data.get("relation", "Self")
        ) if form_data.get("relation") in ["Self", "Spouse/Partner", "Daughter/Son", "Other Family", "Friend/Advocate", "Professional"] else 0,
        help="Your relationship to the care recipient",
    )
    if relation != form_data.get("relation"):
        form_data["relation"] = relation
        log_event("pfma.booking.field_edited", {"field": "relation"})
    
    # Conditional: Show care recipient name if relation != Self
    if relation != "Self":
        st.markdown("**Name of the person needing care** *")
        st.caption("🔒 *We'll never contact this person without your consent.*")
        
        col1a, col2a = st.columns(2)
        with col1a:
            care_recipient_first = st.text_input(
                "First Name",
                value=form_data.get("care_recipient_first", ""),
                placeholder="First name",
                help="Care recipient's first name",
                key="care_recipient_first"
            )
            if care_recipient_first != form_data.get("care_recipient_first"):
                form_data["care_recipient_first"] = care_recipient_first
                log_event("pfma.booking.field_edited", {"field": "care_recipient_first"})
        
        with col2a:
            care_recipient_last = st.text_input(
                "Last Name",
                value=form_data.get("care_recipient_last", ""),
                placeholder="Last name",
                help="Care recipient's last name",
                key="care_recipient_last"
            )
            if care_recipient_last != form_data.get("care_recipient_last"):
                form_data["care_recipient_last"] = care_recipient_last
                log_event("pfma.booking.field_edited", {"field": "care_recipient_last"})
        
        # Combine for display
        care_recipient_name = f"{care_recipient_first} {care_recipient_last}".strip()
        form_data["care_recipient_name"] = care_recipient_name
    else:
        # If Self, attendee and care recipient are the same
        form_data["care_recipient_first"] = attendee_first
        form_data["care_recipient_last"] = attendee_last
        form_data["care_recipient_name"] = attendee_name

    st.markdown("---")

    # Contact Information
    col3, col4 = st.columns(2)

    with col3:
        email = st.text_input(
            "Email Address",
            value=form_data.get("email", ""),
            placeholder="sarah@example.com",
            help="We'll send your confirmation here (email OR phone required)",
        )
        if email != form_data.get("email"):
            form_data["email"] = email
            # Generate lead_id on first meaningful form interaction
            lead_id = get_or_create_lead_id()
            log_event("pfma.booking.field_edited", {"field": "email", "lead_id": lead_id})

    with col4:
        phone = st.text_input(
            "Phone Number",
            value=form_data.get("phone", ""),
            placeholder="555-123-4567",
            help="For appointment reminders (email OR phone required)",
        )
        if phone != form_data.get("phone"):
            form_data["phone"] = phone
            # Generate lead_id on first meaningful form interaction
            lead_id = create_lead(phone=phone, source="pfma")
            log_event("pfma.booking.field_edited", {"field": "phone", "lead_id": lead_id})

    # Timezone
    timezone = st.selectbox(
        "Timezone *",
        options=[
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Phoenix",
            "America/Anchorage",
            "Pacific/Honolulu",
        ],
        index=0,
        format_func=_format_timezone,
        help="Your local timezone for scheduling",
    )
    if timezone != form_data.get("timezone"):
        form_data["timezone"] = timezone
        log_event("pfma.booking.field_edited", {"field": "timezone"})

    st.markdown("### Appointment Preferences")

    col5, col6 = st.columns(2)

    with col5:
        appointment_type = st.selectbox(
            "Appointment Type *",
            options=["video", "phone"],
            format_func=lambda x: {
                "video": "📹 Video Call",
                "phone": "📞 Phone Call",
            }.get(x, x),
            help="How would you like to meet with your advisor?",
        )
        if appointment_type != form_data.get("type"):
            form_data["type"] = appointment_type
            log_event("pfma.booking.field_edited", {"field": "type"})

    with col6:
        preferred_time = st.selectbox(
            "Preferred Time",
            options=["Morning (8am-12pm)", "Afternoon (12pm-5pm)", "Evening (5pm-8pm)", "Flexible"],
            help="We'll do our best to match your preference",
        )
        if preferred_time != form_data.get("preferred_time"):
            form_data["preferred_time"] = preferred_time
            log_event("pfma.booking.field_edited", {"field": "preferred_time"})

    # Notes field
    notes = st.text_area(
        "Additional Notes (Optional)",
        value=form_data.get("notes", ""),
        placeholder="Any specific topics you'd like to discuss or scheduling constraints...",
        help="Share anything that will help us prepare for your consultation",
        max_chars=500,
    )
    if notes != form_data.get("notes"):
        form_data["notes"] = notes
        log_event("pfma.booking.field_edited", {"field": "notes"})

    # Validation and submit
    st.markdown("---")

    col_submit1, col_submit2 = st.columns([3, 1])

    with col_submit1:
        st.caption("*Required fields. Email OR phone required for confirmation.")

    with col_submit2:
        if st.button("📅 Book Appointment", type="primary", use_container_width=True):
            _handle_booking_submit(form_data)


def _format_timezone(tz: str) -> str:
    """Format timezone for display."""
    tz_map = {
        "America/New_York": "Eastern (ET)",
        "America/Chicago": "Central (CT)",
        "America/Denver": "Mountain (MT)",
        "America/Los_Angeles": "Pacific (PT)",
        "America/Phoenix": "Arizona (MST)",
        "America/Anchorage": "Alaska (AKT)",
        "Pacific/Honolulu": "Hawaii (HST)",
    }
    return tz_map.get(tz, tz)


def _handle_booking_submit(form_data: dict):
    """Validate and process booking submission."""

    # Validate
    is_valid, errors = _validate_booking(form_data)

    if not is_valid:
        # Log validation errors
        log_event("pfma.booking.validation_error", {"errors": errors})

        # Show errors
        for error in errors:
            st.error(f"❌ {error}")
        return

    # Create appointment
    confirmation_id = str(uuid.uuid4())[:8].upper()

    appointment = AdvisorAppointment(
        scheduled=True,
        date=datetime.now().isoformat(),  # Will be updated by scheduling team
        time=form_data.get("preferred_time", "TBD"),
        type=form_data.get("type", "video"),
        confirmation_id=confirmation_id,
        contact_email=form_data.get("email", ""),
        contact_phone=form_data.get("phone", ""),
        timezone=form_data.get("timezone", "America/New_York"),
        notes=form_data.get("notes", ""),
        generated_at=datetime.now().isoformat(),
        status="scheduled",
        prep_sections_complete=[],
        prep_progress=0,
    )

    # Convert lead to customer (generates customer_id, preserves lead_id)
    customer_id = convert_to_customer(
        name=form_data.get("name"),
        email=form_data.get("email"), 
        phone=form_data.get("phone"),
        source="appointment_booking"
    )
    crm_status = get_crm_status()
    
    print(f"[PFMA] Appointment booked - CRM Status: {crm_status}")

    # Save to MCIP
    MCIP.set_advisor_appointment(appointment)

    # Log events
    log_event(
        "pfma.booking.submitted",
        {
            "appointment_type": appointment.type,
            "timezone": appointment.timezone,
            "has_email": bool(appointment.contact_email),
            "has_phone": bool(appointment.contact_phone),
            "lead_id": crm_status["lead_id"],
            "customer_id": crm_status["customer_id"],
            "crm_status": crm_status["user_type"],
        },
    )

    log_event(
        "pfma.appointment.requested", {
            "confirmation_id": confirmation_id, 
            "type": appointment.type,
            "lead_id": crm_status["lead_id"],
            "customer_id": crm_status["customer_id"],
        }
    )

    # Clear form
    st.session_state["pfma_v3_form"] = {}

    # Force rerun to show preferences collection (not confirmation yet)
    st.rerun()


def _validate_booking(form_data: dict) -> tuple[bool, list[str]]:
    """Validate booking form data.

    Returns:
        (is_valid, errors) tuple
    """
    errors = []

    # Attendee first name required
    if not form_data.get("attendee_first", "").strip():
        errors.append("Attendee first name is required")
    
    # Attendee last name required
    if not form_data.get("attendee_last", "").strip():
        errors.append("Attendee last name is required")

    # Relation required
    if not form_data.get("relation"):
        errors.append("Relationship to care recipient is required")

    # Care recipient name required if relation != Self
    relation = form_data.get("relation", "Self")
    if relation != "Self":
        if not form_data.get("care_recipient_first", "").strip():
            errors.append("Care recipient's first name is required")
        if not form_data.get("care_recipient_last", "").strip():
            errors.append("Care recipient's last name is required")

    # Email OR phone required (not both mandatory)
    email = form_data.get("email", "").strip()
    phone = form_data.get("phone", "").strip()

    if not email and not phone:
        errors.append("Please provide either Email or Phone for confirmation")

    # Email format validation (if provided)
    if email and "@" not in email:
        errors.append("Please provide a valid email address")

    # Timezone required
    if not form_data.get("timezone"):
        errors.append("Timezone is required")

    # Appointment type required
    if not form_data.get("type"):
        errors.append("Appointment type is required")

    return (len(errors) == 0, errors)


# =============================================================================
# PREFERENCES COLLECTION SCREEN  
# =============================================================================


def _render_preferences_collection(appt: AdvisorAppointment):
    """Render preferences collection using the exact same structure as booking form."""
    
    # Get customer name from profile or appointment
    profile = st.session_state.get("profile", {})
    customer_name = profile.get("name", "you")
    
    # Apply clean CSS with proper width constraint (EXACT SAME AS BOOKING)
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"## More About {customer_name}")
    st.markdown(
        f"**Great! Your appointment is confirmed.** To help your advisor find the best community matches, "
        f"please answer these 4 quick questions (takes about 1 minute)."
    )
    
    # Show appointment confirmation briefly
    with st.expander("📅 Your Appointment Details", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Confirmation:** {appt.confirmation_id}")
            st.markdown(f"**Type:** {appt.type.title()}")
        with col2:
            st.markdown(f"**Preferred Time:** {appt.time}")
            if appt.contact_email:
                st.markdown(f"**Email:** {appt.contact_email}")

    st.markdown("---")

    # Get or create preferences and check recommendation type
    preferences = PreferencesManager.get_preferences()
    care_rec = MCIP.get_care_recommendation()
    care_tier = care_rec.tier if care_rec else "assisted_living"
    
    # Determine if this is community-based care or in-home care
    is_community_care = care_tier in ["assisted_living", "memory_care", "memory_care_high_acuity", "independent"]
    is_in_home_care = care_tier == "in_home"
    
    if not preferences:
        preferences = PreferencesManager.create_default_preferences(care_tier)

    # Streamlined form for essential preferences only
    if is_community_care:
        st.markdown("### Essential Information for Community Matching")
        st.markdown("*These questions help your advisor find communities with availability that match your needs.*")
        form_title = "community matching"
    else:  # in_home_care
        st.markdown("### Essential Information for In-Home Care Planning")
        st.markdown("*These questions help your advisor plan the best in-home care approach for your situation.*")
        form_title = "in-home care planning"
    
    # Initialize form state (EXACT SAME PATTERN AS BOOKING)
    if "preferences_form" not in st.session_state:
        if is_community_care:
            # Extract first/last name if care_recipient_name exists
            existing_name = preferences.care_recipient_name
            name_parts = existing_name.split() if existing_name else []
            first_name = name_parts[0] if len(name_parts) > 0 else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Get ZIP code from cost planner for pre-population
            cost_data = st.session_state.get("cost", {})
            cost_inputs = cost_data.get("inputs", {})
            cost_zip = cost_inputs.get("zip") or st.session_state.get("cost.inputs", {}).get("zip")
            
            st.session_state["preferences_form"] = {
                "care_recipient_name": preferences.care_recipient_name,
                "first_name": first_name,
                "last_name": last_name,
                "zip_code": getattr(preferences, 'zip_code', '') or cost_zip or "",
                "search_radius": getattr(preferences, 'search_radius', '25'),
                "move_timeline": preferences.move_timeline,
                "care_environment": preferences.care_environment_preference,
                "medical_features": getattr(preferences, 'medical_features', []),
                "accommodation_features": getattr(preferences, 'accommodation_features', []),
                "amenity_features": getattr(preferences, 'amenity_features', []),
                "lifestyle_features": getattr(preferences, 'lifestyle_features', []),
            }
        else:  # in_home_care
            # Extract first/last name if care_recipient_name exists
            existing_name = preferences.care_recipient_name
            name_parts = existing_name.split() if existing_name else []
            first_name = name_parts[0] if len(name_parts) > 0 else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            st.session_state["preferences_form"] = {
                "care_recipient_name": preferences.care_recipient_name,
                "first_name": first_name,
                "last_name": last_name,
                "current_living_situation": "own_home",
                "care_start_timeline": "exploring",
                "primary_care_needs": [],
            }

    form_data = st.session_state["preferences_form"]

    # Care recipient name (split into first/last for CRM)
    col_name1, col_name2 = st.columns(2)
    
    with col_name1:
        first_name = st.text_input(
            "First Name *",
            value=form_data.get("first_name", ""),
            placeholder="e.g., Mary",
            help="First name of person receiving care",
        )
        if first_name != form_data.get("first_name"):
            form_data["first_name"] = first_name
    
    with col_name2:
        last_name = st.text_input(
            "Last Name *",
            value=form_data.get("last_name", ""),
            placeholder="e.g., Johnson",
            help="Last name of person receiving care",
        )
        if last_name != form_data.get("last_name"):
            form_data["last_name"] = last_name
    
    # Combine for legacy compatibility and display
    care_recipient_name = f"{first_name.strip()} {last_name.strip()}".strip()
    if care_recipient_name != form_data.get("care_recipient_name"):
        form_data["care_recipient_name"] = care_recipient_name
    
    if is_community_care:
        # Community Care Questions (AL/MC/Independent)
        
        # ZIP code and search radius in columns
        col1, col2 = st.columns(2)
        
        with col1:
            # Get ZIP code from cost planner
            cost_data = st.session_state.get("cost", {})
            cost_inputs = cost_data.get("inputs", {})
            cost_zip = cost_inputs.get("zip") or st.session_state.get("cost.inputs", {}).get("zip")
            
            zip_code = st.text_input(
                "ZIP Code",
                value=form_data.get("zip_code", cost_zip or ""),
                placeholder="12345",
                max_chars=5,
                help="Pre-populated from your cost estimate",
                key="preferences_zip_code"
            )
            if zip_code != form_data.get("zip_code"):
                form_data["zip_code"] = zip_code
        
        with col2:
            search_radius = st.selectbox(
                "Search Radius",
                options=["10", "25", "50", "75", "100", "no_limit"],
                index=["10", "25", "50", "75", "100", "no_limit"].index(
                    form_data.get("search_radius", "25")
                ),
                format_func=lambda x: {
                    "10": "10 miles",
                    "25": "25 miles",
                    "50": "50 miles", 
                    "75": "75 miles",
                    "100": "100 miles",
                    "no_limit": "No distance limit"
                }.get(x, f"{x} miles"),
                help="How far from your ZIP code to search for communities",
                key="preferences_search_radius"
            )
            if search_radius != form_data.get("search_radius"):
                form_data["search_radius"] = search_radius

        # Timeline for moving
        timeline = st.selectbox(
            "What's your timeline for moving?",
            options=["immediate", "2_4_weeks", "2_3_months", "exploring", "future_planning"],
            index=["immediate", "2_4_weeks", "2_3_months", "exploring", "future_planning"].index(
                form_data.get("move_timeline", "exploring")
            ),
            format_func=lambda x: {
                "immediate": "Immediate (within 2 weeks)",
                "2_4_weeks": "2-4 weeks",
                "2_3_months": "2-3 months", 
                "exploring": "Exploring options",
                "future_planning": "Future planning"
            }.get(x, x.replace("_", " ").title()),
            help="This helps find communities with matching availability",
            key="preferences_timeline_select"
        )
        if timeline != form_data.get("move_timeline"):
            form_data["move_timeline"] = timeline

        # Care environment (auto-populated from GCP, read-only)
        st.markdown(f"**Care Level Recommendation:** {care_tier.replace('_', ' ').title()}")
        st.caption("Based on your assessment results - this helps match the right level of care")        # Store the care tier (not user-selectable)
        if form_data.get("care_environment") != care_tier:
            form_data["care_environment"] = care_tier

        # Community Features & Amenities (Community Care Only)
        st.markdown("### Community Features & Amenities")
        st.caption("Select features that are important to you (optional)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Medical & Care Features:**")
            medical_features = st.multiselect(
                "Medical & Care Features",
                options=["hoyer_lift", "house_doctor", "awake_night_staff", "insulin_management", "medicaid_accepted"],
                default=form_data.get("medical_features", []),
                format_func=lambda x: {
                    "hoyer_lift": "Hoyer Lift Available",
                    "house_doctor": "House Doctor on Site",
                    "awake_night_staff": "Awake Night Staff",
                    "insulin_management": "Insulin Management",
                    "medicaid_accepted": "Medicaid Accepted"
                }.get(x, x.replace("_", " ").title()),
                help="Medical services and specialized care equipment",
                label_visibility="collapsed",
                key="medical_features_select"
            )
            if medical_features != form_data.get("medical_features"):
                form_data["medical_features"] = medical_features
                
            st.markdown("**Accommodation Features:**")
            accommodation_features = st.multiselect(
                "Accommodation Features",
                options=["full_kitchen", "air_conditioning", "two_bedroom", "covered_parking", "extra_storage"],
                default=form_data.get("accommodation_features", []),
                format_func=lambda x: {
                    "full_kitchen": "Full Kitchen in Unit",
                    "air_conditioning": "Air Conditioning",
                    "two_bedroom": "Two Bedroom Options",
                    "covered_parking": "Covered Parking",
                    "extra_storage": "Extra Storage Space"
                }.get(x, x.replace("_", " ").title()),
                help="Living space features and accommodations",
                label_visibility="collapsed",
                key="accommodation_features_select"
            )
            if accommodation_features != form_data.get("accommodation_features"):
                form_data["accommodation_features"] = accommodation_features
        
        with col2:
            st.markdown("**Amenities & Activities:**")
            amenity_features = st.multiselect(
                "Amenities & Activities",
                options=["pool", "water_view", "patio", "generator", "cottages"],
                default=form_data.get("amenity_features", []),
                format_func=lambda x: {
                    "pool": "Swimming Pool",
                    "water_view": "Water View",
                    "patio": "Private Patio/Balcony",
                    "generator": "Backup Generator",
                    "cottages": "Cottage-Style Living"
                }.get(x, x.replace("_", " ").title()),
                help="Recreation and lifestyle amenities",
                label_visibility="collapsed",
                key="amenity_features_select"
            )
            if amenity_features != form_data.get("amenity_features"):
                form_data["amenity_features"] = amenity_features
                
            st.markdown("**Lifestyle Policies:**")
            lifestyle_features = st.multiselect(
                "Lifestyle Policies",
                options=["allows_pets", "accepts_smokers", "has_pets_in_home"],
                default=form_data.get("lifestyle_features", []),
                format_func=lambda x: {
                    "allows_pets": "Allows Pets with Placement",
                    "accepts_smokers": "Accepts Smokers",
                    "has_pets_in_home": "Community Has Therapy Pets"
                }.get(x, x.replace("_", " ").title()),
                help="Pet policies and lifestyle accommodations",
                label_visibility="collapsed",
                key="lifestyle_features_select"
            )
            if lifestyle_features != form_data.get("lifestyle_features"):
                form_data["lifestyle_features"] = lifestyle_features
        
    else:  # in_home_care
        # In-Home Care Questions in columns (SAME PATTERN AS BOOKING)
        
        col1, col2 = st.columns(2)
        
        with col1:
            living_situation = st.selectbox(
                "What's the current living situation?",
                options=["own_home", "family_home", "apartment", "senior_housing", "other"],
                index=["own_home", "family_home", "apartment", "senior_housing", "other"].index(
                    form_data.get("current_living_situation", "own_home")
                ),
                format_func=lambda x: {
                    "own_home": "Living in own home",
                    "family_home": "Living with family",
                    "apartment": "Living in apartment/condo",
                    "senior_housing": "Already in senior housing",
                    "other": "Other living arrangement"
                }.get(x, x.replace("_", " ").title()),
                help="This helps determine the best in-home care approach",
            )
            if living_situation != form_data.get("current_living_situation"):
                form_data["current_living_situation"] = living_situation
        
        with col2:
            care_timeline = st.selectbox(
                "When would in-home care ideally start?",
                options=["immediate", "2_4_weeks", "2_3_months", "exploring", "emergency_backup"],
                index=["immediate", "2_4_weeks", "2_3_months", "exploring", "emergency_backup"].index(
                    form_data.get("care_start_timeline", "exploring")
                ),
                format_func=lambda x: {
                    "immediate": "Immediate (within 2 weeks)",
                    "2_4_weeks": "2-4 weeks",
                    "2_3_months": "2-3 months", 
                    "exploring": "Exploring options",
                    "emergency_backup": "Emergency backup plan"
                }.get(x, x.replace("_", " ").title()),
                help="This helps prioritize caregiver availability and planning",
            )
            if care_timeline != form_data.get("care_start_timeline"):
                form_data["care_start_timeline"] = care_timeline

        # Primary care needs
        care_needs = st.multiselect(
            "What are the primary care needs?",
            options=["personal_care", "medication_management", "mobility_assistance", "meal_preparation", "companionship", "safety_supervision", "medical_coordination"],
            default=form_data.get("primary_care_needs", []),
            format_func=lambda x: {
                "personal_care": "Personal care (bathing, dressing)",
                "medication_management": "Medication management",
                "mobility_assistance": "Mobility assistance",
                "meal_preparation": "Meal preparation",
                "companionship": "Companionship & social interaction",
                "safety_supervision": "Safety supervision",
                "medical_coordination": "Medical appointment coordination"
            }.get(x, x.replace("_", " ").title()),
            help="Select the main types of care assistance needed",
            key="primary_care_needs_select"
        )
        if care_needs != form_data.get("primary_care_needs"):
            form_data["primary_care_needs"] = care_needs
    
    # Validation and submit (EXACT SAME PATTERN AS BOOKING)
    st.markdown("---")

    col_submit1, col_submit2, col_submit3 = st.columns([2, 1, 1])

    with col_submit1:
        if is_community_care:
            st.caption("*Takes 1 minute • These questions match you with communities that have availability in your preferred areas and care level.")
        else:
            st.caption("*Takes 1 minute • These questions help plan the best in-home care approach for your specific situation.")

    with col_submit2:
        if st.button("Skip for Now", use_container_width=True):
            st.session_state["pfma_skip_preferences"] = True
            _complete_pfma_process()
            st.rerun()

    with col_submit3:
        if st.button("Save & Continue", type="primary", use_container_width=True):
            _save_preferences_and_complete(form_data, is_community_care)
            st.rerun()


def _save_preferences_and_complete(form_data: dict, is_community_care: bool):
    """Save conditional preferences and complete PFMA process."""
    
    # Create conditional preferences object based on care type
    if is_community_care:
        # Community care preferences (AL/MC/Independent)
        preferences = CustomerPreferences(
            care_recipient_name=form_data.get("care_recipient_name", ""),
            first_name=form_data.get("first_name", ""),
            last_name=form_data.get("last_name", ""),
            zip_code=form_data.get("zip_code", ""),
            search_radius=form_data.get("search_radius", "25"),
            move_timeline=form_data.get("move_timeline", "exploring"),
            care_environment_preference=form_data.get("care_environment", "assisted_living"),
            medical_features=form_data.get("medical_features", []),
            accommodation_features=form_data.get("accommodation_features", []),
            amenity_features=form_data.get("amenity_features", []),
            lifestyle_features=form_data.get("lifestyle_features", []),
            completion_status="complete",
        )
        
        # Log community care preferences completion
        crm_status = get_crm_status()
        log_event(
            "pfma.preferences.completed.community_care",
            {
                "has_care_recipient_name": bool(preferences.care_recipient_name.strip()),
                "has_zip_code": bool(preferences.zip_code.strip()),
                "search_radius": preferences.search_radius,
                "timeline": preferences.move_timeline,
                "care_environment": preferences.care_environment_preference,
                "medical_features_count": len(preferences.medical_features),
                "accommodation_features_count": len(preferences.accommodation_features),
                "amenity_features_count": len(preferences.amenity_features),
                "lifestyle_features_count": len(preferences.lifestyle_features),
                "version": "zip_radius_v3.2_community",
                "lead_id": crm_status["lead_id"],
                "customer_id": crm_status["customer_id"],
                "crm_status": crm_status["user_type"],
            }
        )
    else:
        # In-home care preferences (different structure)
        # For now, store in the same structure but with in-home specific fields
        preferences = CustomerPreferences(
            care_recipient_name=form_data.get("care_recipient_name", ""),
            first_name=form_data.get("first_name", ""),
            last_name=form_data.get("last_name", ""),
            preferred_regions=[],  # Not applicable for in-home
            move_timeline=form_data.get("care_start_timeline", "exploring"),  # Re-purpose as care start timeline
            care_environment_preference="in_home",
            completion_status="complete",
            # Note: In future, we might want a separate InHomeCarePreferences dataclass
            # For now, we'll store in-home specific data in session state
        )
        
        # Store in-home specific data in session state for advisor reference
        st.session_state["in_home_care_details"] = {
            "current_living_situation": form_data.get("current_living_situation", "own_home"),
            "care_start_timeline": form_data.get("care_start_timeline", "exploring"), 
            "primary_care_needs": form_data.get("primary_care_needs", []),
        }
        
        # Log in-home care preferences completion
        crm_status = get_crm_status()
        log_event(
            "pfma.preferences.completed.in_home_care",
            {
                "has_care_recipient_name": bool(preferences.care_recipient_name.strip()),
                "living_situation": form_data.get("current_living_situation", "own_home"),
                "care_timeline": form_data.get("care_start_timeline", "exploring"),
                "care_needs_count": len(form_data.get("primary_care_needs", [])),
                "version": "streamlined_v2_in_home",
                "lead_id": crm_status["lead_id"],
                "customer_id": crm_status["customer_id"],
                "crm_status": crm_status["user_type"],
            }
        )
    
    # Save preferences
    PreferencesManager.save_preferences(preferences)
    
    # Mark preferences as complete
    st.session_state["pfma_preferences_complete"] = True
    
    # Complete PFMA process
    _complete_pfma_process()


def _complete_pfma_process():
    """Complete the PFMA process and mark as done."""
    # Mark PFMA complete (using canonical key)
    MCIP.mark_product_complete("pfma")
    print("[PFMA] Marked PFMA/My Advisor complete")
    
    # Clear form data
    if "preferences_form" in st.session_state:
        del st.session_state["preferences_form"]


# =============================================================================
# CONFIRMATION SCREEN
# =============================================================================


def _render_confirmation(appt: AdvisorAppointment):
    """Render confirmation screen for already-booked appointment."""

    # Apply clean CSS with width constraint
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Appointment Confirmed")

    st.markdown(f"**Your consultation is scheduled!**\n\nConfirmation ID: **{appt.confirmation_id}**")

    # Appointment details in container
    with st.container():
        st.markdown("### Appointment Details")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Type:** {appt.type.title()}")
            st.markdown(f"**Timezone:** {_format_timezone(appt.timezone)}")
            if appt.contact_email:
                st.markdown(f"**Email:** {appt.contact_email}")

        with col2:
            st.markdown(f"**Status:** {appt.status.title()}")
            st.markdown(f"**Preferred Time:** {appt.time}")
            if appt.contact_phone:
                st.markdown(f"**Phone:** {appt.contact_phone}")

        if appt.notes:
            st.markdown("**Notes:**")
            st.info(appt.notes)

    # Show preferences status
    preferences = PreferencesManager.get_preferences()
    if preferences and preferences.completion_status == "complete":
        st.success("✅ **Preferences collected** - Your advisor will have detailed information about your needs and preferences.")
    elif st.session_state.get("pfma_skip_preferences", False):
        st.info("ℹ️ **Preferences skipped** - You can always share more details during your appointment.")

    # Next steps
    st.markdown("### Next Steps")

    # Check if care_prep is appropriate
    if tier in ("assisted_living", "memory_care", "memory_care_high_acuity", "in_home", "in_home_care"):
        st.markdown(
            "**Let's gather a few preferences** to make your consultation more productive. "
            "This will only take a few minutes and will help your advisor prepare personalized recommendations."
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Continue to Preferences →", type="primary", use_container_width=True):
                log_event("pfma.route_to_care_prep", {"tier": tier})
                route_to("care_prep")
        
        st.markdown("")
        st.caption("Or skip this step and return to the Lobby – your advisor will still contact you within 24 hours.")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Skip & Return to Lobby", use_container_width=True):
                log_event("lobby.return", {"from_product": "pfma_v3", "skipped_care_prep": True})
                # Mark Planning journey complete
                from core.journeys import mark_journey_complete
                mark_journey_complete("planning")
                route_to("hub_lobby")
    else:
        # No care prep needed for general/unknown tier
        st.markdown(
            "**One of our advisors will contact you within the next 24 hours** to confirm your consultation time. "
            "In the meantime, feel free to explore additional resources in the Lobby."
        )

        # Action button - End of planning journey
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Return to Lobby", type="primary", use_container_width=True):
                log_event("lobby.return", {"from_product": "pfma_v3"})
                # Mark Planning journey complete
                from core.journeys import mark_journey_complete
                mark_journey_complete("planning")
                route_to("hub_lobby")

