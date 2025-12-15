"""
FAQ Page - AI Advisor "Navi"

Conversational AI advisor interface with dynamic question suggestions.
Questions rotate based on user context (care flags, cost planner flags).
Maintains archive of previously asked questions.

FLAG-DRIVEN PERSONALIZATION:
- Uses NaviOrchestrator.get_suggested_questions() for centralized flag logic
- Surfaces 3 most relevant questions at any time
- Auto-refreshes as user completes products and flags change

LLM-POWERED FAQ (Stage 3):
- Natural language query via TF-IDF retrieval
- Grounded answers using ai/llm_mediator with policy enforcement
- Max 120 words, no hallucinations, safe CTAs only
"""

from __future__ import annotations

from typing import Any, Optional
import html
import json
import re

import streamlit as st
import numpy as np

from core.flags import get_all_flags, get_flag_value
from core.mcip import MCIP
from core.nav import route_to
from core.navi import NaviOrchestrator
from core.url_helpers import add_uid_to_href, back_to_lobby
from ui.header_simple import render_header_simple
from ui.footer_simple import render_footer_simple


# ==============================================================================
# HTML SANITIZATION
# ==============================================================================
_HTML_BLOCK_TAGS = re.compile(r'</?(div|span|p|section|article|header|footer)[^>]*>', re.I)


def _sanitize_to_md(text: str) -> str:
    """Strip common block tags and sanitize to safe Markdown.
    
    Removes HTML block tags while preserving inline Markdown formatting
    (**bold**, *italics*, etc.).
    
    Args:
        text: Raw text that may contain HTML
        
    Returns:
        Sanitized text safe for Markdown rendering
    """
    if not isinstance(text, str):
        return ""
    
    # Strip common block tags (div, span, p, section, etc.)
    text = _HTML_BLOCK_TAGS.sub('', text)
    
    # Convert <br> tags to newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    return text.strip()


