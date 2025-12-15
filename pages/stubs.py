
import streamlit as st

from core.ui import img_src, safe_img_src


@st.cache_resource
def preload_hero_image(image_path: str) -> str | None:
    """Pre-load and cache hero images to prevent flash during navigation."""
    return safe_img_src(image_path)


def _page(title: str, desc: str, ctas: list[tuple[str, str]] | None = None):
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      {title}
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      {desc}
    </p>
  </div>
        """,
        unsafe_allow_html=True,
    )

    if ctas:
        st.markdown(
            '<div class="card-actions" style="justify-content: center; margin-top: var(--space-6);">',
            unsafe_allow_html=True,
        )
        for label, target in ctas:
            st.markdown(
                f'<a class="btn btn--primary" href="?page={target}" style="margin: 0 var(--space-2);">{label}</a>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</section>", unsafe_allow_html=True)


def render_welcome():
    hero = safe_img_src("assets/images/hero.png")
    someone_img = safe_img_src("assets/images/welcome_someone_else.png")
    self_img = safe_img_src("assets/images/welcome_self.png")
    
    # Only render if all images are available
    if not (hero and someone_img and self_img):
        st.markdown("Loading welcome page...", unsafe_allow_html=True)
        return
        
    st.markdown(
        f"""<section class="container section-hero">
<div class="hero-grid">
  <div>
    <div class="hero-eyebrow">Concierge Care Advisors</div>
    <h1 class="hero-title">Senior Navigator</h1>
    <p class="hero-sub">Expert advisors - no cost. Helping families navigate the most important senior living decisions with clarity and compassion.</p>
    <div class="cta-row">
      <a class="btn btn--primary" href="?page=audience">Start Now</a>
      <a class="btn btn--secondary" href="?page=login" style="margin-left: var(--space-3);">Demo/Test Login 🧪</a>
    </div>
  </div>
  <div>
    <img class="card-photo" src="{hero}" alt="Senior and caregiver"/>
  </div>
</div>
</section>

<section class="container stack">
<h2>How We Can Help You</h2>
<div class="cards-2">
  <article class="card card--hover">
    <img class="card-photo" src="{someone_img}" alt="Supporting others"/>
    <div class="card-head">Supporting Others</div>
    <div class="card-meta">For a loved one</div>
    <p>Helping you make confident care decisions for someone you love.</p>
    <div class="card-actions">
      <a class="btn btn--primary" href="?page=audience&mode=someone">For someone</a>
    </div>
  </article>

  <article class="card card--hover">
    <img class="card-photo" src="{self_img}" alt="Getting ready for myself"/>
    <div class="card-head">Getting Ready for Myself</div>
    <div class="card-meta">For myself</div>
    <p>Plan for your own future care with trusted guidance and peace of mind.</p>
    <div class="card-actions">
      <a class="btn btn--primary" href="?page=audience&mode=self">For me</a>
    </div>
  </article>
</div>
</section>""",
        unsafe_allow_html=True,
    )


def render_pro_welcome():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Professional Welcome
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Entry for discharge planners and partners.
    </p>
  </div>
  <div class="card-actions" style="justify-content: center; margin-top: var(--space-6);">
    <a class="btn btn--primary" href="?page=pro_welcome_contextual" style="margin: 0 var(--space-2);">Pro Contextual</a>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_pro_welcome_contextual():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Pro Contextual Welcome
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Contextualized pro entry.
    </p>
  </div>
  <div class="card-actions" style="justify-content: center; margin-top: var(--space-6);">
    <a class="btn btn--primary" href="?page=professionals" style="margin: 0 var(--space-2);">Professionals</a>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_professionals():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container stack">
  <div class="card stack-sm">
    <div class="card-head">Professional Hub</div>
    <div class="card-meta">For discharge planners, social workers, and placement partners.</div>
    <div class="grid">
      <div class="card card--hover grid-span-6 stack-sm">
        <div class="card-head">Submit a referral</div>
        <p>Share essentials securely so our advisor can reach the family within one business day.</p>
        <div class="card-actions mt-space-4">
          <a class="btn btn--primary" href="?page=trusted_partners">Trusted Partners</a>
          <a class="btn btn--ghost" href="?page=about">About Us</a>
        </div>
      </div>
      <div class="card card--hover grid-span-6 stack-sm">
        <div class="card-head">Resources</div>
        <p>Downloadable checklists, eligibility overviews, and care setting definitions.</p>
        <div class="card-actions mt-space-4">
          <a class="btn btn--secondary" href="?page=privacy">Privacy Policy</a>
          <a class="btn btn--ghost" href="?page=terms">Terms</a>
        </div>
      </div>
    </div>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_ai_advisor():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      AI Advisor (Navi)
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Conversation surface placeholder.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_documents():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Documents
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Uploads and document listing. Auth required.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_exports():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Exports
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      PDF/CSV bundle generator. Auth required.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_waiting_room():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    status_img = img_src("assets/images/login.png")
    st.markdown(
        f"""
