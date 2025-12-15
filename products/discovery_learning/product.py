"""Discovery Learning Product - Human-Centered Welcome Screen

Phase Post-CSS: Beautiful, emotionally intelligent onboarding page.

This is the first page many users see — it must feel like home:
warm, intelligent, effortless. Modern SaaS-quality onboarding with Navi guidance.

Visual Direction:
- Clean white space, soft navy text, subtle accents
- Rounded corners, gentle shadows, no unnecessary borders
- Balanced typography with generous spacing
- Fully responsive (mobile-friendly)

Structure:
1. Hero with Navi introduction
2. Three horizontal info tiles
3. Inline Navi search (conversational, no expanders)
4. Centered CTA section
"""

import streamlit as st

from core.journeys import advance_to
from core.mcip import MCIP
from ui.footer_simple import render_footer_simple


def render():
    """Render Discovery Learning - clean, card-based layout matching app aesthetic."""
    
    # Initialize MCIP
    MCIP.initialize()
    
    # Inject custom CSS for this page
    _inject_discovery_styles()
    
    # Mark as viewed
    if "discovery_learning_viewed" not in st.session_state:
        st.session_state["discovery_learning_viewed"] = True
    
    # Force narrow layout using columns (like product tile width)
    # Left spacer | Content (60%) | Right spacer
    _, col_center, _ = st.columns([1, 3, 1])
    
    with col_center:
        # ========================================
        # HERO SECTION - Clean title with subtitle
        # ========================================
        st.markdown('<h1 class="page-title">Welcome to Your Discovery Journey</h1>', unsafe_allow_html=True)
        
        # ========================================
        # NAVI PANEL - At the top for guidance
        # ========================================
        st.markdown("""
        <div class="navi-card">
            <div class="navi-header">
                <span class="navi-icon">✨</span>
                <span class="navi-greeting">Here's What You'll Discover</span>
            </div>
            <p class="navi-intro">This page introduces you to Senior Navigator's three key tools: the <strong>Guided Care Plan</strong> (assess needs in 5-10 minutes), the <strong>Cost Planner</strong> (estimate expenses and find funding), and <strong>Concierge Services</strong> (connect with verified advisors). Watch the video below, then ask me any questions about getting started.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # ========================================
        # VIDEO CARD - Embedded with description
        # ========================================
        st.markdown("""
        <div class="content-card">
            <div class="card-header">
                <span class="card-icon">🎥</span>
                <h3 class="card-title">How Senior Navigator Works</h3>
            </div>
            <div class="card-body">
                <div class="video-wrapper">
                    <iframe class="video-iframe"
                        src="https://www.youtube.com/embed/c_nbkkHKqac"
                        title="Learn About Senior Navigator"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen>
                    </iframe>
                </div>
                <p class="video-caption">See how the Guided Care Plan and Cost Planner work together to help families make informed decisions.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        
        # ========================================
        # ASK NAVI - FAQ Style (Compact)
        # ========================================
        st.markdown('<h3 class="section-header">Ask Navi a Question</h3>', unsafe_allow_html=True)
        
        # Initialize session state for current answer
        if "discovery_current_answer" not in st.session_state:
            st.session_state.discovery_current_answer = None
        
        # Quick Questions FIRST - load into text box
        st.markdown('<p class="quick-label">Common Questions:</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("What is the Discovery Journey?", use_container_width=True, key="faq_discovery"):
                st.session_state.discovery_navi_input = "What is the Discovery Journey?"
                st.session_state.discovery_current_answer = None
                st.rerun()
        
        with col2:
            if st.button("How long does it take?", use_container_width=True, key="faq_duration"):
                st.session_state.discovery_navi_input = "How long does it take?"
                st.session_state.discovery_current_answer = None
                st.rerun()
        
        with col3:
            if st.button("What's the Cost Planner?", use_container_width=True, key="faq_cost"):
                st.session_state.discovery_navi_input = "What's the Cost Planner?"
                st.session_state.discovery_current_answer = None
                st.rerun()
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # Simple text input + Send button
        col1, col2 = st.columns([5, 1])
        
        with col1:
            navi_query = st.text_input(
                "Question",
                placeholder="Type your question here...",
                key="discovery_navi_input",
                label_visibility="collapsed"
            )
        
        with col2:
            send_clicked = st.button("Send", type="primary", use_container_width=True, key="discovery_send")
        
        # Process question
        if send_clicked and navi_query:
            # Simple contextual responses
            responses = {
                "discovery": "The Discovery Journey is your introduction to Senior Navigator. It takes about 10-15 minutes and helps you understand what we offer and how I can guide you through your care planning process.",
                "care plan": "The Guided Care Plan takes about 5-10 minutes. You'll answer questions about daily living, health needs, and safety concerns. I'll be with you every step, explaining what each question means.",
                "long": "Most families complete the Discovery Journey in 10-15 minutes. The full Guided Care Plan adds another 5-10 minutes. You can always save and come back later.",
                "cost": "After your care recommendation, you'll access the Cost Planner. It provides detailed estimates for different care types, including in-home care, assisted living, and memory care options.",
                "path": "The Discovery Journey is your introduction to Senior Navigator. It takes about 10-15 minutes and helps you understand what we offer.",
            }
            
            # Simple keyword matching
            response = None
            query_lower = navi_query.lower()
            for key, answer in responses.items():
                if key in query_lower:
                    response = answer
                    break
            
            if not response:
                response = "That's a great question! I'm here to help you understand your care planning journey. Try asking about the Discovery Journey, Care Plan, costs, or how long things take."
            
            # Store answer
            st.session_state.discovery_current_answer = response
        
        # Display answer if exists
        if st.session_state.discovery_current_answer:
            with st.container():
                st.markdown(f'<div class="navi-answer">{st.session_state.discovery_current_answer}</div>', unsafe_allow_html=True)
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # ========================================
        # COMPLETION CARD
        # ========================================
        st.markdown("""
        <div class="content-card completion-card">
            <div class="card-header">
                <span class="card-icon">🚀</span>
                <h3 class="card-title">Ready to Begin?</h3>
            </div>
            <div class="card-body">
                <p class="completion-text">Once you've watched the video and explored your questions, you're ready to start your personalized care planning journey.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action Buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("← Back to Lobby", use_container_width=True, key="return_lobby", type="secondary"):
                st.query_params.clear()
                st.query_params["page"] = "hub_lobby"
                st.rerun()
        
        with col2:
            if st.button("Complete Discovery Journey", type="primary", use_container_width=True, key="complete_discovery"):
                # Mark as complete
                _mark_complete()
                # Advance to planning phase
                advance_to("planning")
                # Navigate back to Lobby
                st.query_params.clear()
                st.query_params["page"] = "hub_lobby"
                st.rerun()
    
    # Render footer (outside column for full width)
    render_footer_simple()


def _inject_discovery_styles():
    """Inject clean card-based styling matching app aesthetic."""
    st.markdown("""
    <style>
    /* === Page Title === */
    .page-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #0E1E54;
        text-align: center;
        margin: 2rem 0 1rem;
        line-height: 1.2;
    }
    
    /* === Hero Subtitle === */
    .hero-subtitle {
        font-size: 1.1rem;
        color: #4b4f63;
        text-align: center;
        max-width: 700px;
        margin: 0 auto 2rem;
        line-height: 1.6;
    }

    /* === Navi Card at Top === */
    .navi-card {
        background: linear-gradient(135deg, #f0f4ff 0%, #f8f9fe 100%);
        border: 2px solid #e0e7ff;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0 0 2rem;
        box-shadow: 0 2px 8px rgba(124, 92, 255, 0.1);
    }
    .navi-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }
    .navi-icon {
        font-size: 1.5rem;
    }
    .navi-greeting {
        font-size: 1.25rem;
        font-weight: 600;
        color: #0E1E54;
    }
    .navi-intro {
        font-size: 1rem;
        color: #4b4f63;
        line-height: 1.6;
        margin: 0;
    }

    /* === Content Cards === */
    .content-card {
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        padding: 1.5rem;
        margin: 1.5rem 0;
        transition: box-shadow 0.2s ease;
    }
    .content-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    }
    
    .card-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
    }
    .card-icon {
        font-size: 1.75rem;
    }
    .card-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #0E1E54;
        margin: 0;
    }
    
    .card-body {
        color: #4b4f63;
        line-height: 1.6;
    }

    /* === Video Wrapper === */
    .video-wrapper {
        position: relative;
        width: 100%;
        padding-bottom: 56.25%; /* 16:9 aspect ratio */
        margin-bottom: 1rem;
        border-radius: 8px;
        overflow: hidden;
    }
    .video-iframe {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: 0;
    }
    .video-caption {
        font-size: 0.95rem;
        color: #6b7280;
        font-style: italic;
        margin: 0;
    }

    /* === FAQ Style Q&A === */
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #0E1E54;
        margin: 2rem 0 1rem;
        text-align: center;
    }
    
    .navi-answer {
        background: #f8f9fe;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.25rem;
        margin: 1rem 0;
        line-height: 1.6;
        color: #1e293b;
        font-size: 1rem;
    }
    
    .quick-label {
        text-align: center;
        font-weight: 600;
        font-size: 0.95rem;
        color: #6b7280;
        margin: 1.5rem 0 1rem;
    }

    /* === Completion Card === */
    .completion-card {
        background: linear-gradient(135deg, #f8f9fe 0%, #f0f4ff 100%);
        border: 1px solid #e0e7ff;
    }
    .completion-text {
        font-size: 1rem;
        color: #4b4f63;
        margin: 0;
        text-align: center;
    }

    /* === Button Enhancements === */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* === Mobile Responsive === */
    @media (max-width: 768px) {
        .hero-title {
            font-size: 2rem;
        }
        .hero-subtitle {
            font-size: 1rem;
        }
        .card-title {
            font-size: 1.25rem;
        }
        .content-card {
            padding: 1.25rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def _mark_complete():
    """Mark Discovery Learning as complete in MCIP."""
    st.session_state["discovery_learning_complete"] = True
    
    # Mark as complete in MCIP
    try:
        MCIP.mark_product_complete("discovery_learning")
        print("[DISCOVERY_LEARNING] Marked as complete in MCIP")
    except Exception as e:
        print(f"[DISCOVERY_LEARNING] Error marking complete: {e}")