# ==============================================================================
# QUESTION DATABASE LOADER
# ==============================================================================
@st.cache_data
def load_faq_items() -> list[dict[str, Any]]:
    """Load FAQ questions from config/faq.json.
    
    Returns:
        List of FAQ question dicts with schema:
        {
            "id": str,
            "question": str,
            "answer": str,
            "tags": list[str],
            "triggers": list[str],
            "flags": list[str],
            "priority": int,
            "category": str,
            "ctas": list[dict]
        }
    """
    with open("config/faq.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_faq_policy() -> dict[str, Any]:
    """Load FAQ policy guardrails from config/faq_policy.json.
    
    Returns:
        Policy dict with schema:
        {
            "allowed_products": list[str],
            "allowed_terms": list[str],
            "banned_phrases": list[str],
            "fallback_name": str,
            "default_cta": dict
        }
    """
    with open("config/faq_policy.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_faq_recommended() -> list[dict[str, Any]]:
    """Load canonical recommended FAQ questions from config/faq_recommended.json.
    
    These are the top 3 chips shown at the top of the page. They bypass retrieval
    and always return a deterministic answer from the FAQ database.
    
    Returns:
        List of recommended FAQ dicts with schema:
        {
            "id": str,        # FAQ ID from faq.json
            "label": str      # Display text for chip (from FAQ question)
        }
    """
    with open("config/faq_recommended.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    faqs = {f["id"]: f for f in load_faq_items()}
    recs = []
    
    for r in data.get("items", []):
        item = faqs.get(r["id"])
        if not item or not item.get("answer"):
            # Skip missing or empty FAQs (should be caught by CI validation)
            continue
        recs.append({
            "id": item["id"],
            "label": item["question"]  # Chip text comes from canonical question
        })
    
    return recs


@st.cache_data
def load_easter_eggs() -> list[dict[str, Any]]:
    """Load easter egg patterns from config/easter_eggs.json.
    
    Returns:
        List of easter egg dicts with schema:
        {
            "id": str,
            "match": str,      # Regex pattern
            "reply": str,      # Response text
            "cta": dict | None,
            "env": list[str]   # ["dev", "staging", "prod"]
        }
    """
    try:
        with open("config/easter_eggs.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def try_easter_egg(query: str) -> dict[str, Any] | None:
    """Check if query matches an easter egg pattern.
    
    Args:
        query: User's question text
        
    Returns:
        Easter egg dict if matched, None otherwise
    """
    import os
    
    # Check environment (default to dev for local)
    env = os.getenv("STREAMLIT_ENV", "dev")
    
    eggs = load_easter_eggs()
    for egg in eggs:
        # Check if egg is enabled for this environment
        if env not in egg.get("env", ["dev"]):
            continue
        
        # Check if query matches pattern
        pattern = egg.get("match", "")
        if pattern and re.search(pattern, query):
            return egg
    
    return None


def ask_direct_faq(faq_id: str, name: str | None) -> dict[str, Any]:
    """Answer a FAQ question directly without retrieval (deterministic).
    
    Used for recommended chips to ensure they always work regardless of
    TF-IDF performance or website crawl status.
    
    Args:
        faq_id: FAQ ID from faq.json
        name: User's name for personalization (optional)
        
    Returns:
        Answer dict with schema:
        {
            "answer": str,
            "sources": list[dict],  # [{"title": str, "url": str}]
            "cta": dict | None
        }
    """
    faqs = load_faq_items()
    faq = next((f for f in faqs if f["id"] == faq_id), None)
    policy = load_faq_policy()
    
    if not faq:
        # Fallback if FAQ ID missing (shouldn't happen with CI validation)
        return {
            "answer": "We don't have that in our FAQ yet. You can start the Guided Care Plan to get a tailored next step.",
            "sources": [],
            "cta": policy.get("default_cta")
        }
    
    # Return stored answer verbatim (deterministic, fast)
    return {
        "answer": faq["answer"],
        "sources": [{"title": f"From CCA FAQ: {faq.get('question', 'Untitled')}", "url": ""}],
        "cta": (faq.get("ctas") or [None])[0]
    }



# ==============================================================================
# RETRIEVAL LAYER (TF-IDF)
# ==============================================================================
@st.cache_data
def retrieve_faq(query: str, faqs: list[dict], k: int = 3) -> list[dict]:
    """Retrieve top-k most relevant FAQs using TF-IDF cosine similarity.
    
    Args:
        query: User's natural language question
        faqs: List of FAQ dicts from load_faq_items()
        k: Number of results to return (default 3)
        
    Returns:
        List of top-k FAQ dicts with similarity > 0, sorted by relevance
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Combine question + answer for richer matching
        texts = [f"{f['question']} {f['answer']}" for f in faqs]
        
        vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
        X = vectorizer.fit_transform(texts)
        q_vec = vectorizer.transform([query])
        
        sims = cosine_similarity(q_vec, X).flatten()
        top_idx = np.argsort(sims)[::-1][:k]
        
        # Only return results with positive similarity
        return [faqs[i] for i in top_idx if sims[i] > 0]
    except Exception as e:
        print(f"[FAQ_RETRIEVAL_ERROR] {e}")
        return []


# ==============================================================================
# CORPORATE KNOWLEDGE LOADER + RETRIEVER (Stage 3.5)
# ==============================================================================
@st.cache_data(ttl=None, show_spinner=False)
def _get_corp_chunks_mtime() -> float:
    """Get modification time of corp_knowledge.jsonl for cache invalidation."""
    import os
    chunks_path = "config/corp_knowledge.jsonl"
    try:
        return os.path.getmtime(chunks_path)
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False)
def load_corp_chunks(_mtime: float | None = None) -> list[dict[str, Any]]:
    """Load corporate knowledge chunks from prebuilt index or JSONL fallback.
    
    Prefers config/corp_index.pkl (instant loading) over JSONL (slower parsing).
    Cache automatically refreshes when file is updated (via _mtime parameter).
    
    Args:
        _mtime: File modification time (for cache invalidation, passed by caller)
    
    Returns:
        List of chunk dicts with schema:
        {
            "doc_id": str,
            "url": str,
            "title": str,
            "heading": str,
            "text": str,
            "last_fetched": str,
            "tags": list[str],
            "type": str  # about, leadership, services, blog (Stage 3.6)
        }
    """
    import os
    import pickle
    from pathlib import Path
    
    # Try prebuilt index first (instant loading)
    index_path = Path("config/corp_index.pkl")
    if index_path.exists():
        try:
            with index_path.open("rb") as f:
                index_data = pickle.load(f)
            chunks = index_data['chunks']
            built_at = index_data.get('built_at', 'unknown')
            print(f"[RAG_STATS] chunks={len(chunks)} source=prebuilt_index built={built_at}")
            return chunks
        except Exception as e:
            print(f"[RAG_LOAD_ERROR] Failed to load prebuilt index: {e}, falling back to JSONL")
    
    # Fallback to JSONL (original logic)
    try:
        chunks_path = "config/corp_knowledge.jsonl"
        if not os.path.exists(chunks_path):
            print(f"[CORP_KNOWLEDGE_WARN] {chunks_path} not found - run 'make sync-site'")
            return []
        
        chunks = []
        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    chunks.append(json.loads(line))
                except Exception:
                    pass
        print(f"[RAG_STATS] chunks={len(chunks)} source=config/corp_knowledge.jsonl")
        return chunks
    except Exception as e:
        print(f"[CORP_CHUNKS_ERROR] {e}")
        return []


@st.cache_data
def load_corp_mini_faq() -> list[dict[str, Any]]:
    """Load curated mini-FAQ for identity questions (Stage 3.6).
    
    Returns:
        List of mini-FAQ dicts with schema:
        {
            "id": str,
            "q": str,
            "a": str,
            "ctas": list[dict]  # [{"label": str, "route": str}]
        }
    """
    import os
    p = "config/corp_mini_faq.json"
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[MINI_FAQ_LOAD_ERROR] {e}")
    return []


@st.cache_resource
def build_corp_index(chunks: tuple) -> tuple:
    """Load prebuilt TF-IDF index or build in-memory fallback (Stage 3.6).
    
    Prefers loading from config/corp_index.pkl (instant) over rebuilding.
    
    Args:
        chunks: Tuple of chunk JSON strings (for hashability)
        
    Returns:
        Tuple of (vectorizer, matrix, chunk_list) for reuse
    """
    import pickle
    from pathlib import Path
    
    # Try prebuilt index first
    index_path = Path("config/corp_index.pkl")
    if index_path.exists():
        try:
            with index_path.open("rb") as f:
                index_data = pickle.load(f)
            return index_data['vectorizer'], index_data['matrix'], index_data['chunks']
        except Exception as e:
            print(f"[RAG_INDEX_ERROR] Failed to load prebuilt index: {e}, rebuilding...")
    
    # Fallback: build in-memory (original logic)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        if not chunks:
            return None, None, []
        
        # Deserialize JSON strings back to dicts
        chunk_list = [json.loads(c) if isinstance(c, str) else c for c in chunks]
        texts = [f"{c.get('heading', '')} {c.get('text', '')}" for c in chunk_list]
        
        vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
        X = vectorizer.fit_transform(texts)
        
        print("[RAG_INDEX_WARN] Built in-memory (should use prebuilt index)")
        return vectorizer, X, chunk_list
    except Exception as e:
        print(f"[CORP_INDEX_BUILD_ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None, None, []


@st.cache_data
def retrieve_corp(query: str, chunks: list[dict], k: int = 5) -> list[dict]:
    """Retrieve top-k most relevant corp knowledge chunks using weighted TF-IDF.
    
    Applies priors to prioritize authoritative content (about/leadership/services)
    and boost fresh content (<90 days old). Uses cached index for faster retrieval.
    
    Args:
        query: User's natural language question
        chunks: List of chunk dicts from load_corp_chunks()
        k: Number of results to return (default 5)
        
    Returns:
        List of top-k chunk dicts with similarity > 0, sorted by relevance
    """
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        from datetime import datetime
        
        if not chunks:
            return []
        
        # Build/get cached index
        chunks_tuple = tuple(json.dumps(c, sort_keys=True) for c in chunks)
        vectorizer, X, chunk_list = build_corp_index(chunks_tuple)
        
        if vectorizer is None or X is None:
            return []
        
        # Transform query
        q_vec = vectorizer.transform([query])
        sims = cosine_similarity(q_vec, X).flatten()
        
        # Apply weighted priors (Stage 3.6)
        def prior(ctype: str) -> float:
            """Authoritative content gets boost."""
            if ctype in ("about", "leadership"):
                return 0.25
            if ctype == "services":
                return 0.10
            return 0.0
        
        def freshness_bonus(chunk: dict) -> float:
            """Fresh content (<90 days) gets small boost."""
            try:
                last_fetched = chunk.get("last_fetched", "")
                if not last_fetched:
                    return 0.0
                dt = datetime.fromisoformat(last_fetched.replace("Z", ""))
                age_days = (datetime.utcnow() - dt).days
                return 0.05 if age_days < 90 else 0.0
            except Exception:
                return 0.0
        
        # Add priors to similarity scores
        priors = np.array([prior(c.get("type", "blog")) for c in chunk_list])
        freshness = np.array([freshness_bonus(c) for c in chunk_list])
        scores = sims + priors + freshness
        
        top_idx = np.argsort(scores)[::-1][:k]
        
        # Only return results with positive score
        return [chunk_list[i] for i in top_idx if scores[i] > 0]
    except Exception as e:
        print(f"[CORP_RETRIEVAL_ERROR] {e}")
        return []


# ==============================================================================
# MINI-FAQ ROUTING (Stage 3.6)
# ==============================================================================
IDENTITY_RE = re.compile(
    r"(?:^|\b)(?:who\s+(?:is|are)\s+(?:cca|concierge\s+care\s+advisors)|"
    r"about\s+(?:cca|concierge\s+care\s+advisors)|"
    r"(?:leadership|leadership\s+team|executives)|"
    r"(?:founded|how\s+long\s+in\s+business|been\s+around))",
    re.IGNORECASE
)


def try_mini_faq(user_q: str) -> dict[str, Any] | None:
    """Try to match identity question to curated mini-FAQ.
    
    Args:
        user_q: User's question text
        
    Returns:
        Mini-FAQ dict if pattern matches, else None
    """
    mini = load_corp_mini_faq()
    
    if not mini:
        return None
    
    if not IDENTITY_RE.search(user_q or ""):
        return None
    
    # Simple keyword matching to pick best entry
    q_lower = (user_q or "").lower()
    
    # Check for specific keywords
    if any(k in q_lower for k in ["who is cca", "who are", "about cca", "about concierge"]):
        for item in mini:
            if item["id"] == "corp_who_is_cca":
                return item
    
    if any(k in q_lower for k in ["leadership", "team", "executives", "who runs"]):
        for item in mini:
            if item["id"] == "corp_leadership":
                return item
    
    if any(k in q_lower for k in ["founded", "how long", "been around", "been in business"]):
        for item in mini:
            if item["id"] == "corp_founded":
                return item
    
    # Fallback to first match if pattern matched but no specific keyword
    return mini[0] if mini else None


# Load question database from JSON
QUESTION_DATABASE = load_faq_items()


# ==============================================================================
# LEGACY HARDCODED DATABASE (removed - now loaded from config/faq.json)
# ==============================================================================
# Preserved for reference only - all questions now externalized
_LEGACY_QUESTION_DATABASE = [
    # DEFAULT QUESTIONS - shown when no flags exist
    {
        "flags": [],  # Always available
        "priority": 3,
        "category": "planning",
        "question": "Where do I start with care planning?",
        "triggers": [
            "care plan",
            "where do i start",
            "how to start",
            "care planning",
            "getting started",
        ],
        "response": "Let's get started with a clear plan. The **Guided Care Plan** is a 10-15 minute assessment that:\n- Evaluates current care needs\n- Identifies safety concerns\n- Recommends personalized care options\n\nNext, use the **Cost Planner** to estimate costs and explore funding. Then, connect with an expert via **Plan for My Advisor** in the Concierge Hub.",
    },
    {
        "flags": [],
        "priority": 3,
        "category": "cost",
        "question": "What does Medicare cover for care?",
        "triggers": ["medicare", "medi care"],
        "response": "Let's clarify Medicare's role in care. **Medicare does not cover long-term custodial care** (like help with daily tasks), but it may cover:\n- Short-term skilled nursing (up to 100 days post-hospitalization)\n- Limited home health services for medical needs\n- Hospice care for end-of-life support\n\nFor ongoing care, explore Medicaid, VA benefits, or private pay. The **Cost Planner** can help you find funding options.",
    },
    {
        "flags": [],
        "priority": 3,
        "category": "planning",
        "question": "What are my next steps after planning?",
        "triggers": ["next", "what now", "what should i do", "how to proceed", "what's next"],
        "response": "You're on the right track! Here's how to move forward:\n1. **Assess Needs**: Use the **Guided Care Plan** to understand care requirements.\n2. **Estimate Costs**: Run the **Cost Planner** to see expenses and funding options.\n3. **Get Expert Help**: Schedule a **Plan for My Advisor** consultation in the Concierge Hub.\n4. **Take Action**: Implement your plan with professional support.\n\nStart or continue in the Concierge Hub — we're here to help every step of the way!",
    },
    # SAFETY & URGENCY FLAGS (Priority 1)
    {
        "flags": ["fall_risk", "mobility_concern"],
        "priority": 1,
        "category": "care",
        "question": "How can I reduce fall risk at home?",
        "triggers": ["fall risk", "falling", "fall prevention", "home safety", "grab bars"],
        "response": "**Fall prevention is critical.** Here's what to do now:\n\n**Immediate actions:**\n- Remove tripping hazards (rugs, cords, clutter)\n- Improve lighting in hallways and stairs\n- Install grab bars in bathroom\n- Consider medical alert device\n\n**Home modifications:**\n- Non-slip mats in bathroom\n- Raised toilet seat\n- Stair railings on both sides\n- Night lights in bedroom/bathroom path\n\n**Cost:** $500–$2,000 for basic modifications. VA benefits may cover some costs for veterans. Use the **Cost Planner's home modification module** to get estimates.",
    },
    {
        "flags": ["cog_moderate", "cog_severe", "cognitive_decline"],
        "priority": 1,
        "category": "care",
        "question": "What's the difference between Memory Care and Assisted Living?",
        "triggers": ["memory care", "assisted living", "difference", "dementia care", "alzheimer"],
        "response": "**Assisted Living:**\n- For seniors who need help with daily activities\n- Average: $5,500/month\n- Standard staffing and supervision\n- Mix of independent and assisted residents\n\n**Memory Care:**\n- Specialized for dementia/Alzheimer's\n- Average: $7,200/month (higher for high acuity)\n- Secured environment (prevent wandering)\n- Staff trained in cognitive care\n- Specialized activities and therapies\n\n**Memory care is appropriate when:**\n- Cognitive decline creates safety risks\n- Wandering or getting lost\n- Needs 24/7 supervision\n- Requires specialized engagement\n\nUse the **Guided Care Plan** to assess needs, then check local pricing with the **Cost Planner**.",
    },
    {
        "flags": ["medication_management", "med_complexity"],
        "priority": 1,
        "category": "care",
        "question": "Who can help manage medications safely?",
        "triggers": [
            "medication",
            "meds",
            "medication management",
            "pill management",
            "prescriptions",
        ],
        "response": "**Medication safety is critical.** Options for help:\n\n**In-Home Care:**\n- Caregivers can provide medication reminders\n- Some agencies offer medication administration (requires licensed staff)\n- Cost: $28–$40/hour\n\n**Assisted Living/Memory Care:**\n- Staff provides medication management\n- Included in monthly cost (~$5,500–$7,200/month)\n\n**Technology Solutions:**\n- Pill dispensers with alarms ($50–$300)\n- Smart pill boxes that notify family\n- Pharmacy auto-refill services\n\n**Important:** Complex medication regimens may require licensed nursing care. Discuss with your doctor.",
    },
    # VETERAN FLAGS (Priority 2)
    {
        "flags": ["veteran_eligible", "is_veteran"],
        "priority": 2,
        "category": "benefits",
        "question": "Am I eligible for VA Aid & Attendance benefits?",
        "triggers": ["va", "veteran", "aid and attendance", "veterans benefits", "va benefits"],
        "response": "We're here to support veterans and their families. You may qualify for **VA Aid & Attendance** or Community Care programs to help cover care costs.\n\n**Eligibility often includes:**\n- Being a veteran or surviving spouse\n- Wartime service (even 1 day during wartime period)\n- Needing help with daily activities (ADLs)\n- Meeting income and asset limits\n\n**Benefit amounts:**\n- Veteran with spouse: up to $2,431/month\n- Single veteran: up to $2,050/month\n- Surviving spouse: up to $1,318/month\n\n**What it covers:**\n- In-home care\n- Assisted living\n- Memory care\n\nCheck your eligibility with the **VA Benefits module** in the Cost Planner to see how much support you can get.",
    },
    {
        "flags": ["veteran_eligible", "is_veteran", "is_home_owner"],
        "priority": 2,
        "category": "benefits",
        "question": "Can VA help with home modifications for safety?",
        "triggers": ["va home", "home modification veteran", "hisa", "va home improvements"],
        "response": "Yes! The VA offers several programs to help veterans make homes safer:\n\n**HISA Grant (Home Improvements and Structural Alterations):**\n- Up to $6,800 for service-connected disabilities\n- Up to $2,000 for non-service-connected\n- Covers ramps, grab bars, widened doorways, roll-in showers\n\n**SAH/SHA Grants (for service-connected disabilities):**\n- SAH: up to $101,754 for specially adapted housing\n- SHA: up to $20,387 for home modifications\n\n**Application:** Work with your VA social worker or contact your regional VA office.\n\nUse the **Cost Planner's home modification module** to estimate costs and apply for VA grants.",
    },
    # HOME CARE & IN-HOME FLAGS (Priority 2)
    # HOME CARE & IN-HOME FLAGS (Priority 2)
    {
        "flags": ["in_home_care", "home_care_recommended"],
        "priority": 2,
        "category": "cost",
        "question": "How much does in-home care cost in my area?",
        "triggers": [
            "home care cost",
            "home care price",
            "cost of home care",
            "in-home care cost",
            "how much",
        ],
        "response": "Non-medical in-home care typically costs **$28–$40/hour**, depending on your area. For 20 hours a week, that's about **$2,400–$3,200/month**.\n\n**Factors affecting cost:**\n- Geographic location (urban vs. rural)\n- Hours per week needed\n- Specialized care (dementia care costs more)\n- Agency vs. independent caregiver\n\n**Typical care packages:**\n- Light support (10 hrs/week): $1,200–$1,600/month\n- Part-time (20 hrs/week): $2,400–$3,200/month\n- Full-time (40 hrs/week): $4,800–$6,400/month\n\nSince prices vary by location, use the **Cost Planner** with your ZIP code to get a personalized estimate and explore funding options.",
    },
    {
        "flags": ["is_home_owner", "aging_in_place"],
        "priority": 2,
        "category": "planning",
        "question": "How can I make my home safer for aging in place?",
        "triggers": [
            "aging in place",
            "home safety",
            "home modification",
            "stay at home",
            "modifications",
        ],
        "response": "Making your home safer can help you or your loved one stay independent. **Common modifications:**\n\n**Bathroom ($500–$2,000):**\n- Grab bars near toilet and shower\n- Non-slip mats\n- Raised toilet seat\n- Walk-in tub or roll-in shower ($3,000–$10,000)\n\n**Mobility ($1,000–$15,000):**\n- Wheelchair ramps\n- Stairlifts ($3,000–$5,000)\n- Widened doorways\n- Lever door handles\n\n**General Safety ($200–$1,000):**\n- Improved lighting\n- Remove trip hazards\n- Night lights\n- Medical alert system\n\n**Funding options:**\n- VA benefits (HISA grants for veterans)\n- Medicaid waivers (some states)\n- Home equity or personal savings\n\nThe **Cost Planner** can help you estimate costs and identify funding for home modifications.",
    },
    # COGNITIVE CARE FLAGS (Priority 2)
    {
        "flags": ["cog_moderate", "cog_severe", "dementia_care"],
        "priority": 2,
        "category": "care",
        "question": "What is memory care and how much does it cost?",
        "triggers": ["memory care", "dementia", "alzheimer", "alzheimers", "memory care cost"],
        "response": "Memory care provides specialized support for those with Alzheimer's or dementia in a safe, structured environment.\n\n**Average costs:**\n- Standard memory care: $7,200/month\n- High-acuity care: $9,000+/month\n- Geographic variation: $5,000–$12,000/month\n\n**Services include:**\n- Secured facilities (prevent wandering)\n- Specialized staff and cognitive therapies\n- 24/7 supervision\n- Structured daily activities\n- Medication management\n- Memory-focused programming\n\n**When is memory care needed?**\n- Moderate to severe cognitive decline\n- Safety concerns (wandering, leaving stove on)\n- Needs 24/7 supervision\n- Caregiver burnout\n\nUse the **Guided Care Plan** to assess needs, then check local pricing with the **Cost Planner**.",
    },
    {
        "flags": ["caregiver_strain", "family_caregiver"],
        "priority": 2,
        "category": "support",
        "question": "What support is available for family caregivers?",
        "triggers": [
            "caregiver support",
            "respite care",
            "family caregiver",
            "caregiver help",
            "caregiver burnout",
        ],
        "response": "Caring for a loved one is rewarding but challenging. **Respite care and support services** can give you a break:\n\n**In-Home Respite:**\n- Professional caregiver comes to your home\n- Cost: $28–$40/hour\n- Flexible scheduling (few hours to overnight)\n\n**Adult Day Programs:**\n- Social activities and supervision during the day\n- Cost: $50–$150/day\n- Usually 8am–5pm, meals included\n\n**Short-Term Facility Care:**\n- Assisted living or memory care for a few days/weeks\n- Cost: $200–$400/day\n\n**Support Groups:**\n- Often free or low-cost\n- Emotional support and practical tips\n- Many available online\n\n**Funding may be available through:**\n- VA benefits for veterans' families\n- Medicaid waivers (some states)\n- Long-term care insurance\n\nExplore your options with the **Cost Planner** and connect with a **Plan for My Advisor** expert for guidance.",
    },
    # MEDICAID FLAGS (Priority 2)
    {
        "flags": ["medicaid_likely", "has_medicaid", "financial_gap"],
        "priority": 2,
        "category": "benefits",
        "question": "Does Medicaid cover long-term care?",
        "triggers": ["medicaid", "medical aid", "medicaid coverage", "medicaid long term care"],
        "response": "Medicaid can help with long-term care costs, but eligibility varies by state.\n\n**Typical eligibility:**\n- Income below ~$2,800/month (varies by state)\n- Assets below ~$2,000 (individual, excludes home in some cases)\n- A medical need for care\n\n**What Medicaid covers:**\n- Nursing home care (all states)\n- Assisted living (many states, through waivers)\n- In-home care (varies by state)\n- Memory care (varies by state)\n\n**Spousal protections:**\n- Healthy spouse can keep home\n- Can keep ~$30,000–$150,000 in assets (varies by state)\n- Minimum monthly income allowance (~$2,500)\n\n**Important:** Rules vary significantly by state. Some states have 5-year look-back period for asset transfers.\n\nThe **Medicaid module** in the Cost Planner will guide you through eligibility and strategies to protect your assets.",
    },
    {
        "flags": ["medicaid_likely", "has_assets"],
        "priority": 2,
        "category": "benefits",
        "question": "How can I protect assets and still qualify for Medicaid?",
        "triggers": ["medicaid", "asset", "protect", "spend down", "medicaid planning"],
        "response": "Yes, there are legal ways to protect assets and qualify for Medicaid:\n\n**Strategies:**\n- **Spousal protections** — Healthy spouse can keep home, car, ~$150,000+ in assets\n- **Irrevocable trusts** — Must be set up 5 years before applying (look-back period)\n- **Caregiver child exemption** — Transfer home to child who provided care 2+ years\n- **Medicaid Annuities** — Convert countable assets to income stream\n- **Spend-down** — Pay off debts, home improvements, prepay funeral\n\n**Important considerations:**\n- 5-year look-back period for asset transfers\n- Penalties for improper transfers\n- State-specific rules vary significantly\n- Timing is critical\n\n**Critical:** These require expert guidance. Improper transfers can cause penalties and delay Medicaid eligibility.\n\nPlan for My Advisor can connect you with elder law specialists who understand your state's rules.",
    },
    # COST & AFFORDABILITY FLAGS (Priority 2)
    {
        "flags": ["financial_gap", "cost_concern"],
        "priority": 2,
        "category": "cost",
        "question": "How can I afford care for my loved one?",
        "triggers": ["afford", "pay for", "budget", "how to pay", "can i afford", "funding"],
        "response": 'We understand care costs can feel overwhelming, but there are ways to make it work:\n\n**Funding sources:**\n- **VA Benefits**: Aid & Attendance for eligible veterans (up to $2,431/month)\n- **Medicaid**: Covers long-term care if you qualify\n- **Long-term care insurance**: Check your policy for coverage\n- **Home equity**: Reverse mortgage, home equity loan, or home sale\n- **Life insurance**: Some policies have accelerated death benefits or can be sold\n- **Retirement accounts**: 401(k) or IRA withdrawals\n- **Family support**: Combine family care with paid help\n\n**Strategies to reduce costs:**\n- Start with fewer hours and increase as needed\n- Share caregivers with other families\n- Use adult day programs instead of full-day care\n- Combine family caregiving with professional help\n\n**Financial planning:**\n- Create a monthly care budget\n- Project costs over 3-5 years ("runway")\n- Apply for benefits early (processing takes time)\n- Consider tax deductions for medical expenses\n\nThe **Cost Planner\'s financial modules** will help you identify eligible funding sources and create a budget.',
    },
    {
        "flags": ["is_home_owner", "financial_gap"],
        "priority": 2,
        "category": "cost",
        "question": "Should I use home equity to pay for care?",
        "triggers": ["home equity", "reverse mortgage", "sell home", "home sale", "house equity"],
        "response": "Home equity can fund care, but consider carefully:\n\n**Options:**\n- **Sell the home** — Full proceeds available immediately (minus selling costs)\n- **Reverse mortgage** — Monthly payments or line of credit, keep ownership\n- **Home equity loan** — Lump sum, requires monthly payments (may not fit fixed income)\n- **Home equity line of credit (HELOC)** — Flexibility, requires monthly payments\n\n**Questions to ask:**\n- Will your loved one return home?\n- Is there a healthy spouse still living there?\n- Do you want to preserve it for heirs?\n- What's the Medicaid impact? (Home may be exempt asset)\n- What are the tax implications?\n\n**Reverse mortgage details:**\n- Available to homeowners 62+\n- No monthly payments required\n- Loan repaid when home is sold or owner passes\n- Can fund care while preserving Medicaid eligibility (in some cases)\n\n**Important:** This decision affects Medicaid planning, inheritance, and long-term options. Consult with a **Plan for My Advisor** expert and consider elder law guidance.",
    },
    # ASSISTED LIVING FLAGS (Priority 3)
    {
        "flags": ["assisted_living_recommended", "assisted_living"],
        "priority": 3,
        "category": "care",
        "question": "What is assisted living and how much does it cost?",
        "triggers": ["assisted living", "assisted care", "assisted living cost"],
        "response": "Assisted living offers 24/7 support in a community setting for those needing help with daily activities.\n\n**Average costs:**\n- National average: $5,500/month\n- Geographic range: $3,500–$8,000/month\n- Additional care services: +$500–$2,000/month\n\n**What's included:**\n- Private or shared apartment\n- Three meals daily and snacks\n- Housekeeping and laundry\n- Personal care assistance (bathing, dressing, medication reminders)\n- Social activities and transportation\n- 24/7 staff availability\n\n**What costs extra:**\n- Higher levels of care\n- Medication management\n- Specialized therapies\n- Beauty salon services\n\n**When is assisted living appropriate?**\n- Needs help with 2+ daily activities (ADLs)\n- Social isolation at home\n- Home safety concerns\n- Family caregiver burnout\n\nEnter your ZIP code in the **Cost Planner** to get local estimates and compare facilities.",
    },
    # SKILLED NURSING FLAGS (Priority 3)
    {
        "flags": ["skilled_nursing_recommended", "high_medical_needs"],
        "priority": 3,
        "category": "care",
        "question": "What is skilled nursing care and when is it needed?",
        "triggers": ["skilled nursing", "nursing home", "nursing facility", "snf"],
        "response": "Skilled nursing facilities provide 24/7 medical care for those with complex health needs.\n\n**Average costs:**\n- Semi-private room: $8,000–$9,500/month\n- Private room: $9,000–$12,000/month\n- Geographic variation: $6,000–$15,000/month\n\n**Services include:**\n- 24/7 licensed nursing care\n- Medical monitoring and treatments\n- Rehabilitation services (PT, OT, speech therapy)\n- Medication management\n- Personal care and meals\n- Wound care, IV therapy, feeding tubes\n\n**When is skilled nursing needed?**\n- Post-hospital recovery requiring skilled care\n- Complex medical conditions (tracheostomy, ventilator)\n- Advanced dementia with medical complications\n- End-stage illness requiring palliative care\n- Multiple chronic conditions requiring constant monitoring\n\n**Medicare coverage:**\n- Up to 100 days post-hospitalization (first 20 days fully covered)\n- Must have 3+ day hospital stay first\n- Only covers skilled nursing, not custodial care\n\nUse the **Cost Planner** to get local pricing and explore funding options like Medicaid or long-term care insurance.",
    },
    # HOSPICE/PALLIATIVE FLAGS (Priority 2)
    {
        "flags": ["end_of_life", "hospice_appropriate", "palliative_care"],
        "priority": 2,
        "category": "care",
        "question": "What is hospice care and is it covered by Medicare?",
        "triggers": ["hospice", "palliative care", "end of life care", "comfort care"],
        "response": "Hospice and palliative care focus on comfort and quality of life for those with serious illnesses.\n\n**Hospice care:**\n- For those with life expectancy of 6 months or less\n- Focuses on comfort, not cure\n- Usually covered by Medicare, Medicaid, or insurance\n- Can be provided at home, facility, or hospital\n\n**What Medicare hospice covers:**\n- Nursing care and doctor visits\n- Medical equipment and supplies\n- Medications for symptom control\n- Physical, occupational, and speech therapy\n- Social worker and counseling services\n- Short-term respite care for family caregivers\n- Grief counseling for family\n\n**Cost:**\n- Medicare covers ~95% of hospice costs\n- Small copays for medications ($5) and respite care\n- No copays for most services\n\n**Palliative care:**\n- Can be provided alongside curative treatment\n- Focuses on symptom management and quality of life\n- Cost: $500–$2,000/month for non-Medicare-covered services\n- Medicare may cover some palliative services\n\n**Important:** Hospice doesn't mean giving up hope—it means prioritizing comfort and quality time with loved ones.\n\nUse the **Cost Planner** to explore coverage and start with the **Guided Care Plan** to assess needs.",
    },
    # INSURANCE FLAGS (Priority 3)
    {
        "flags": ["has_ltc_insurance"],
        "priority": 3,
        "category": "benefits",
        "question": "How does my long-term care insurance work?",
        "triggers": [
            "long term care insurance",
            "ltc insurance",
            "insurance for care",
            "ltc policy",
        ],
        "response": "Long-term care insurance can help cover costs for home care, assisted living, or nursing homes. Coverage depends on your policy:\n\n**Common policy features:**\n- **Daily benefit**: Typically $100–$300/day\n- **Waiting period**: Often 90 days before benefits start (you pay out-of-pocket first)\n- **Benefit period**: 2–5 years of coverage (some unlimited)\n- **Inflation protection**: Benefit amount increases over time\n\n**What's typically covered:**\n- In-home care (most policies)\n- Assisted living\n- Memory care\n- Skilled nursing\n- Adult day care\n\n**What's usually NOT covered:**\n- Care provided by family members\n- Services during waiting period\n- Pre-existing conditions (sometimes)\n\n**Action steps:**\n1. Review your policy document carefully\n2. Understand your daily benefit and waiting period\n3. Check if provider needs to be approved\n4. File claim early (waiting period starts when claim is filed)\n5. Keep detailed records of care expenses\n\nReview your policy details and use the **Cost Planner** to see how insurance fits into your budget.",
    },
    # GENERAL PLANNING (Priority 3)
    {
        "flags": [],
        "priority": 3,
        "category": "planning",
        "question": "How do I talk to my family about care planning?",
        "triggers": ["talk to", "family", "conversation", "family meeting", "discuss care"],
        "response": 'Having the care conversation with family can be difficult. Here\'s how:\n\n**Preparation tips:**\n- Start early before a crisis\n- Focus on safety and quality of life, not "giving up independence"\n- Share specific concerns (falls, medications, isolation)\n- Come with objective data (care plan results, costs, options)\n\n**Conversation structure:**\n1. **Express concern with love** — "I\'m worried about your safety and want to help"\n2. **Share specific observations** — "I\'ve noticed you\'ve fallen twice this month"\n3. **Present options, not ultimatums** — "Let\'s look at a few ways to keep you safe"\n4. **Include the person receiving care** — Honor their preferences and dignity\n5. **Focus on maintaining independence** — "This will help you stay in control"\n\n**Bring data:**\n- Guided Care Plan assessment results\n- Cost Planner estimates\n- Doctor\'s recommendations\n- Options that match their preferences\n\n**Common resistance:**\n- "I\'m fine" → Acknowledge feelings, share specific concerns\n- "Too expensive" → Show funding options (VA, Medicaid, etc.)\n- "I don\'t want to be a burden" → Emphasize family wants to help\n\n**Remember:** This is a process, not a one-time talk. Be patient and revisit the conversation as needs change.\n\nThe Guided Care Plan and Cost Planner give you objective information to frame the conversation.',
    },
]


# ==============================================================================
# DYNAMIC QUESTION SELECTION ENGINE
# ==============================================================================


def _get_active_flags() -> set[str]:
    """Extract all active care and cost flags from session state.

    Returns:
        Set of flag strings (e.g., {'fall_risk', 'veteran_eligible', 'cog_moderate'})
    """
    active_flags: set[str] = set()

    # Get GCP handoff flags
    handoff = st.session_state.get("handoff", {})
    gcp_state = handoff.get("gcp", {})
    gcp_flags = gcp_state.get("flags", {})

    # Add all TRUE GCP flags
    for flag_name, flag_value in gcp_flags.items():
        if flag_value:
            active_flags.add(flag_name)

    # Get GCP care recommendation and derive flags
    care_recommendation = gcp_state.get("recommendation", "")
    if care_recommendation:
        rec_lower = care_recommendation.lower()
        if "in-home" in rec_lower or "in_home" in rec_lower:
            active_flags.add("in_home_care")
            active_flags.add("home_care_recommended")
        if "assisted living" in rec_lower:
            active_flags.add("assisted_living")
            active_flags.add("assisted_living_recommended")
        if "memory care" in rec_lower:
            active_flags.add("memory_care")
            active_flags.add("dementia_care")
        if "skilled nursing" in rec_lower:
            active_flags.add("skilled_nursing_recommended")
            active_flags.add("high_medical_needs")

    # Get Cost Planner state
    cost_data = st.session_state.get("cost_data", {})

    # Veteran status
    is_veteran = cost_data.get("is_veteran", False)
    if is_veteran:
        active_flags.add("is_veteran")
        active_flags.add("veteran_eligible")

    # Home ownership
    is_home_owner = cost_data.get("is_home_owner", False)
    if is_home_owner:
        active_flags.add("is_home_owner")
        active_flags.add("aging_in_place")

    # Medicaid status
    has_medicaid = cost_data.get("has_medicaid", False)
    medicaid_likely = cost_data.get("medicaid_likely", False)
    if has_medicaid or medicaid_likely:
        active_flags.add("has_medicaid")
        active_flags.add("medicaid_likely")

    # Long-term care insurance
    has_ltc_insurance = cost_data.get("has_ltc_insurance", False)
    if has_ltc_insurance:
        active_flags.add("has_ltc_insurance")

    # Financial gap detection
    monthly_income = cost_data.get("monthly_income", 0)
    estimated_cost = cost_data.get("estimated_monthly_cost", 0)
    if estimated_cost > 0 and monthly_income > 0:
        if monthly_income < estimated_cost:
            active_flags.add("financial_gap")
            active_flags.add("cost_concern")

    # Assets
    total_assets = cost_data.get("total_assets", 0)
    if total_assets > 50000:
        active_flags.add("has_assets")

    return active_flags


def _build_suggested_questions(
    active_flags: set[str], asked_questions: list[str]
) -> list[dict[str, Any]]:
    """Build pool of relevant questions based on active flags.

    Args:
        active_flags: Set of active flag strings from user's context
        asked_questions: List of question text strings already asked

    Returns:
        List of question dicts, sorted by relevance (priority + flag matches)
    """
    scored_questions = []

    for q in QUESTION_DATABASE:
        # Skip if already asked
        if q["question"] in asked_questions:
            continue

        # Calculate relevance score
        question_flags = set(q["flags"])

        # If question has no flags, it's a default question (always available)
        if not question_flags:
            # Base score for default questions
            score = 100 - q["priority"] * 10
        else:
            # Score based on flag matches
            matches = len(active_flags & question_flags)
            if matches == 0:
                # No flag match, skip this question
                continue

            # Higher priority = higher score (priority 1 is most urgent)
            priority_boost = (4 - q["priority"]) * 20  # Priority 1 = 60, 2 = 40, 3 = 20
            match_boost = matches * 15  # Each matched flag adds 15 points

            score = priority_boost + match_boost

        scored_questions.append(
            {
                "question": q,
                "score": score,
                "matches": len(active_flags & question_flags) if question_flags else 0,
            }
        )

    # Sort by score (highest first)
    scored_questions.sort(key=lambda x: x["score"], reverse=True)

    # Return question objects
    return [sq["question"] for sq in scored_questions]


def _get_top_3_suggestions() -> list[str]:
    """Get 3 best questions to display right now.

    Returns:
        List of 3 question text strings
    """
    asked = st.session_state.get("ai_asked_questions", [])
    active_flags = _get_active_flags()

    # Build pool of relevant questions
    question_pool = _build_suggested_questions(active_flags, asked)

    # If we have fewer than 3 questions, reset asked history (except most recent 3)
    if len(question_pool) < 3:
        st.session_state["ai_asked_questions"] = asked[-3:] if len(asked) > 3 else []
        question_pool = _build_suggested_questions(
            active_flags, st.session_state["ai_asked_questions"]
        )

    # Take top 3 from sorted, relevant questions
    top_questions = question_pool[:3]

    # If still not enough, add default questions
    if len(top_questions) < 3:
        default_questions = [q for q in QUESTION_DATABASE if not q["flags"]]
        for dq in default_questions:
            if dq["question"] not in [tq["question"] for tq in top_questions]:
                top_questions.append(dq)
            if len(top_questions) >= 3:
                break

    return [q["question"] for q in top_questions[:3]]


def _get_navi_response(question_text: str) -> str:
    """Generate Navi's response to a question.

    Uses the question database to match questions by exact text or triggers.

    Args:
        question_text: User's question string

    Returns:
        Response text from database or fallback response
    """
    q_lower = question_text.lower()

    # Try exact match first
    for q in QUESTION_DATABASE:
        if q["question"].lower() == q_lower:
            return q["answer"]

    # Try trigger matching
    for q in QUESTION_DATABASE:
        for trigger in q["triggers"]:
            if trigger.lower() in q_lower:
                return q["answer"]

    # Legacy fallback for unmatched questions
    return _get_legacy_response(question_text)


def _get_legacy_response(question: str) -> str:
    """Legacy fallback responses for questions not yet in database.

    TODO: Eventually migrate all of these into the main QUESTION_DATABASE.
    """
    q = question.lower()

    # Urgency/warning signs
    if "urgent" in q or "warning sign" in q or "need care now" in q:
        return (
            "**Urgent warning signs requiring immediate action:**\n"
            "🚨 Falls or near-falls becoming frequent\n"
            "🚨 Forgetting medications or taking incorrectly\n"
            "🚨 Weight loss, poor nutrition\n"
            "🚨 Unable to manage personal hygiene\n"
            "🚨 Wandering or getting lost\n"
            "🚨 Burns from cooking/smoking\n"
            "🚨 Signs of self-neglect\n\n"
            "If you see these, don't wait. Contact your doctor and consider emergency respite care while you set up a longer-term plan."
        )

    # Default response
    return (
        "That's a thoughtful question. Here's what I'd consider:\n\n"
        "Care planning involves balancing safety, quality of life, and affordability. "
        "The best approach depends on your specific situation — care needs, budget, family support, and personal preferences.\n\n"
        "**I can help with:**\n"
        "- Care costs and funding options\n"
        "- VA and Medicaid benefits\n"
        "- When different care levels are appropriate\n"
        "- Next steps in your planning process\n\n"
        "Try asking something more specific, or click one of the suggested questions above!"
    )


# ==============================================================================
# UX ENHANCEMENT HELPERS
# ==============================================================================
def fmt_date(iso: str) -> str | None:
    """Format ISO date string to 'MMM YYYY' for display.
    
    Args:
        iso: ISO 8601 date string (e.g., "2024-10-25T12:00:00Z")
        
    Returns:
        Formatted date string (e.g., "Oct 2024") or None if parsing fails
    """
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(iso.replace("Z", ""))
        return dt.strftime("%b %Y")
    except Exception:
        return None


def _copy_button(text: str, key: str) -> None:
    """Render a copy-to-clipboard button with JS."""
    safe_text = html.escape(text).replace("'", "\\'").replace("\n", "\\n")
    st.markdown(f"""
    <button id="copy_{key}" style="
        width: 100%;
        background: #ffffff;
        border: 1px solid rgba(59,130,246,.25);
        border-radius: 999px;
        padding: 10px 18px;
        font-size: 0.95rem;
        font-weight: 600;
        color: #1f3b7a;
        cursor: pointer;
        margin-top: 4px;
        box-shadow: 0 10px 24px rgba(15,23,42,.08);
        transition: all .18s ease;
    " onclick="
        navigator.clipboard.writeText('{safe_text}');
        this.textContent = '✓ Copied!';
        setTimeout(() => this.textContent = '📋 Copy answer', 1500);
    ">📋 Copy answer</button>
    """, unsafe_allow_html=True)


def _get_follow_up_chips(used_ids: set[str], faqs: list[dict], max_chips: int = 3) -> list[dict]:
    """Get follow-up FAQ suggestions based on shared tags with used sources.
    
    Args:
        used_ids: Set of FAQ IDs used in the current answer
        faqs: Full FAQ corpus
        max_chips: Maximum number of chips to return
        
    Returns:
        List of FAQ dicts for follow-up chips
    """
    # Get source items and collect tags
    source_items = [f for f in faqs if f["id"] in used_ids]
    tag_pool = {t for f in source_items for t in f.get("tags", [])}
    
    if not tag_pool:
        return []
    
    # Find FAQs sharing tags (exclude already used)
    candidates = [
        f for f in faqs
        if any(t in tag_pool for t in f.get("tags", []))
        and f["id"] not in used_ids
    ]
    
    # Prioritize by priority field, then limit
    candidates.sort(key=lambda x: x.get("priority", 5), reverse=True)
    return candidates[:max_chips]


# ==============================================================================
# PAGE RENDER
# ==============================================================================


def render():
    """Render AI Advisor FAQ page with modern chat interface."""
    
    # ─── Preload from Query Params (?q=) ───
    qp = st.query_params
    if qp.get("q") and not st.session_state.get("faq_chat"):
        st.session_state["faq_composer"] = qp["q"]
        st.session_state["faq_send_now"] = True
    
    # CSS Styling
    st.markdown("""
    <style>
      /* Hide custom navigation header on AI Advisor page (keep Streamlit controls) */
      .sn-header {
        display: none !important;
      }
      
      /* Remove default Streamlit spacing */
      .main .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: 100% !important;
      }
      .main > div:first-child {
        gap: 0 !important;
      }
      
      .faq-shell-sentinel + div[data-testid="stElementContainer"] > div[data-testid="stVerticalBlock"]{
        min-height:100vh;
        padding:12px 0 72px;
        background:radial-gradient(circle at 10% -20%,#eef3ff 0%,#ffffff 58%);
      }
      .faq-layout-sentinel + div[data-testid="stElementContainer"] > div[data-testid="stHorizontalBlock"]{
        max-width:1080px;
        margin:0 auto;
        padding:0 24px;
        display:flex;
        flex-direction:column;
        gap:28px;
        width:100%;
      }
      .faq-header{background:#ffffff;border-radius:26px;padding:32px 40px;border:1px solid rgba(15,23,42,.06);box-shadow:0 30px 60px rgba(15,23,42,.12);} 
      .faq-header__eyebrow{font-size:0.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#1d4ed8;margin-bottom:12px;} 
      .faq-header__title{margin:0;font-size:2.6rem;line-height:1.1;color:#0f172a;letter-spacing:-.015em;} 
      .faq-header__lead{margin:14px 0 0;font-size:1.05rem;color:#475569;max-width:60ch;}

      /* AI Advisor layout spacing */
      .ai-rec-wrapper { margin-top: 6px; margin-bottom: 10px; }
      .ai-chip-row { margin-top: 8px; margin-bottom: 14px; }
      .ai-input-wrap { margin-top: 12px; margin-bottom: 20px; }

      .faq-recs{background:#ffffff;border-radius:22px;padding:22px 26px;border:1px solid rgba(15,23,42,.06);box-shadow:0 24px 44px rgba(15,23,42,.08);} 
      .faq-recs__label{display:flex;align-items:center;gap:10px;font-weight:700;color:#1f3b7a;font-size:0.85rem;text-transform:uppercase;letter-spacing:.12em;margin-bottom:16px;} 
      .faq-recs__label::before{content:"⭐";font-size:1rem;} 

      .faq-shell div[data-testid="stButton"] > button{border-radius:999px;border:1px solid rgba(15,23,42,.08);padding:12px 20px;background:#f8fafc;color:#0f172a;font-weight:600;font-size:0.95rem;transition:all .18s ease;} 
      .faq-shell div[data-testid="stButton"] > button:hover{border-color:#93abff;background:#eef3ff;color:#0f172a;box-shadow:0 14px 30px rgba(59,130,246,.18);} 
      .faq-shell div[data-testid="stButton"] > button[kind="primary"]{background:#0f1b58;color:#fff;border-color:#0f1b58;box-shadow:0 18px 34px rgba(15,27,88,.32);} 
      .faq-shell div[data-testid="stButton"] > button[kind="primary"]:hover{background:#16257a;border-color:#16257a;}

      .chat-thread{display:flex;flex-direction:column;gap:26px;} 
      .chat-message{display:flex;gap:18px;align-items:flex-start;} 
      .chat-message--assistant{flex-direction:row;} 
      .chat-message--user{flex-direction:row-reverse;} 
      .chat-avatar{width:44px;height:44px;border-radius:16px;background:linear-gradient(135deg,#1d4ed8,#312e81);display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;box-shadow:0 16px 32px rgba(49,46,129,.25);} 
      .chat-avatar--user{background:#0f172a;} 
      .chat-bubble{flex:1;padding:24px;border-radius:24px;border:1px solid rgba(148,163,184,.35);background:#ffffff;box-shadow:0 24px 46px rgba(15,23,42,.12);color:#0f172a;font-size:1.02rem;line-height:1.6;} 
      .chat-bubble--assistant{background:linear-gradient(180deg,#ffffff 0%,#f5f7ff 94%);border-color:rgba(59,130,246,.2);} 
      .chat-bubble--user{background:#0f172a;border-color:#0f172a;color:#ffffff;box-shadow:0 24px 46px rgba(15,23,42,.35);} 
      .chat-bubble p{margin:0 0 16px;} 
      .chat-bubble p:last-child{margin-bottom:0;} 
      .chat-bubble__content{display:block;color:inherit;} 

      .chat-badge{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;margin-bottom:18px;border-radius:999px;background:#e7f1ff;border:1px solid rgba(37,99,235,.32);font-size:0.82rem;font-weight:700;color:#1d3b8b;text-transform:uppercase;letter-spacing:.08em;} 
      .chat-sources{margin-top:20px;display:flex;flex-wrap:wrap;gap:10px;} 
      .chat-source-pill{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:#eef3ff;border:1px solid rgba(59,130,246,.18);color:#1f3b7a;font-size:0.85rem;font-weight:600;text-decoration:none;} 

      .chat-follow-ups__label{font-size:0.9rem;color:#1d3b8b;font-weight:700;margin-bottom:12px;} 

      .chat-divider{height:1px;background:linear-gradient(90deg,rgba(148,163,184,.2) 0%,rgba(148,163,184,0) 100%);margin:32px 0;} 

      .faq-shell .stAlert{border-radius:20px;border:1px solid rgba(59,130,246,.18);background:#f5f7ff;box-shadow:none;} 
      .chat-sentinel{display:block;height:0;margin:0;padding:0;} 

      .chat-action-sentinel + div[data-testid="stElementContainer"] > div[data-testid="stVerticalBlock"]{
        background:#ffffff;
        border-radius:18px;
        border:1px solid rgba(148,163,184,.25);
        box-shadow:0 18px 36px rgba(15,23,42,.12);
        padding:16px 18px;
        margin-top:20px;
      }
      .chat-action-sentinel + div[data-testid="stElementContainer"] div[data-testid="stHorizontalBlock"]{gap:12px;}
      .chat-action-sentinel + div[data-testid="stElementContainer"] div[data-testid="column"]{padding:0!important;}
      .chat-action-sentinel + div[data-testid="stElementContainer"] button{width:100%;border-radius:999px;font-weight:600;}

      .chat-followup-sentinel + div[data-testid="stElementContainer"] > div[data-testid="stVerticalBlock"]{
        background:#f0f4ff;
        border-radius:18px;
        border:1px solid rgba(59,130,246,.18);
        padding:18px 20px;
        margin-top:18px;
      }
      .chat-followup-sentinel + div[data-testid="stElementContainer"] div[data-testid="stHorizontalBlock"]{gap:12px;}
      .chat-followup-sentinel + div[data-testid="stElementContainer"] div[data-testid="column"]{padding:0!important;}

      .chat-cta-sentinel + div[data-testid="stElementContainer"] button{
        width:100%;
        padding:14px 0;
        border-radius:14px;
        font-size:1rem;
        font-weight:700;
      }

      .composer-sentinel + div[data-testid="stElementContainer"] > div[data-testid="stVerticalBlock"]{
        background:#ffffff;
        border-radius:26px;
        border:1px solid rgba(148,163,184,.25);
        box-shadow:0 24px 50px rgba(15,23,42,.12);
        padding:26px 26px 20px;
      }
      .composer-sentinel + div[data-testid="stElementContainer"] div[data-testid="stHorizontalBlock"]{gap:16px;}
      .composer-sentinel + div[data-testid="stElementContainer"] div[data-testid="column"]{padding:0!important;}
      .composer-sentinel + div[data-testid="stElementContainer"] input{
        border-radius:16px;
        border:1px solid rgba(148,163,184,.45);
        padding:14px 18px;
        font-size:1rem;
        box-shadow:inset 0 2px 6px rgba(15,23,42,.08);
      }
      .composer-sentinel + div[data-testid="stElementContainer"] input:focus{
        border-color:#2563eb;
        outline:none;
        box-shadow:0 0 0 3px rgba(37,99,235,.2);
      }
      .composer-sentinel + div[data-testid="stElementContainer"] .composer-meta{
        display:flex;
        justify-content:space-between;
        flex-wrap:wrap;
        gap:12px;
        align-items:center;
        font-size:0.9rem;
        color:#475569;
        margin-top:12px;
      }
      .composer-sentinel + div[data-testid="stElementContainer"] .composer-meta a{
        color:#1f3b7a;
        font-weight:600;
        text-decoration:none;
      }

      .control-sentinel + div[data-testid="stElementContainer"] div[data-testid="stHorizontalBlock"]{gap:12px;}
      .control-sentinel + div[data-testid="stElementContainer"] div[data-testid="column"]{padding:0!important;}
      .control-sentinel + div[data-testid="stElementContainer"] button{width:100%;border-radius:12px;font-weight:600;}


      @media (max-width:900px){
        .faq-layout{padding:0 18px;}
        .chat-message{gap:14px;}
        .chat-bubble{padding:20px;}
        .chat-avatar{width:40px;height:40px;border-radius:14px;}
      }
      @media (max-width:640px){
        .faq-header{padding:24px;}
        .chat-message{flex-direction:column;}
        .chat-message--user{flex-direction:column;align-items:flex-end;}
        .chat-message--user .chat-avatar{margin-bottom:12px;}
      }
    </style>
    """, unsafe_allow_html=True)

    # Render page chrome
    render_header_simple(active_route="faq")

    # Initialize session state for chat
    if "faq_chat" not in st.session_state:
        st.session_state["faq_chat"] = []
    if "faq_composer" not in st.session_state:
        st.session_state["faq_composer"] = ""
    if "faq_send_now" not in st.session_state:
        st.session_state["faq_send_now"] = False
    
    # Initialize audio cache early to prevent KeyError
    if "audio_cache" not in st.session_state:
        st.session_state["audio_cache"] = {}
    
    # Clear audio config validation cache when returning to page from elsewhere
    # Track current page to detect navigation
    current_page = "faq"
    last_page = st.session_state.get("_last_visited_page")
    
    if last_page != current_page:
        # User navigated to this page from elsewhere - clear validation cache
        if "elevenlabs_config_valid" in st.session_state:
            del st.session_state["elevenlabs_config_valid"]
        if "elevenlabs_config_msg" in st.session_state:
            del st.session_state["elevenlabs_config_msg"]
    
    # Update last visited page
    st.session_state["_last_visited_page"] = current_page
    
    # Get processing state early so it can be used in UI
    is_processing = st.session_state.get("faq_processing", False)
    
    # Initialize variables that will be set in the UI and used in processing
    user_q = ""
    should_send = False
    send_clicked = False
    
    shell_container = st.container()
    with shell_container:
        st.markdown('<div class="faq-shell-sentinel"></div>', unsafe_allow_html=True)
        layout_container = st.container()
        with layout_container:
            st.markdown('<div class="faq-layout-sentinel"></div>', unsafe_allow_html=True)

            st.markdown(
                """
                <section class="faq-header">
                  <div class="faq-header__eyebrow">Concierge Care Advisors</div>
                  <h1 class="faq-header__title">Ask the AI Advisor</h1>
                  <p class="faq-header__lead">Short, on-point answers grounded in our FAQ and company knowledge.</p>
                </section>
                """,
                unsafe_allow_html=True,
            )

            # ─── Recommended Questions (3 canonical chips) ───
            recommendations = load_faq_recommended()

            # Wrap recommended section with spacing
            st.markdown('<div class="ai-rec-wrapper">', unsafe_allow_html=True)
            st.markdown('<section class="faq-recs"><div class="faq-recs__label">Recommended questions</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Wrap chips row with spacing
            st.markdown('<div class="ai-chip-row">', unsafe_allow_html=True)
            with st.container():
                cols = st.columns(len(recommendations), gap="medium")
                for i, rec in enumerate(recommendations):
                    if cols[i].button(
                        rec["label"],
                        key=f"rec_chip_{rec['id']}",
                        use_container_width=True,
                        help="Canonical answer from CCA FAQ"
                    ):
                        chat = list(st.session_state.get("faq_chat", []))
                        
                        name = st.session_state.get("ctx", {}).get("auth", {}).get("name")
                        ans = ask_direct_faq(rec["id"], name)

                        source_titles = [s["title"] for s in ans.get("sources", [])]

                        # Insert at beginning for newest-first ordering
                        msg = {
                            "role": "assistant",
                            "text": str(ans["answer"]),
                            "sources": source_titles,
                            "source_ids": [],
                            "cta": ans.get("cta") if isinstance(ans.get("cta"), dict) else None,
                            "user_query": str(rec["label"]),
                            "seed_tags": [],
                            "is_canonical": True
                        }
                        chat.insert(0, msg)
                        chat.insert(0, {"role": "user", "text": str(rec["label"])})
                        st.session_state["faq_chat"] = chat
                        st.rerun()
            st.markdown('</section></div>', unsafe_allow_html=True)
            
            # ─── Composer (moved here, under recommended questions) ───
            advisor_href = add_uid_to_href("?page=hub_lobby")
            st.markdown('<div class="ai-input-wrap">', unsafe_allow_html=True)
            st.markdown('<div class="chat-sentinel composer-sentinel"></div>', unsafe_allow_html=True)
            
            # Callback to handle Enter key in text input
            def on_input_change():
                # Only trigger send if there's actual text content
                input_text = st.session_state.get("faq_composer_input", "").strip()
                if input_text:
                    st.session_state["faq_send_now"] = True
                else:
                    # Clear the flag if input is empty
                    st.session_state["faq_send_now"] = False
            
            col1, col2 = st.columns([5, 1], gap="medium")

            with col1:
                user_q = st.text_input(
                    "Ask about planning, costs, eligibility, or our company…",
                    key="faq_composer_input",
                    placeholder="e.g., What is assisted living? Who is CCA?",
                    label_visibility="collapsed",
                    disabled=is_processing,
                    on_change=on_input_change,
                )

            with col2:
                send_clicked = st.button(
                    "Send",
                    type="primary",
                    key="faq_send_btn",
                    disabled=is_processing,
                )
            
            # Remove the JavaScript - using on_change callback instead

            st.markdown(
                f"""
                <div class=\"composer-meta\">
                  <a href=\"{advisor_href}\">Need a human advisor?</a>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Voice toggle on main screen with config validation
            if get_flag_value("FEATURE_FAQ_AUDIO") == "on":
                # Validate configuration before showing toggle
                from core.config import validate_elevenlabs_config, get_config
                
                # Cache validation result in session state to avoid repeated checks
                if "elevenlabs_config_valid" not in st.session_state:
                    is_valid, msg = validate_elevenlabs_config()
                    st.session_state["elevenlabs_config_valid"] = is_valid
                    st.session_state["elevenlabs_config_msg"] = msg
                    
                    # Debug logging
                    api_key = get_config("ELEVENLABS_API_KEY")
                    if api_key:
                        print(f"[FAQ_AUDIO] ✓ Config validation: API key present (length: {len(api_key)})")
                    else:
                        print("[FAQ_AUDIO] ❌ Config validation: API key missing")
                else:
                    is_valid = st.session_state["elevenlabs_config_valid"]
                    msg = st.session_state["elevenlabs_config_msg"]
                
                if is_valid:
                    st.toggle("🔊 Enable voice responses", key="faq_voice_enabled", value=False, help="When enabled, answers will include audio playback")
                else:
                    # Show warning if config is invalid (collapsed by default to be less intrusive)
                    with st.expander("⚠️ Audio Configuration Issue", expanded=False):
                        st.warning(msg)
                        st.caption("Audio playback requires ElevenLabs API credentials. Contact your administrator.")
                        if st.button("🔄 Retry Configuration", key="retry_audio_config"):
                            # Clear cache and retry
                            if "elevenlabs_config_valid" in st.session_state:
                                del st.session_state["elevenlabs_config_valid"]
                            if "elevenlabs_config_msg" in st.session_state:
                                del st.session_state["elevenlabs_config_msg"]
                            st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            send_now = st.session_state.pop("faq_send_now", False)
            should_send = send_clicked or send_now
            
            # Capture the CURRENT question IMMEDIATELY before any processing
            current_question = user_q.strip() if user_q else ""
            
            # Additional validation: Don't send if question is empty
            if should_send and not current_question:
                should_send = False
                # Clear any stale flags
                st.session_state["faq_send_now"] = False

            if send_now and st.session_state.get("faq_composer"):
                user_q = st.session_state["faq_composer"]
                st.session_state["faq_composer"] = ""

            st.markdown('<div class="chat-divider"></div>', unsafe_allow_html=True)

            # ─── Chat Transcript ───
            chat = st.session_state["faq_chat"]

            if not chat:
                st.info("💡 Click a recommended question above or type your own to start chatting.")
            else:
                st.markdown('<section class="chat-thread">', unsafe_allow_html=True)

                # Track if we've seen the first assistant message (for autoplay)
                first_assistant_seen = False
                
                for idx, msg in enumerate(chat):
                    role = msg["role"]
                    text = msg["text"]

                    if role == "user":
                        # Skip rendering user messages - show question in input only
                        pass
                    elif role == "typing":
                        st.markdown("*Navi is typing...*")
                    else:
                        # Assistant message - simple, clean Markdown rendering
                        
                        # Prepare clean Markdown answer (already sanitized by llm_mediator)
                        is_html = msg.get("is_html", False)
                        answer_md = _sanitize_to_md(text) if not is_html else text
                        
                        # Prepare Markdown sources
                        sources_lines = []
                        if msg.get("source_metas"):
                            for meta in msg.get("source_metas")[:4]:
                                title = meta.get("title", "Source")
                                url = meta.get("url", "")
                                if url:
                                    sources_lines.append(f"- [{title}]({url})")
                                else:
                                    sources_lines.append(f"- {title}")
                        elif msg.get("sources"):
                            for src in msg.get("sources")[:4]:
                                if isinstance(src, dict):
                                    title = src.get("title", "Source")
                                    url = src.get("url", "")
                                    if url:
                                        sources_lines.append(f"- [{title}]({url})")
                                    else:
                                        sources_lines.append(f"- {title}")
                                else:
                                    sources_lines.append(f"- {html.escape(str(src))}")
                        
                        sources_md = ""
                        if sources_lines:
                            sources_md = "\n\n**Sources:**\n" + "\n".join(sources_lines)
                        
                        # Simple container for answer
                        with st.container():
                            st.markdown(answer_md + sources_md)
                            
                            # Audio playback feature (if enabled and toggle is on)
                            # Only autoplay for the FIRST assistant message (newest)
                            if get_flag_value("FEATURE_FAQ_AUDIO") == "on" and st.session_state.get("faq_voice_enabled", False):
                                try:
                                    from shared.audio.tts_client import synthesize
                                    # Use clean text without sources for audio
                                    audio_text = _sanitize_to_md(text) if not is_html else text
                                    audio_bytes = synthesize(audio_text)
                                    
                                    if audio_bytes:
                                        # Only autoplay the first (newest) message
                                        should_autoplay = not first_assistant_seen
                                        st.audio(audio_bytes, format="audio/mp3", autoplay=should_autoplay)
                                        first_assistant_seen = True
                                        
                                        # Log audio playback
                                        from core.events import log_event
                                        log_event("faq_audio_played", {
                                            "query": msg.get("user_query", ""),
                                            "text_length": len(audio_text),
                                            "autoplay": should_autoplay
                                        })
                                    else:
                                        st.caption("⚠️ Audio unavailable")
                                except Exception as e:
                                    st.caption("⚠️ Audio unavailable")
                                    # Log error (optional - can be removed if not needed)
                                    print(f"[FAQ_AUDIO] Error in audio playback: {e}")

                        with st.container():
                            st.markdown('<div class="chat-sentinel chat-action-sentinel"></div>', unsafe_allow_html=True)
                            action_cols = st.columns([1, 1, 1, 1], gap="small")
                            with action_cols[0]:
                                # Copy button uses original text (sanitized but not HTML-escaped)
                                copy_text = _sanitize_to_md(text) if not is_html else text
                                _copy_button(copy_text, key=f"copy_{idx}")
                            with action_cols[1]:
                                share_query = msg.get("user_query", "")
                                if share_query and st.button("🔗 Share link", key=f"share_{idx}"):
                                    from urllib.parse import quote
                                    share_url = f"?q={quote(share_query)}"
                                    st.code(share_url, language="text")
                                    from core.events import log_event
                                    log_event("faq_action", {"share": True, "q": share_query})
                                    st.toast("Share this link!", icon="🔗")
                            with action_cols[2]:
                                if st.button("👍 Helpful", key=f"fb_yes_{idx}"):
                                    from core.events import log_event
                                    log_event("faq_feedback", {"helpful": True, "msg_idx": idx})
                                    st.toast("Thanks for the feedback!", icon="✅")
                            with action_cols[3]:
                                if st.button("👎 Not helpful", key=f"fb_no_{idx}"):
                                    from core.events import log_event
                                    log_event("faq_feedback", {"helpful": False, "msg_idx": idx})
                                    st.toast("Thanks — we'll improve this!", icon="📝")

                        used_ids = set(msg.get("source_ids", []))
                        if used_ids:
                            faqs = load_faq_items()
                            follow_ups = _get_follow_up_chips(used_ids, faqs, max_chips=3)

                            if follow_ups:
                                with st.container():
                                    st.markdown('<div class="chat-sentinel chat-followup-sentinel"></div>', unsafe_allow_html=True)
                                    st.markdown('<div class="chat-follow-ups__label">You can also ask</div>', unsafe_allow_html=True)
                                    fu_cols = st.columns(min(3, len(follow_ups)), gap="small")
                                    for i, fu in enumerate(follow_ups):
                                        label = fu["question"][:40] + ("..." if len(fu["question"]) > 40 else "")
                                        if fu_cols[i].button(label, key=f"fu_{idx}_{fu['id']}", use_container_width=True):
                                            st.session_state["faq_composer"] = fu["question"]
                                            st.session_state["faq_send_now"] = True
                                            from core.events import log_event
                                            log_event("faq_followup_chip", {"clicked_id": fu["id"], "from_idx": idx})
                                            st.rerun()

                        cta = msg.get("cta")
                        if cta:
                            seed_tags = list(msg.get("seed_tags", []))[:3]
                            user_q = msg.get("user_query", "")

                            with st.container():
                                st.markdown('<div class="chat-sentinel chat-cta-sentinel"></div>', unsafe_allow_html=True)
                                if st.button(
                                    cta["label"],
                                    key=f"cta_{idx}_{cta['route']}",
                                    type="secondary",
                                    use_container_width=True
                                ):
                                    from core.events import log_event
                                    log_event("faq_cta_nav", {
                                        "route": cta["route"],
                                        "tags": seed_tags,
                                        "query": user_q,
                                    })

                                    route_to(
                                        cta["route"],
                                        seed={
                                            "from_faq": True,
                                            "q": user_q,
                                            "tags": seed_tags,
                                        },
                                    )

                        if idx < len(chat) - 1:
                            st.markdown('<div class="chat-divider"></div>', unsafe_allow_html=True)

                st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)

                st.markdown('</section>', unsafe_allow_html=True)
                st.markdown(
                    """
                    <script>
                        const chatBottom = document.getElementById('chat-bottom');
                        if (chatBottom) {
                            chatBottom.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        }
                    </script>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="chat-divider"></div>', unsafe_allow_html=True)
    
    # ─── Process Question ───
    if should_send and current_question:
        q = current_question
        
        # Set processing flag (#3)
        st.session_state["faq_processing"] = True
        
        # Add user message and typing indicator (newest-first pattern)
        chat = list(st.session_state.get("faq_chat", []))
        chat.insert(0, {"role": "typing", "text": "..."})
        chat.insert(0, {"role": "user", "text": str(q)})
        st.session_state["faq_chat"] = chat
        
        with st.spinner("🤔 Thinking..."):
            # Load policy
            policy = load_faq_policy()
            
            # ─── EASTER EGG PATH ───
            # Check for easter eggs first (dev/staging only)
            egg = try_easter_egg(q)
            if egg:
                msg = {
                    "role": "assistant",
                    "text": str(egg.get("reply", "")),
                    "sources": ["🥚 Easter Egg"],
                    "source_ids": [],
                    "cta": egg.get("cta"),
                    "user_query": str(q),
                    "seed_tags": ["easter-egg"],
                    "is_easter_egg": True  # Flag for special badge
                }
                
                # Remove typing indicator and add response (newest-first pattern)
                chat = list(st.session_state.get("faq_chat", []))
                if len(chat) > 1 and chat[1].get("role") == "typing":
                    chat.pop(1)
                chat.insert(0, msg)
                st.session_state["faq_chat"] = chat
                st.session_state["faq_processing"] = False
                st.rerun()
            
            # ─── MINI-FAQ PATH (Stage 3.6) ───
            # Try curated identity answers first for instant response
            hit = try_mini_faq(q)
            if hit:
                # Direct (fast) path: no LLM needed (safe pattern)
                cta = (hit.get("ctas") or [None])[0]
                cta = cta if isinstance(cta, dict) else {}  # Ensure it's a dict
                
                msg = {
                    "role": "assistant",
                    "text": str(hit.get("a", "")),
                    "sources": ["CCA Identity (curated)"],
                    "source_ids": [],
                    "cta": cta,
                    "user_query": str(q),
                    "seed_tags": ["identity", "about"],
                    "is_mini_faq": True  # Flag for badge display (#6)
                }
                
                # Log mini-FAQ hit
                from core.events import log_event
                log_event("faq_mini", {
                    "query": q,
                    "mini_id": hit["id"],
                    "cta_route": cta.get("route") if cta else None
                })
                
                # Remove typing indicator and add response (newest-first pattern)
                chat = list(st.session_state.get("faq_chat", []))
                if len(chat) > 1 and chat[1].get("role") == "typing":
                    chat.pop(1)
                chat.insert(0, msg)
                st.session_state["faq_chat"] = chat
                st.session_state["faq_processing"] = False  # Clear processing flag
                st.rerun()
            
            # ─── ROUTING: Corp Knowledge vs FAQ ───
            # Expanded routing to catch care-related queries (not just identity)
            corp_keywords = [
                # Identity keywords (original)
                "cca", "concierge care advisors", "leadership", "team",
                "about", "founded", "business since", "history",
                "who is", "who are", "company", "organization",
                # Geographic keywords (Seattle, Washington, etc.)
                "seattle", "washington state", "pacific northwest", "wa",
                "bellevue", "tacoma", "spokane", "everett", "redmond",
                # Care type keywords (living guides)
                "senior living", "assisted living", "memory care",
                "independent living", "adult family home", "retirement community",
                # Service keywords (advisory/support)
                "how do you", "how does your", "your service", "advisory",
                "consultation", "free service", "how you help",
                # Post-move support keywords
                "after moving", "post-move", "follow-up", "adjustment",
                "transition support", "settling in",
                # Alzheimer's/dementia keywords (alz.org content)
                "alzheimer", "dementia", "memory loss", "cognitive",
                "stages of dementia", "diagnosis", "symptoms",
                "caregiver", "caregiving", "behaviors", "wandering",
                # VA benefits keywords (va.gov content)
                "va ", "veteran", "aid and attendance", "pension",
                "va benefits", "military", "service connected",
                # Legal/financial planning keywords
                "legal", "financial planning", "estate", "will",
                "power of attorney", "advance directive", "medicaid",
                "long-term care insurance", "trust"
            ]
            is_corp_query = any(kw in q.lower() for kw in corp_keywords)
            corp_hits = []
            
            print(f"[CORP_ROUTING] query='{q}' is_corp_query={is_corp_query}")
            
            if is_corp_query:
                # Try corporate knowledge first (auto-refreshes when corpus updates)
                corp_chunks = load_corp_chunks(_get_corp_chunks_mtime())
                corp_hits = retrieve_corp(q, corp_chunks, k=5)
                
                print(f"[CORP_RETRIEVAL] total_chunks={len(corp_chunks)} retrieved={len(corp_hits)}")
                if corp_hits:
                    print(f"[CORP_HITS] {[(h.get('title', '')[:50], h.get('source', '')) for h in corp_hits[:3]]}")
                
                if corp_hits:
                    from ai.llm_mediator import answer_corp
                    
                    name = st.session_state.get("ctx", {}).get("auth", {}).get("name") or policy.get("fallback_name", "the person you're helping")
                    
                    try:
                        result = answer_corp(q, name, corp_hits, policy)
                    except Exception as e:
                        # Error handling with retry (#8)
                        from core.events import log_event
                        log_event("faq_error", {
                            "query": q,
                            "error_type": type(e).__name__,
                            "error_msg": str(e),
                            "path": "corp"
                        })
                        
                        # Remove typing indicator and show error (newest-first pattern)
                        chat = list(st.session_state.get("faq_chat", []))
                        if len(chat) > 1 and chat[1].get("role") == "typing":
                            chat.pop(1)
                        
                        # Show error message with retry option
                        msg = {
                            "role": "assistant",
                            "text": "I'm sorry, I encountered an error while processing your question. Please try asking again or rephrase your question.",
                            "sources": [],
                            "source_ids": [],
                            "cta": None,
                            "user_query": str(q),
                            "seed_tags": [],
                            "is_error": True
                        }
                        chat.insert(0, msg)
                        st.session_state["faq_chat"] = chat
                        st.session_state["faq_processing"] = False
                        st.rerun()
                    
                    # Format sources with freshness (Stage 3.6)
                    # Dedupe by URL first
                    used_sources = result.get("sources", [])[:5]
                    seen_urls = set()
                    source_metas = []
                    
                    for s in used_sources:
                        url = s.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            source_metas.append({
                                "title": s.get("title", "Untitled"),
                                "url": url,
                                "last_fetched": s.get("last_fetched", "")
                            })
                    
                    # Collect tags for smart CTA chaining (from corp chunks)
                    seed_tags = []
                    for chunk in corp_hits[:3]:
                        seed_tags.extend(chunk.get("tags", []))
                    seed_tags = list(set(seed_tags))[:5]  # Dedupe and limit
                    
                    msg = {
                        "role": "assistant",
                        "text": str(result.get("answer", "")),
                        "sources": [],  # Will be rendered with metadata
                        "source_metas": source_metas,  # Metadata for rendering with freshness
                        "source_ids": [],  # Corp doesn't use FAQ IDs
                        "cta": None,  # Corp answers don't have CTAs
                        "user_query": str(q),
                        "seed_tags": seed_tags
                    }
                    
                    # Log corp query
                    from core.events import log_event
                    log_event("corp_llm", {
                        "query": q,
                        "retrieved_ids": [c.get("doc_id") or c.get("id", "unknown") for c in corp_hits],
                        "used_sources": [s.get("url", "") for s in result.get("sources", [])],
                        "name_present": bool(st.session_state.get("person_a_name")),
                    })
                    
                    # Remove typing indicator and add response (newest-first pattern)
                    chat = list(st.session_state.get("faq_chat", []))
                    if len(chat) > 1 and chat[1].get("role") == "typing":
                        chat.pop(1)
                    chat.insert(0, msg)
                    st.session_state["faq_chat"] = chat
                    st.session_state["faq_processing"] = False  # Clear processing flag
                    st.rerun()
            
            # ─── FAQ Path ───
            if not is_corp_query or not corp_hits:
                faqs = load_faq_items()
                retrieved = retrieve_faq(q, faqs, k=3)
                
                if retrieved:
                    from ai.llm_mediator import answer_faq
                    
                    name = st.session_state.get("ctx", {}).get("auth", {}).get("name") or policy.get("fallback_name", "the person you're helping")
                    
                    try:
                        result = answer_faq(q, name, retrieved, policy)
                    except Exception as e:
                        # Error handling with retry (#8)
                        from core.events import log_event
                        log_event("faq_error", {
                            "query": q,
                            "error_type": type(e).__name__,
                            "error_msg": str(e),
                            "path": "faq"
                        })
                        
                        # Remove typing indicator and show error (newest-first pattern)
                        chat = list(st.session_state.get("faq_chat", []))
                        if len(chat) > 1 and chat[1].get("role") == "typing":
                            chat.pop(1)
                        
                        # Show error message with retry option
                        msg = {
                            "role": "assistant",
                            "text": "I'm sorry, I encountered an error while processing your question. Please try asking again or rephrase your question.",
                            "sources": [],
                            "source_ids": [],
                            "cta": None,
                            "user_query": str(q),
                            "seed_tags": [],
                            "is_error": True
                        }
                        chat.insert(0, msg)
                        st.session_state["faq_chat"] = chat
                        st.session_state["faq_processing"] = False
                        st.rerun()
                    
                    # Map source IDs to FAQ questions for display
                    used_ids = set(result.get("sources", []))
                    source_titles = [
                        f["question"][:50] + ("..." if len(f["question"]) > 50 else "")
                        for f in retrieved if f["id"] in used_ids
                    ]
                    
                    # Collect tags for smart CTA chaining and follow-ups
                    seed_tags = []
                    for f in retrieved:
                        if f["id"] in used_ids:
                            seed_tags.extend(f.get("tags", []))
                    seed_tags = list(set(seed_tags))[:5]  # Dedupe and limit
                    
                    msg = {
                        "role": "assistant",
                        "text": str(result.get("answer", "")),
                        "sources": source_titles,
                        "source_ids": list(used_ids),  # For follow-up chips
                        "cta": result.get("cta") if isinstance(result.get("cta"), dict) else None,
                        "user_query": str(q),
                        "seed_tags": seed_tags
                    }
                    
                    # Log FAQ query
                    from core.events import log_event
                    log_event("faq_llm", {
                        "query": q,
                        "retrieved_ids": [f["id"] for f in retrieved],
                        "used_sources": result.get("sources", []),
                        "cta_route": (result.get("cta") or {}).get("route"),
                        "name_present": bool(st.session_state.get("person_a_name")),
                    })
                    
                    # Remove typing indicator and add response (newest-first pattern)
                    chat = list(st.session_state.get("faq_chat", []))
                    if len(chat) > 1 and chat[1].get("role") == "typing":
                        chat.pop(1)
                    chat.insert(0, msg)
                    st.session_state["faq_chat"] = chat
                else:
                    # ─── FALLBACK: Try Corp Knowledge Before Giving Up ───
                    # FAQ retrieval failed, try corp corpus as last resort
                    print(f"[FAQ_FALLBACK] No FAQ results for query: {q[:50]}")
                    
                    corp_chunks = load_corp_chunks(_get_corp_chunks_mtime())
                    corp_hits = retrieve_corp(q, corp_chunks, k=5)
                    
                    if corp_hits:
                        # Found something in corp knowledge!
                        from ai.llm_mediator import answer_corp
                        
                        name = st.session_state.get("ctx", {}).get("auth", {}).get("name") or policy.get("fallback_name", "the person you're helping")
                        
                        try:
                            result = answer_corp(q, name, corp_hits, policy)
                            
                            # Format sources with freshness
                            used_sources = result.get("sources", [])[:5]
                            seen_urls = set()
                            source_metas = []
                            
                            for s in used_sources:
                                url = s.get("url", "")
                                if url and url not in seen_urls:
                                    seen_urls.add(url)
                                    source_metas.append({
                                        "title": s.get("title", "Untitled"),
                                        "url": url,
                                        "last_fetched": s.get("last_fetched", "")
                                    })
                            
                            # Prefix answer to indicate it's from guide (not FAQ)
                            answer_text = result.get("answer", "")
                            if not answer_text.startswith("Based on"):
                                answer_text = f"Based on our guides: {answer_text}"
                            
                            msg = {
                                "role": "assistant",
                                "text": answer_text,
                                "sources": [],
                                "source_metas": source_metas,
                                "source_ids": [],
                                "cta": None,
                                "user_query": str(q),
                                "seed_tags": [],
                                "is_fallback": True  # Flag for UI badge
                            }
                            
                            # Log corp fallback
                            from core.events import log_event
                            log_event("corp_fallback", {
                                "query": q,
                                "retrieved_ids": [c["doc_id"] for c in corp_hits],
                                "used_sources": [s.get("url", "") for s in result.get("sources", [])],
                                "name_present": bool(st.session_state.get("person_a_name")),
                            })
                            
                            # Remove typing indicator and add response
                            chat = list(st.session_state.get("faq_chat", []))
                            if len(chat) > 1 and chat[1].get("role") == "typing":
                                chat.pop(1)
                            chat.insert(0, msg)
                            st.session_state["faq_chat"] = chat
                            st.session_state["faq_processing"] = False
                            st.rerun()
                            
                        except Exception as e:
                            print(f"[CORP_FALLBACK_ERROR] {e}")
                            # Fall through to final fallback below
                    
                    # ─── FINAL FALLBACK: No Results Anywhere ───
                    # Only bail if BOTH FAQ and corp failed
                    msg = {
                        "role": "assistant",
                        "text": "We don't have that in our FAQ yet. You can start the Guided Care Plan to get a tailored next step.",
                        "sources": [],
                        "source_ids": [],
                        "cta": {"label": "Open Guided Care Plan", "route": "gcp_intro"},
                        "user_query": str(q),
                        "seed_tags": []
                    }
                    
                    # Log no-result query
                    from core.events import log_event
                    log_event("faq_no_result", {
                        "query": q,
                        "retrieved_ids": [],
                        "used_sources": [],
                        "cta_route": "gcp_intro",
                        "name_present": bool(st.session_state.get("person_a_name")),
                    })
                    
                    # Remove typing indicator and add response (newest-first pattern)
                    chat = list(st.session_state.get("faq_chat", []))
                    if len(chat) > 1 and chat[1].get("role") == "typing":
                        chat.pop(1)
                    chat.insert(0, msg)
                    st.session_state["faq_chat"] = chat
                    
                st.session_state["faq_processing"] = False  # Clear processing flag
                st.rerun()
    
    # ─── Controls ───
    with st.container():
        st.markdown('<div class="chat-sentinel control-sentinel"></div>', unsafe_allow_html=True)
        col_clear, col_back = st.columns([1, 1], gap="small")

        with col_clear:
            if st.button("🧹 Clear chat", key="clear_chat_btn", help="Reset conversation"):
                st.session_state["faq_chat"] = []
                st.rerun()

        with col_back:
            if st.button("← Back to Lobby", key="back_to_lobby_btn", use_container_width=True):
                back_to_lobby()
    
    render_footer_simple()


def _ask_question(question: str):
    """Process a question - add to thread, mark as asked, get response."""
    # Add to thread
    st.session_state["ai_thread"].append(("user", question))
    st.session_state["ai_thread"].append(("assistant", _get_navi_response(question)))

    # Add to asked questions (for filtering suggestions)
    st.session_state["ai_asked_questions"].append(question)


def _get_suggested_questions_pool() -> list:
    """Generate pool of suggested questions based on user context and flags.

    Uses NaviOrchestrator for centralized flag-driven question logic.
    """

    # Get centralized flags from all products/modules
    flags = get_all_flags()

    # Get completed products for context
    progress = MCIP.get_journey_progress()
    completed_products = progress.get("completed_products", [])

    # Use NaviOrchestrator for centralized question generation
    questions = NaviOrchestrator.get_suggested_questions(flags, completed_products)

    # Filter out already asked questions
    asked = set(st.session_state.get("ai_asked_questions", []))
    available = [q for q in questions if q not in asked]

    # If we've asked everything, reset and show all again
    if len(available) < 3:
        available = questions

    return available