<section class="container stack">
  <div class="banner banner--success">You’re booked. An advisor will follow up within 24 hours.</div>
  <div class="grid">
    <div class="card grid-span-8 stack-sm">
      <div class="card-head">Ducks in a Row</div>
      <div class="card-meta">Complete these quick tasks to prep your call.</div>
      <ul class="list-unstyled stack-xs">
        <li><span class="chip status success"><span class="dot"></span> Contact details confirmed</span></li>
        <li><span class="chip status"><span class="dot"></span> Upload recent medication list</span></li>
        <li><span class="chip status"><span class="dot"></span> Confirm living situation</span></li>
      </ul>
      <div class="card-actions mt-space-4">
        <a class="btn btn--primary" href="?page=ai_advisor">Ask Navi</a>
        <a class="btn btn--ghost" href="?page=documents">Open Documents</a>
      </div>
    </div>
    <div class="card grid-span-4 text-center">
      <img class="img-responsive img-rounded" src="{status_img}" alt="Status" />
    </div>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_trusted_partners():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Trusted Partners
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Partner directory and disclosures.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_my_account():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      My Account
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Profile, preferences, and consent history.
    </p>
  </div>
  <div class="card-actions" style="justify-content: center; margin-top: var(--space-6);">
    <a class="btn btn--primary" href="?page=privacy" style="margin: 0 var(--space-2);">Privacy Policy</a>
    <a class="btn btn--primary" href="?page=terms" style="margin: 0 var(--space-2);">Terms of Use</a>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_terms():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Terms of Use
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Versioned legal surface.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_privacy():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      Privacy Policy
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Versioned privacy surface.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_about():
    # Apply consistent styling like other pages
    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="container section">
  <div class="text-center" style="margin-bottom: var(--space-8);">
    <h1 style="font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; line-height: 1.15; color: var(--ink); margin-bottom: var(--space-4);">
      About Us
    </h1>
    <p style="color: var(--ink-600); max-width: 48ch; margin: 0 auto; font-size: 1.1rem;">
      Company, mission, and contact.
    </p>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_faqs():
    """Delegate to the full FAQ/AI Advisor implementation."""
    from pages import ai_advisor

    ai_advisor.render()


# --- DEPRECATED: temporarily disabled during CSS/IA refactor ---
def render_legacy_fa_intro():
    """Legacy FA intro route - redirect to modern PFMA v3."""
    from core.nav import route_to
    route_to("pfma_v3")


def render_signup():
    # intentionally disabled (will be rebuilt as its own page)
    return


def render_logout():
    """Logout page - toggles auth off."""
    import streamlit as st

    from core.nav import route_to
    from core.state import logout_user

    # Toggle auth off
    logout_user()

    st.title("👋 Logged Out")
    st.success("You've been logged out successfully!")
    st.info("Your progress is saved. Log back in anytime to continue.")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Welcome", use_container_width=True):
            route_to("welcome")
            st.rerun()

    with col2:
        if st.button("🔐 Log Back In", use_container_width=True, type="primary"):
            route_to("login")
            st.rerun()


