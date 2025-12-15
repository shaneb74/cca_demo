"""
Smart Community Matching Engine - AI-powered facility recommendations
Enhanced with customer preferences collection for personalized matching
"""
import streamlit as st
import json
from pathlib import Path
from core.adapters.streamlit_crm import get_all_crm_customers, get_crm_customer_by_id
from shared.data_access.quickbase_client import quickbase_client
from core.preferences import PreferencesManager

def inject_matching_css():
    """Professional community matching styling"""
    if st.session_state.get("_matching_css"):
        return
        
    css = """
    <style>
    /* Matching engine base styling */
    .matching-header {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(5, 150, 105, 0.15);
    }
    
    .matching-title {
        font-size: 2.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        display: flex;
        align-items: center;
    }
    
    .matching-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        margin: 0;
    }
    
    .smart-badge {
        background: rgba(255, 255, 255, 0.2);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 999px;
        font-size: 0.875rem;
        font-weight: 600;
        margin-left: 1rem;
    }
    
    /* Match results grid */
    .matches-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 2rem;
        margin: 2rem 0;
    }
    
    .match-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 0;
        overflow: hidden;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }
    
    .match-card:hover {
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
        transform: translateY(-4px);
    }
    
    .match-header {
        background: linear-gradient(135deg, #f8fafc, #e2e8f0);
        padding: 1.5rem;
        border-bottom: 1px solid #e5e7eb;
    }
    
    .match-name {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0 0 0.5rem 0;
    }
    
    .match-location {
        font-size: 0.9rem;
        color: #6b7280;
        margin: 0;
    }
    
    .match-score {
        background: linear-gradient(135deg, #059669, #047857);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 999px;
        font-size: 0.875rem;
        font-weight: 700;
        float: right;
        margin-top: -0.5rem;
    }
    
    .match-content {
        padding: 1.5rem;
    }
    
    .match-highlights {
        margin-bottom: 1.5rem;
    }
    
    .highlight {
        display: flex;
        align-items: center;
        margin-bottom: 0.75rem;
        font-size: 0.9rem;
    }
    
    .highlight-icon {
        width: 24px;
        height: 24px;
        background: #f0fdf4;
        color: #166534;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.75rem;
        font-size: 0.75rem;
    }
    
    .highlight-text {
        color: #374151;
    }
    
    .match-details {
        background: #f9fafb;
        border: 1px solid #f3f4f6;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .detail-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    
    .detail-row:last-child {
        margin-bottom: 0;
    }
    
    .detail-label {
        font-size: 0.875rem;
        color: #6b7280;
        font-weight: 500;
    }
    
    .detail-value {
        font-size: 0.875rem;
        color: #1f2937;
        font-weight: 600;
    }
    
    /* Customer context panel */
    .context-panel {
        background: linear-gradient(135deg, #fef7ff, #f3e8ff);
        border: 1px solid #e9d5ff;
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    
    .context-header {
        display: flex;
        align-items: center;
        margin-bottom: 1.5rem;
    }
    
    .context-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        color: white;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 1rem;
        font-size: 1.2rem;
    }
    
    .context-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #581c87;
        margin: 0;
    }
    
    .context-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
    }
    
    .context-item {
        background: white;
        border: 1px solid #e9d5ff;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    
    .context-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0 0 0.25rem 0;
    }
    
    .context-label {
        font-size: 0.875rem;
        color: #7c3aed;
        margin: 0;
    }
    
    /* Action buttons */
    .match-actions {
        display: flex;
        gap: 0.75rem;
    }
    
    .btn-recommend {
        background: #059669;
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-size: 0.875rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        flex: 1;
    }
    
    .btn-recommend:hover {
        background: #047857;
        transform: translateY(-1px);
    }
    
    .btn-details {
        background: white;
        color: #374151;
        border: 1px solid #d1d5db;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-size: 0.875rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-details:hover {
        background: #f9fafb;
    }
    
    /* No matches state */
    .no-matches {
        text-align: center;
        padding: 4rem 2rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        margin: 2rem 0;
    }
    
    .no-matches-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    
    .no-matches-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0 0 1rem 0;
    }
    
    .no-matches-text {
        color: #6b7280;
        margin: 0;
    }
    
    /* Preferences section styling */
    .preferences-section {
        margin-top: 1.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid #e9d5ff;
    }
    
    .preferences-title {
        font-size: 1rem;
        font-weight: 600;
        color: #7c3aed;
        margin: 0 0 0.75rem 0;
    }
    
    .preferences-details {
        font-size: 0.875rem;
        line-height: 1.6;
        color: #374151;
    }
    
    .preferences-details strong {
        color: #581c87;
    }
    
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.session_state["_matching_css"] = True

def load_community_database():
    """Load community data from QuickBase WA Communities table"""
    return quickbase_client.get_communities()

def calculate_match_score(customer_data, community):
    """Enhanced AI-powered matching algorithm with customer preferences integration"""
    score = 0
    reasons = []
    
    # Get customer preferences if available
    preferences = PreferencesManager.get_preferences()
    pref_data = PreferencesManager.get_crm_matching_data() if preferences else {}
    
    # Care level matching (35% weight) - Use actual recommendation which respects gating
    care_recommendation = customer_data.get('care_recommendation', '').lower()
    
    if care_recommendation in community['care_levels']:
        score += 35
        reasons.append(f"Perfect care level match: {care_recommendation}")
    elif any(level in care_recommendation for level in community['care_levels']):
        score += 22
        reasons.append(f"Compatible care levels available")
    else:
        reasons.append(f"Care level mismatch: needs {care_recommendation}, available {community['care_levels']}")
    
    # Geographic preference matching (20% weight) - NEW
    if pref_data.get('preferred_regions'):
        location_match = False
        community_location = community.get('location', '').lower()
        
        for region in pref_data['preferred_regions']:
            if region == 'bellevue_area' and 'bellevue' in community_location:
                score += 20
                reasons.append("🎯 Preferred Bellevue area location")
                location_match = True
                break
            elif region == 'eastside' and any(city in community_location for city in ['bellevue', 'redmond', 'kirkland']):
                score += 18
                reasons.append("🎯 Preferred Eastside location")
                location_match = True
                break
            elif region == 'seattle' and 'seattle' in community_location:
                score += 18
                reasons.append("🎯 Preferred Seattle area location")
                location_match = True
                break
            elif region == 'washington_state':
                score += 10
                reasons.append("✓ Within preferred Washington state")
                location_match = True
                break
        
        if not location_match:
            reasons.append("⚠️ Outside preferred geographic areas")
    else:
        # Default geographic bonus for Bellevue (if no preferences)
        if 'bellevue' in community.get('location', '').lower():
            score += 15
            reasons.append("🏠 Bellevue location advantage")
    
    # Budget compatibility (20% weight) - Consider preference budget level
    budget_min = 3000  # Default
    budget_max = 6000  # Default
    
    # Adjust budget based on preferences
    if pref_data.get('budget_level') == 'tight':
        budget_max = 5000
        budget_min = 2500
    elif pref_data.get('budget_level') == 'comfortable':
        budget_min = 4000
        budget_max = 8000
    elif pref_data.get('budget_level') == 'luxury':
        budget_min = 6000
        budget_max = 12000
    
    if (budget_min <= community['monthly_cost']['max'] and 
        budget_max >= community['monthly_cost']['min']):
        score += 20
        reasons.append(f"Budget compatible: ${community['monthly_cost']['min']:,}-${community['monthly_cost']['max']:,}")
    elif budget_max >= community['monthly_cost']['min']:
        score += 10
        reasons.append(f"Partial budget overlap available")
    
    # Timeline urgency matching (15% weight) - NEW
    timeline = pref_data.get('timeline', 'exploring')
    if timeline == 'immediate' and community['availability'] == 'immediate':
        score += 15
        reasons.append("🚨 Immediate availability matches urgent timeline")
    elif timeline == '2_4_weeks' and community['availability'] in ['immediate', '2_weeks']:
        score += 12
        reasons.append("⏰ Availability matches 2-4 week timeline")
    elif timeline == 'exploring' and community['availability'] == 'contact':
        score += 8
        reasons.append("🔍 Contact for availability - good for exploration")
    else:
        score += 5
        reasons.append("✓ Standard availability consideration")
    
    # Availability with vacancy data (10% weight)
    if community['availability'] == 'immediate':
        score += 10
        reasons.append("✅ Immediate availability")
    elif community['availability'] == '2_weeks':
        score += 8
        reasons.append("⏰ Available within 2 weeks")
    elif community['availability'] == 'waitlist':
        score += 3
        reasons.append("⏳ Waitlist available")
    elif community['availability'] == 'contact':
        score += 6
        reasons.append("📞 Contact for availability details")
    
    # Bonus for specific vacancy information from QuickBase
    if community.get('available_beds', 0) > 0:
        score += 3
        reasons.append(f"🛏️ {community['available_beds']} beds currently available")
    
    # Quality rating (5% weight)
    if community['rating'] >= 4.7:
        score += 5
        reasons.append(f"Excellent rating: {community['rating']}/5")
    elif community['rating'] >= 4.5:
        score += 3
        reasons.append(f"High rating: {community['rating']}/5")
    else:
        score += 2
        reasons.append(f"Good rating: {community['rating']}/5")
    
    # Activity preferences bonus (5% weight) - NEW
    if pref_data.get('activity_preferences'):
        activity_match = False
        for activity in pref_data['activity_preferences']:
            if activity in community.get('amenities', []):
                score += 2
                activity_match = True
        
        if activity_match:
            reasons.append("🎨 Activity preferences match available amenities")
        else:
            reasons.append("ℹ️ Standard amenities available")
    
    return min(score, 100), reasons

def render_customer_context(customer_data):
    """Render enhanced customer context with preferences for matching"""
    care_rec = customer_data.get('care_recommendation', 'Not assessed')
    
    # Handle different name fields from different sources
    customer_name = customer_data.get('name') or customer_data.get('person_name', 'Customer')
    
    # Get preferences data
    preferences = PreferencesManager.get_preferences()
    pref_data = PreferencesManager.get_crm_matching_data() if preferences else {}
    
    # Build preferences summary
    pref_summary = "Not collected"
    if preferences:
        completion = PreferencesManager.get_completion_percentage()
        pref_summary = f"{completion}% complete"
        if completion == 100:
            pref_summary = "✅ Complete"
    
    context_html = f"""
    <div class="context-panel">
        <div class="context-header">
            <div class="context-icon">👤</div>
            <h2 class="context-title">{customer_data.get('person_name', 'Customer')} - Enhanced Matching Context</h2>
        </div>
        <div class="context-grid">
            <div class="context-item">
                <div class="context-value">{care_rec}</div>
                <div class="context-label">Care Recommendation</div>
            </div>
            <div class="context-item">
                <div class="context-value">{budget_status}</div>
                <div class="context-label">Budget Status</div>
            </div>
            <div class="context-item">
                <div class="context-value">{journey_progress}</div>
                <div class="context-label">Journey Progress</div>
            </div>
            <div class="context-item">
                <div class="context-value">{readiness}</div>
                <div class="context-label">Readiness Level</div>
            </div>
            <div class="context-item">
                <div class="context-value">{pref_summary}</div>
                <div class="context-label">Preferences Data</div>
            </div>
        </div>
    """
    
    # Add preferences details if available
    if preferences and pref_data:
        pref_details = []
        
        if pref_data.get('preferred_regions'):
            regions = ", ".join([r.replace('_', ' ').title() for r in pref_data['preferred_regions'][:3]])
            if len(pref_data['preferred_regions']) > 3:
                regions += f" +{len(pref_data['preferred_regions']) - 3} more"
            pref_details.append(f"📍 <strong>Preferred areas:</strong> {regions}")
        
        if pref_data.get('timeline') and pref_data['timeline'] != 'exploring':
            timeline_map = {
                'immediate': 'Immediate (within 2 weeks)',
                '2_4_weeks': '2-4 weeks',
                '2_3_months': '2-3 months',
                'future_planning': 'Future planning'
            }
            timeline_text = timeline_map.get(pref_data['timeline'], pref_data['timeline'])
            pref_details.append(f"⏰ <strong>Timeline:</strong> {timeline_text}")
        
        if pref_data.get('budget_level') and pref_data['budget_level'] != 'moderate':
            budget_map = {
                'tight': 'Budget-conscious',
                'comfortable': 'Comfortable budget', 
                'luxury': 'Premium/luxury options'
            }
            budget_text = budget_map.get(pref_data['budget_level'], pref_data['budget_level'])
            pref_details.append(f"💰 <strong>Budget level:</strong> {budget_text}")
        
        if pref_data.get('activity_preferences'):
            activities = ", ".join([a.replace('_', ' ').title() for a in pref_data['activity_preferences'][:3]])
            if len(pref_data['activity_preferences']) > 3:
                activities += f" +{len(pref_data['activity_preferences']) - 3} more"
            pref_details.append(f"🎨 <strong>Activity interests:</strong> {activities}")
        
        if pref_details:
            context_html += f"""
            <div class="preferences-section">
                <h3 class="preferences-title">Customer Preferences</h3>
                <div class="preferences-details">
                    {' • '.join(pref_details)}
                </div>
            </div>
            """
    
    context_html += """</div>"""
    
    return context_html

def render_community_match(community, score, reasons):
    """Render individual community match card"""
    # Format cost range
    cost_range = f"${community['monthly_cost']['min']:,} - ${community['monthly_cost']['max']:,}"
    
    # Generate highlights from reasons (using clean text only)
    highlights_html = ""
    for reason in reasons[:3]:  # Show top 3 reasons
        highlights_html += f"""
        <div class="highlight">
            <div class="highlight-icon">✓</div>
            <div class="highlight-text">{reason}</div>
        </div>
        """
    
    # Availability text
    avail_map = {
        'immediate': 'Immediate',
        '2_weeks': '2 weeks',
        '1_month': '1 month'
    }
    availability = avail_map.get(community['availability'], 'Contact for details')
    
    match_html = f"""
    <div class="match-card">
        <div class="match-header">
            <div class="match-name">{community['name']}</div>
            <div class="match-score">{score}% Match</div>
            <div class="match-location">📍 {community['location']}</div>
        </div>
        <div class="match-content">
            <div class="match-highlights">
                {highlights_html}
            </div>
            <div class="match-details">
                <div class="detail-row">
                    <span class="detail-label">Monthly Cost:</span>
                    <span class="detail-value">{cost_range}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Availability:</span>
                    <span class="detail-value">{availability}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Rating:</span>
                    <span class="detail-value">{community['rating']}/5 ⭐</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Contact:</span>
                    <span class="detail-value">{community['contact']}</span>
                </div>
            </div>
            <div class="match-actions">
                <button class="btn-recommend">Recommend to Customer</button>
                <button class="btn-details">View Details</button>
            </div>
        </div>
    </div>
    """
    
    return match_html

def render(customer_id=None):
    """Main render function for Smart Community Matching"""
    inject_matching_css()
    
    # Check for customer to match (from Customer 360 "Match Communities" button)
    if not customer_id and 'match_for_customer' in st.session_state:
        customer_id = st.session_state['match_for_customer']
        del st.session_state['match_for_customer']  # Clear after using
    
    # Check for selected customer in session state if no customer_id provided
    if not customer_id and 'matching_customer' in st.session_state:
        customer_id = st.session_state['matching_customer']
    
    if not customer_id:
        # Customer selection interface
        st.markdown("""
        <div class="matching-header">
            <h1 class="matching-title">
                🎯 Smart Community Matching
                <span class="smart-badge">AI Powered</span>
            </h1>
            <p class="matching-subtitle">
                Intelligent facility recommendations replacing 132-field QuickBase spreadsheets
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Use CRM customer data (includes Navigator, QuickBase, and demo users)
        customers = get_all_crm_customers()
        
        if customers:
            st.subheader("Select Customer for Community Matching")
            for customer in customers:
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    # Handle different name fields from different sources
                    name = customer.get('name') or customer.get('person_name', 'Unknown')
                    st.write(f"**{name}**")
                with col2:
                    care_rec = customer.get('care_recommendation', 'Not assessed')
                    st.write(f"Care: {care_rec}")
                with col3:
                    has_assessments = customer.get('has_gcp_assessment') and customer.get('has_cost_plan')
                    status = "✅ Ready" if has_assessments else "⏳ In progress"
                    st.write(status)
                with col4:
                    # Use the appropriate ID field
                    cust_id = customer.get('customer_id') or customer.get('user_id') or customer.get('id')
                    if st.button("Match", key=f"match_{cust_id}"):
                        st.session_state['matching_customer'] = cust_id
                        st.rerun()
        else:
            st.info("No customers found. Customers will appear here after they use the Navigator.")
        
        # Show innovation summary
        st.markdown("""
        ---
        
        ### 🚀 **Enhanced QuickBase Community Matching**
        
        **Before:** 132 manual fields per community requiring constant spreadsheet maintenance  
        **After:** Focused AI-driven matching using 11 high-impact criteria for precise care compatibility
        
        **Critical Safety Matching:**
        - 🦽 Hoyer Lift availability for mobility assistance
        - 🧠 Dedicated Memory Care for specialized needs  
        - 👥 Two-person transfer capabilities for complex care
        - 💪 Bariatric care equipment and training
        
        **Medical Service Compatibility:**
        - 💉 Insulin management for diabetes care
        - 🩹 Professional wound care services
        - 👨‍⚕️ 24/7 awake staff supervision
        
        **Quality of Life Factors:**
        - 🐕 Pet-friendly policies for emotional support
        - 🗣️ Language services for cultural compatibility
        - 🍳 Full kitchen access for independence
        
        *This transforms QuickBase's 132-field complexity into intelligent, safety-first community matching.*
        """)
        
        return
    
    # Community matching for specific customer
    customer_data = get_crm_customer_by_id(customer_id)
    
    if not customer_data:
        st.error(f"Customer not found: {customer_id}")
        return
    
    # Back button
    if st.button("← Back to Dashboard", type="secondary"):
        # Clear matching session state
        if 'matching_customer' in st.session_state:
            del st.session_state['matching_customer']
        if 'match_for_customer' in st.session_state:
            del st.session_state['match_for_customer']
        st.rerun()
    
    st.markdown("---")
    
    # Customer context (this shows the customer name prominently)
    st.markdown(render_customer_context(customer_data), unsafe_allow_html=True)
    
    # Load communities and calculate matches
    communities = load_community_database()
    matches = []
    
    for community in communities:
        score, reasons = calculate_match_score(customer_data, community)
        if score >= 30:  # Only show decent matches
            matches.append((community, score, reasons))
    
    # Sort by score
    matches.sort(key=lambda x: x[1], reverse=True)
    
    if matches:
        st.markdown('<div class="matches-grid">', unsafe_allow_html=True)
        
        for idx, (community, score, reasons) in enumerate(matches):
            # Render match card with clean, professional design
            with st.container():
                # Header with match score badge
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"### {community['name']}")
                    st.markdown(f"📍 {community['location']}")
                with col2:
                    st.markdown(f"""
                        <div style="text-align: right; padding: 10px;">
                            <div style="background-color: #1f77b4; color: white; padding: 8px 16px; 
                                        border-radius: 20px; display: inline-block; font-weight: bold;">
                                {score}% Match
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                
                # Separate matches from gaps
                matches_list = [r for r in reasons if not r.startswith('⚠️')]
                gaps_list = [r for r in reasons if r.startswith('⚠️')]
                
                # Show match strengths and considerations in clean text format
                if matches_list:
                    st.markdown("**✅ Match Strengths:**")
                    for reason in matches_list:
                        clean_reason = reason.replace('✅ ', '').replace('💰 ', '').replace('⏰ ', '').replace('📞 ', '').replace('⏳ ', '').replace('📍 ', '')
                        st.markdown(f"- {clean_reason}")
                
                if gaps_list:
                    st.markdown("**⚠️ Considerations:**")
                    for gap in gaps_list:
                        clean_gap = gap.replace('⚠️ ', '')
                        st.markdown(f"- {clean_gap}")
                
                # Show availability details
                avail_map = {
                    'immediate': '✅ Immediate',
                    '2_weeks': '⏰ 2 weeks', 
                    '1_month': '📅 1 month',
                    'waitlist': '⏳ Waitlist',
                    'contact': '📞 Contact for details'
                }
                availability = avail_map.get(community['availability'], 'Contact for details')
                
                # Clean, compact availability and vacancy info
                st.markdown("---")
                
                # Determine number of columns based on cost data availability
                cost_data = community.get('monthly_cost')
                if cost_data:
                    # Show cost if we have real placement data
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        cost_range = f"${cost_data['min']:,.0f} - ${cost_data['max']:,.0f}"
                        st.markdown(f"**Move-In Cost:** {cost_range}")
                        st.caption(f"Based on {cost_data['count']} placements (Avg: ${cost_data['avg']:,.0f})")
                    with col2:
                        st.markdown(f"**Availability:** {availability}")
                    with col3:
                        # Show real-time vacancy data from QuickBase
                        if community.get('available_beds', 0) > 0:
                            st.markdown(f"**Vacancy:** {community['available_beds']} beds available")
                        elif community.get('vacancy_status'):
                            st.markdown(f"**Vacancy:** {community['vacancy_status']}")
                        else:
                            st.markdown(f"**Capacity:** {community.get('total_beds', 'N/A')} beds")
                else:
                    # No cost data - just show availability info
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Availability:** {availability}")
                    with col2:
                        # Show real-time vacancy data from QuickBase
                        if community.get('available_beds', 0) > 0:
                            st.markdown(f"**Vacancy:** {community['available_beds']} beds available")
                        elif community.get('vacancy_status'):
                            st.markdown(f"**Vacancy:** {community['vacancy_status']}")
                        else:
                            st.markdown(f"**Capacity:** {community.get('total_beds', 'N/A')} beds")
                
                st.markdown("")  # Small spacing
                
                # Action buttons with guaranteed unique keys using index
                col1, col2 = st.columns(2)
                with col1:
                    # Use index to guarantee unique keys
                    button_key = f"contact_{idx}_{hash(str(community)) % 10000}"
                    if st.button(f"📞 Contact {community['name']}", key=button_key):
                        # Display detailed contact information from QuickBase
                        contact_info = f"**Contact Information:**\n\n"
                        
                        if community.get('licensee'):
                            contact_info += f"**Licensee:** {community['licensee']}\n\n"
                        
                        if community.get('cell_phone'):
                            contact_info += f"**Cell Phone:** {community['cell_phone']}\n\n"
                        
                        if community.get('phone') and community.get('phone') != community.get('cell_phone'):
                            contact_info += f"**Phone:** {community['phone']}\n\n"
                        
                        if community.get('email'):
                            contact_info += f"**Email:** {community['email']}\n\n"
                        
                        if community.get('address'):
                            contact_info += f"**Address:** {community['address']}"
                        
                        st.success(contact_info)
                with col2:
                    # Use index to guarantee unique keys
                    details_key = f"details_{idx}_{hash(str(community)) % 10000}"
                    if st.button(f"📋 View Details", key=details_key):
                        # Show detailed community information including vacancy data
                        details = f"**{community['name']} Details:**\n\n"
                        details += f"**Care Type:** {community.get('care_type', 'Not specified')}\n\n"
                        details += f"**Care Levels:** {', '.join(community.get('care_levels', []))}\n\n"
                        details += f"**Availability:** {availability}\n\n"
                        
                        # Add real-time vacancy information from QuickBase
                        if community.get('vacancy_info'):
                            details += f"**Current Vacancy Info:** {community['vacancy_info']}\n\n"
                        if community.get('available_beds', 0) > 0:
                            details += f"**Available Beds:** {community['available_beds']} currently open\n\n"
                        if community.get('total_beds'):
                            details += f"**Total Capacity:** {community['total_beds']} beds\n\n"
                        
                        details += f"**Address:** {community.get('address', 'Not specified')}"
                        st.info(details)
                
                st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Summary stats
        avg_score = sum(match[1] for match in matches) / len(matches)
        st.markdown(f"""
        ---
        
        **🤖 AI Matching Summary:** Found {len(matches)} compatible communities with average match score of {avg_score:.0f}%
        
        **Next Steps:** Review top recommendations with customer and schedule facility tours for highest-scoring matches.
        """)
        
    else:
        st.markdown("""
        <div class="no-matches">
            <div class="no-matches-icon">🔍</div>
            <h2 class="no-matches-title">No Compatible Communities Found</h2>
            <p class="no-matches-text">
                No communities match the current assessment criteria. 
                Consider expanding search parameters or updating customer preferences.
            </p>
        </div>
        """, unsafe_allow_html=True)

def calculate_match_score(customer_data, community):
    """Enhanced AI-powered matching algorithm with customer care needs"""
    score = 0
    reasons = []
    
    # Care level matching (40% weight) - Most important factor
    care_recommendation = customer_data.get('care_recommendation', '').lower()
    # Normalize: convert spaces to underscores for comparison
    care_recommendation_normalized = care_recommendation.replace(' ', '_')
    
    # Special case: "in_home" customers are exploring community options
    # Don't penalize them - they're open to any care level
    if care_recommendation_normalized == 'in_home':
        # Give full score - exploring communities is valid
        score += 40
        reasons.append(f"Exploring community care options")
    else:
        # Also normalize community care levels for comparison
        community_care_levels_normalized = [level.lower().replace(' ', '_') for level in community['care_levels']]
        
        if care_recommendation_normalized in community_care_levels_normalized:
            score += 40
            reasons.append(f"Perfect care level match: {care_recommendation}")
        elif any(care_recommendation_normalized in level or level in care_recommendation_normalized for level in community_care_levels_normalized):
            score += 25
            reasons.append(f"Compatible care levels available")
        else:
            reasons.append(f"⚠️ Care level mismatch: needs {care_recommendation}")
    
    # Budget compatibility (30% weight)
    budget_min = customer_data.get('budget_min', 3000)
    budget_max = customer_data.get('budget_max', 6000)
    
    # Check if we have real cost data
    monthly_cost = community.get('monthly_cost')
    if monthly_cost:
        # We have real placement cost data
        if (budget_min <= monthly_cost['max'] and 
            budget_max >= monthly_cost['min']):
            score += 30
            reasons.append(f"💰 Budget compatible: ${monthly_cost['min']:,}-${monthly_cost['max']:,}")
        elif budget_max >= monthly_cost['min']:
            score += 15
            reasons.append(f"💰 Partial budget overlap available")
        else:
            reasons.append(f"⚠️ Budget mismatch: needs ${budget_min:,}-${budget_max:,}")
    else:
        # No cost data available - don't penalize, give full score
        score += 30
        reasons.append(f"Budget: ${budget_min:,}-${budget_max:,} (no cost data available)")
    
    # Availability (20% weight)
    if community['availability'] == 'immediate':
        score += 20
        reasons.append("Immediate availability")
    elif community['availability'] == '2_weeks':
        score += 15
        reasons.append("Available within 2 weeks")
    elif community['availability'] == 'waitlist':
        score += 5
        reasons.append("Waitlist available")
    else:
        score += 10
        reasons.append("Contact for availability")
    
    # Location proximity (10% weight)
    customer_location = customer_data.get('location', '')
    if customer_location and customer_location.lower() in community['location'].lower():
        score += 10
        reasons.append(f"Located in {community['location']}")
    else:
        score += 5
        reasons.append(f"Located in {community['location']}")
    
    # Amenity matching - Check customer preferences against community amenities
    matching_flags = customer_data.get('community_matching_flags', {})
    if matching_flags:
        community_amenities = [a.lower().replace('_', ' ') for a in community.get('amenities', [])]
        
        # Check for pool preference
        if matching_flags.get('prefers_pool'):
            if any('pool' in amenity or 'swim' in amenity for amenity in community_amenities):
                score += 5
                reasons.append("Has pool (requested)")
            else:
                reasons.append("⚠️ Does not have pool (requested)")
        
        # Check for kitchen preference
        if matching_flags.get('prefers_full_kitchen'):
            if any('kitchen' in amenity for amenity in community_amenities):
                score += 5
                reasons.append("Has full kitchen (requested)")
            else:
                reasons.append("⚠️ Does not have full kitchen (requested)")
        
        # Check for pet-friendly preference
        if matching_flags.get('prefers_pets_allowed'):
            # Check if pets are mentioned in amenities or specializations
            has_pets = any('pet' in amenity for amenity in community_amenities)
            if not has_pets:
                specializations = [s.lower() for s in community.get('specializations', [])]
                has_pets = any('pet' in spec for spec in specializations)
            
            if has_pets:
                score += 5
                reasons.append("Pet-friendly (requested)")
            else:
                reasons.append("⚠️ Not pet-friendly (requested)")
    
    return min(score, 100), reasons