def render_export_results():
    """Export/share journey results - shows summary of all completed products.

    Powered by Navi, your AI guide through the senior care journey.
    """
    import json
    from datetime import datetime

    from core.mcip import MCIP
    from core.state import get_user_ctx

    st.markdown(
        """<style>
        .main .block-container {
            background: var(--bg);
            min-height: 80vh;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    # Get user context
    ctx = get_user_ctx()
    user_name = ctx.get("auth", {}).get("name", "Your")

    # Get data from Navi (MCIP)
    care_rec = MCIP.get_care_recommendation()
    financial = MCIP.get_financial_profile()
    appointment = MCIP.get_advisor_appointment()
    progress = MCIP.get_journey_progress()

    st.title("📤 Export Your Journey")
    st.markdown(f"### {user_name} Senior Care Journey Summary")
    st.markdown("*Powered by ✨ Navi - Your AI Care Navigator*")

    # Journey progress
    completed = progress["completed_count"]
    st.progress(completed / 3.0)
    st.markdown(f"**{completed}/3 Products Completed**")

    st.markdown("---")

    # Care Recommendation
    if care_rec:
        st.markdown("### 🧭 Guided Care Plan")
        tier_map = {
            "no_care": "No Care Needed",
            "in_home": "In-Home Care",
            "assisted_living": "Assisted Living",
            "memory_care": "Memory Care",
            "memory_care_high": "Memory Care — High Acuity",
        }
        tier_label = tier_map.get(care_rec.tier, care_rec.tier)
        st.markdown(f"**Navi's Recommendation:** {tier_label}")
        st.markdown(f"**Confidence:** {int(care_rec.tier_score)}%")
        if care_rec.rationale:
            st.markdown("**Key Factors:**")
            for reason in care_rec.rationale[:3]:
                st.markdown(f"- {reason}")

    # Financial Profile
    if financial:
        st.markdown("### 💰 Cost Planner")
        st.markdown(f"**Estimated Monthly Cost:** ${financial.estimated_monthly_cost:,.0f}")
        st.markdown(f"**Runway:** {financial.runway_months} months")
        if financial.gap_amount > 0:
            st.markdown(f"**Monthly Gap:** ${financial.gap_amount:,.0f}")

    # Appointment
    if appointment and appointment.scheduled:
        st.markdown("### 📅 Plan with My Advisor")
        st.markdown(f"**Type:** {appointment.type.title()}")
        st.markdown(f"**Date:** {appointment.date} at {appointment.time}")
        st.markdown(f"**Confirmation:** {appointment.confirmation_id}")

    st.markdown("---")

    # Export options
    st.markdown("### Export Options")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export as JSON
        export_data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "generated_by": "Navi - AI Care Navigator",
            "user_name": user_name,
            "progress": progress,
            "care_recommendation": care_rec.__dict__ if care_rec else None,
            "financial_profile": financial.__dict__ if financial else None,
            "advisor_appointment": appointment.__dict__ if appointment else None,
        }

        json_str = json.dumps(export_data, indent=2)
        st.download_button(
            label="📄 Download JSON",
            data=json_str,
            file_name=f"care_journey_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

    with col2:
        # Copy to clipboard (via text area)
        summary_text = f"""
SENIOR CARE JOURNEY SUMMARY
Powered by Navi - AI Care Navigator
Generated: {datetime.now().strftime("%B %d, %Y")}

Progress: {completed}/3 Products Completed
"""
        if care_rec:
            summary_text += f"\nNAVI'S CARE RECOMMENDATION:\n- {tier_label} ({int(care_rec.tier_score)}% confidence)\n"
        if financial:
            summary_text += f"\nFINANCIAL PROFILE:\n- Monthly Cost: ${financial.estimated_monthly_cost:,.0f}\n- Runway: {financial.runway_months} months\n"
        if appointment and appointment.scheduled:
            summary_text += f"\nADVISOR APPOINTMENT:\n- {appointment.type.title()} - {appointment.date} at {appointment.time}\n"

        if st.button("📋 Copy Summary", use_container_width=True):
            st.code(summary_text, language=None)
            st.success("Summary displayed above - copy from the text box!")

    with col3:
        # Email results (placeholder)
        if st.button("📧 Email Results", use_container_width=True):
            st.info("Email feature coming soon! Use the Copy or Download options for now.")

    st.markdown("---")

    # Footer message from Navi
    st.info(
        "🤖 **Navi here!** Your progress is always saved. Come back anytime to continue your journey or update your plan."
    )

    # Back to hub
    from core.nav import route_to

    if st.button("← Back to Lobby", use_container_width=True):
        route_to("hub_lobby")
