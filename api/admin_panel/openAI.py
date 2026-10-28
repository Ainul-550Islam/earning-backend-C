# api/admin_panel/openAI.py
"""
OpenAI Integration for admin_panel.
AI-powered admin features: auto-moderation summaries, fraud narrative,
report generation, smart search, anomaly explanation, broadcast drafting.

"Do not summarize or skip any logic. Provide the full code."
Uses: openai Python SDK — pip install openai
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ==================== OPENAI CLIENT ====================

def _get_client():
    """Get OpenAI client. Returns None if not configured."""
    try:
        import openai
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or cache.get('admin_panel:openai_key')
        if not api_key:
            return None
        return openai.OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("[OpenAI] openai package not installed. Run: pip install openai")
        return None
    except Exception as e:
        logger.error(f"[OpenAI] Client init failed: {e}")
        return None


MODEL = getattr(settings, 'OPENAI_ADMIN_MODEL', 'gpt-4o-mini')
MAX_TOKENS = 1024
CACHE_TTL = 300  # 5 minutes cache for AI responses


# ==================== CORE AI CALL ====================

def _call_openai(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = MAX_TOKENS,
    cache_key: Optional[str] = None,
) -> Optional[str]:
    """
    Core OpenAI API call with caching and error handling.
    Returns the text response or None on failure.
    """
    # Check cache
    if cache_key:
        cached = cache.get(cache_key)
        if cached:
            return cached

    client = _get_client()
    if not client:
        return None

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result = response.choices[0].message.content.strip()
        if cache_key and result:
            cache.set(cache_key, result, CACHE_TTL)
        return result
    except Exception as e:
        logger.error(f"[OpenAI] API call failed: {e}")
        return None


# ==================== ADMIN AI FEATURES ====================

def generate_fraud_explanation(
    user_id: Any,
    fraud_score: int,
    signals: List[Dict],
    ip: str = '',
) -> str:
    """
    Generate a human-readable explanation of why a user was flagged for fraud.
    Used in fraud review panel.
    """
    cache_key = f'admin_panel:openai:fraud:{user_id}:{fraud_score}'

    signals_text = '\n'.join([
        f"- {s.get('signal', 'unknown')}: score={s.get('weight', 0)}, detail={s.get('count', '')}"
        for s in signals
    ])

    system = (
        "You are an expert fraud analyst for a CPA earning platform. "
        "Explain fraud signals in plain English for admin review. "
        "Be concise, factual, and actionable. Max 3 sentences."
    )
    user = (
        f"User ID: {user_id}\n"
        f"Risk Score: {fraud_score}/100\n"
        f"IP: {ip or 'unknown'}\n"
        f"Fraud Signals:\n{signals_text}\n\n"
        f"Explain why this user is flagged and recommend action."
    )

    result = _call_openai(system, user, temperature=0.2, cache_key=cache_key)
    return result or f"Risk score {fraud_score}/100 based on {len(signals)} signals. Manual review recommended."


def draft_admin_broadcast(
    audience: str,
    topic: str,
    tone: str = 'friendly',
    language: str = 'en',
) -> Dict[str, str]:
    """
    Draft an admin broadcast message using AI.
    Returns: {title, body}
    """
    cache_key = f'admin_panel:openai:broadcast:{hash(topic+audience+language)}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    system = (
        "You are a community manager for a mobile earning app. "
        "Write clear, engaging notifications for users. "
        f"Tone: {tone}. Language: {language}. "
        "Return JSON with keys: title (max 60 chars) and body (max 200 chars)."
    )
    user = f"Write a broadcast to {audience} users about: {topic}"

    result = _call_openai(system, user, temperature=0.7, cache_key=None)
    if result:
        try:
            # Strip markdown if present
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            data = json.loads(clean)
            if 'title' in data and 'body' in data:
                cache.set(cache_key, data, CACHE_TTL)
                return data
        except Exception:
            pass
    return {
        'title': f'Important Update for {audience.title()} Users',
        'body': f'We have an important update regarding {topic}. Please check the app for details.',
    }


def generate_report_summary(
    report_type: str,
    data: Dict[str, Any],
    period: str = 'last 7 days',
) -> str:
    """
    Generate an executive summary for a data report.
    Used in admin report view.
    """
    cache_key = f'admin_panel:openai:report:{report_type}:{hash(str(data)[:200])}'

    system = (
        "You are a data analyst for a mobile CPA earning platform. "
        "Write a concise executive summary (3-5 bullets) of the provided metrics. "
        "Highlight trends, anomalies, and actionable insights. "
        "Be specific with numbers."
    )
    user = (
        f"Report Type: {report_type}\n"
        f"Period: {period}\n"
        f"Key Metrics:\n{json.dumps(data, indent=2, default=str)}\n\n"
        "Write an executive summary with bullet points."
    )

    result = _call_openai(system, user, temperature=0.3, max_tokens=512, cache_key=cache_key)
    return result or f"Report generated for {period}. Please review the data manually."


def explain_anomaly(
    metric_name: str,
    current_value: float,
    expected_value: float,
    historical_context: Dict = None,
) -> str:
    """
    Explain a detected anomaly in plain English.
    Used in AI Insights panel.
    """
    pct_change = ((current_value - expected_value) / max(abs(expected_value), 0.001)) * 100
    direction = 'increased' if pct_change > 0 else 'decreased'
    cache_key = f'admin_panel:openai:anomaly:{metric_name}:{int(pct_change)}'

    system = (
        "You are a data anomaly analyst for a CPA earning platform. "
        "Explain metric anomalies clearly and suggest possible causes. "
        "Be specific, concise (2-3 sentences), and actionable."
    )
    user = (
        f"Metric: {metric_name}\n"
        f"Current: {current_value:.2f}\n"
        f"Expected: {expected_value:.2f}\n"
        f"Change: {direction} by {abs(pct_change):.1f}%\n"
        f"Context: {json.dumps(historical_context or {}, default=str)}\n\n"
        f"Explain this anomaly and suggest possible causes."
    )

    result = _call_openai(system, user, temperature=0.3, cache_key=cache_key)
    return result or (
        f"{metric_name} has {direction} by {abs(pct_change):.1f}% "
        f"(current: {current_value:.2f}, expected: {expected_value:.2f}). "
        "Manual investigation recommended."
    )


def smart_admin_search(
    query: str,
    context: str = 'admin panel',
) -> Dict[str, Any]:
    """
    Parse natural language admin search queries.
    Returns structured filter parameters.
    E.g., "users who joined last week from Bangladesh" →
    {model: 'User', filters: {date_joined__gte: '...', country: 'BD'}}
    """
    system = (
        "You parse natural language admin search queries for a CPA earning platform. "
        "Return JSON with: model (User/Wallet/PayoutItem/Offer), "
        "filters (dict of Django ORM kwargs), order_by (field string). "
        "Be conservative — only include filters you're confident about."
    )
    user = f"Parse this search: '{query}'"

    result = _call_openai(system, user, temperature=0.1, max_tokens=256)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {'model': 'User', 'filters': {}, 'raw_query': query}


def generate_kyc_review_summary(
    user_id: Any,
    document_type: str,
    submission_data: Dict,
) -> str:
    """
    Summarise a KYC submission for admin review.
    """
    system = (
        "You are a KYC compliance officer. "
        "Summarise the KYC submission for admin review. "
        "Note any risk factors or inconsistencies. Max 3 sentences."
    )
    user = (
        f"User ID: {user_id}\n"
        f"Document: {document_type}\n"
        f"Data: {json.dumps(submission_data, default=str)}\n\n"
        "Provide a brief KYC review summary."
    )

    result = _call_openai(system, user, temperature=0.2, max_tokens=256)
    return result or f"KYC submission for User {user_id} ({document_type}) requires manual review."


def suggest_fraud_rule(
    fraud_pattern: str,
    recent_examples: List[Dict],
) -> Dict[str, Any]:
    """
    Suggest a new fraud detection rule based on observed patterns.
    Used in Fraud Control → auto-suggest rules.
    """
    system = (
        "You are a fraud engineer for a CPA earning platform. "
        "Suggest a fraud detection rule in JSON format with: "
        "name, rule_type, condition (dict), action_on_trigger, severity, weight (1-100)."
    )
    examples_text = json.dumps(recent_examples[:5], default=str, indent=2)
    user = (
        f"Fraud Pattern: {fraud_pattern}\n"
        f"Recent Examples:\n{examples_text}\n\n"
        "Suggest a fraud rule to catch this pattern."
    )

    result = _call_openai(system, user, temperature=0.2, max_tokens=400)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {
        'name': f'Auto-suggested rule: {fraud_pattern[:50]}',
        'rule_type': 'behavior',
        'severity': 'medium',
        'weight': 50,
        'action_on_trigger': 'flag',
    }


def translate_admin_content(
    text: str,
    target_language: str,
    content_type: str = 'notification',
) -> str:
    """
    Translate admin content (notifications, announcements) to another language.
    """
    lang_map = {
        'bn': 'Bengali', 'hi': 'Hindi', 'ar': 'Arabic', 'id': 'Indonesian',
        'ms': 'Malay', 'ur': 'Urdu', 'tr': 'Turkish', 'fr': 'French',
        'es': 'Spanish', 'de': 'German', 'zh': 'Chinese (Simplified)',
    }
    lang_name = lang_map.get(target_language, target_language)
    cache_key = f'admin_panel:openai:translate:{target_language}:{hash(text)}'

    system = (
        f"You are a professional translator. Translate the following {content_type} "
        f"to {lang_name}. Maintain the original tone and meaning. Return only the translation."
    )
    user = text

    result = _call_openai(system, user, temperature=0.1, cache_key=cache_key)
    return result or text


# ==================== ADMIN VIEWSET INTEGRATION ====================

class OpenAIAdminView:
    """
    ViewSet methods for OpenAI-powered admin features.
    Add to any ViewSet or use standalone.
    """

    @staticmethod
    def fraud_explain(request, user_id, fraud_score, signals, ip=''):
        """REST endpoint handler for fraud explanation."""
        from rest_framework.response import Response
        explanation = generate_fraud_explanation(user_id, fraud_score, signals, ip)
        return Response({'success': True, 'explanation': explanation, 'ai_powered': True})

    @staticmethod
    def draft_broadcast(request):
        """REST endpoint handler for broadcast drafting."""
        from rest_framework.response import Response
        audience = request.data.get('audience', 'all')
        topic    = request.data.get('topic', '')
        tone     = request.data.get('tone', 'friendly')
        language = request.data.get('language', 'en')
        if not topic:
            return Response({'error': 'topic required'}, status=400)
        draft = draft_admin_broadcast(audience, topic, tone, language)
        return Response({'success': True, 'draft': draft, 'ai_powered': True})

    @staticmethod
    def smart_search(request):
        """REST endpoint handler for NL search."""
        from rest_framework.response import Response
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'error': 'q parameter required'}, status=400)
        parsed = smart_admin_search(query)
        return Response({'success': True, 'parsed': parsed, 'ai_powered': True})

    @staticmethod
    def report_summary(request, report_type, data, period='last 7 days'):
        """REST endpoint handler for report summaries."""
        from rest_framework.response import Response
        summary = generate_report_summary(report_type, data, period)
        return Response({'success': True, 'summary': summary, 'ai_powered': True})

    @staticmethod
    def translate(request):
        """REST endpoint handler for content translation."""
        from rest_framework.response import Response
        text     = request.data.get('text', '')
        lang     = request.data.get('target_language', 'bn')
        ctype    = request.data.get('content_type', 'notification')
        if not text:
            return Response({'error': 'text required'}, status=400)
        translated = translate_admin_content(text, lang, ctype)
        return Response({'success': True, 'translated': translated, 'target_language': lang})

    @staticmethod
    def suggest_rule(request):
        """REST endpoint handler for fraud rule suggestion."""
        from rest_framework.response import Response
        pattern  = request.data.get('pattern', '')
        examples = request.data.get('examples', [])
        if not pattern:
            return Response({'error': 'pattern required'}, status=400)
        rule = suggest_fraud_rule(pattern, examples)
        return Response({'success': True, 'suggested_rule': rule, 'ai_powered': True})


# ==================== HEALTH CHECK ====================

def openai_health_check() -> Dict[str, Any]:
    """Check if OpenAI integration is configured and working."""
    client = _get_client()
    if not client:
        return {
            'status': 'unconfigured',
            'message': 'OPENAI_API_KEY not set in settings',
            'features_available': False,
        }
    try:
        # Lightweight test call
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return {
            'status': 'healthy',
            'model': MODEL,
            'features_available': True,
            'test_response': response.choices[0].message.content,
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'features_available': False,
        }


def set_api_key(api_key: str, persist: bool = False) -> None:
    """
    Set OpenAI API key at runtime (stored in cache or SystemConfig).
    """
    cache.set('admin_panel:openai_key', api_key, 86400)
    if persist:
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            SystemConfigService.set('openai_api_key', api_key, 'string', group='api')
        except Exception as e:
            logger.error(f"[OpenAI] Persist key failed: {e}")


# ===========================================================================
# MISSING FUNCTIONS — Full completion
# ===========================================================================

def analyze_user_behavior(
    user_id: Any,
    events: List[Dict],
    window_days: int = 30,
) -> Dict[str, Any]:
    """
    Analyze user behavior patterns for fraud/churn risk using AI.
    Calls api.behavior_analytics — admin_panel never stores behavior data itself.
    Returns: {pattern_summary, risk_indicators, recommendations}
    """
    cache_key = f'admin_panel:openai:behavior:{user_id}:{window_days}'

    system = (
        "You are a behavioral analytics expert for a CPA earning platform. "
        "Analyze the given user events and identify: "
        "1) Normal usage patterns "
        "2) Suspicious behaviors (bot-like activity, click fraud, unusual timing) "
        "3) Churn risk indicators "
        "Return JSON with: pattern_summary (string), risk_level (low/medium/high/critical), "
        "risk_indicators (list of strings), churn_probability (0.0-1.0), "
        "recommendations (list of strings)."
    )
    events_text = json.dumps(events[:20], default=str, indent=2)
    user_prompt = (
        f"User ID: {user_id}\n"
        f"Analysis window: last {window_days} days\n"
        f"Recent events ({len(events)} total, showing 20):\n{events_text}\n\n"
        "Analyze behavior and return JSON."
    )

    result = _call_openai(system, user_prompt, temperature=0.2, max_tokens=600, cache_key=cache_key)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {
        'pattern_summary': f'Analysis of {len(events)} events for user {user_id}',
        'risk_level': 'unknown',
        'risk_indicators': [],
        'churn_probability': 0.0,
        'recommendations': ['Manual review recommended'],
    }


def generate_offer_description(
    offer_name: str,
    category: str,
    requirements: str,
    payout: float,
    target_countries: List[str] = None,
) -> Dict[str, str]:
    """
    Auto-generate offer description for the offerwall/offer inventory.
    Returns: {title, short_description, full_description, call_to_action}
    """
    cache_key = f'admin_panel:openai:offer_desc:{hash(offer_name + category)}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    countries_text = ', '.join(target_countries[:5]) if target_countries else 'All countries'
    system = (
        "You write engaging offer descriptions for a mobile CPA earning app. "
        "Be clear, concise, and action-oriented. "
        "Return JSON with: title (max 60 chars), short_description (max 100 chars), "
        "full_description (max 300 chars), call_to_action (max 40 chars, e.g. 'Download Now')."
    )
    user_prompt = (
        f"Offer Name: {offer_name}\n"
        f"Category: {category}\n"
        f"Requirements: {requirements}\n"
        f"Payout: ${payout:.2f}\n"
        f"Countries: {countries_text}\n\n"
        "Write engaging offer copy in English."
    )

    result = _call_openai(system, user_prompt, temperature=0.6, max_tokens=400)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            data = json.loads(clean)
            cache.set(cache_key, data, CACHE_TTL * 10)
            return data
        except Exception:
            pass
    return {
        'title': offer_name,
        'short_description': f'Complete this {category} offer and earn ${payout:.2f}',
        'full_description': requirements,
        'call_to_action': 'Complete Now',
    }


def auto_moderate_content(
    content: str,
    content_type: str = 'user_submission',
) -> Dict[str, Any]:
    """
    AI-powered content moderation for admin auto_mod module.
    Returns moderation decision + reason without storing content.
    Result: {action: approve|reject|flag, confidence, reason, categories}
    """
    system = (
        "You are a content moderation AI for a CPA earning platform. "
        "Analyze the given content and decide: approve, reject, or flag for manual review. "
        "Reject for: hate speech, adult content, violence, spam, illegal activity, fraud. "
        "Flag for: borderline content, ambiguous cases. "
        "Return JSON with: action (approve/reject/flag), "
        "confidence (0.0-1.0), reason (string), categories (list of violated categories)."
    )
    user_prompt = f"Content type: {content_type}\nContent: {content[:500]}\n\nModerate this content."

    result = _call_openai(system, user_prompt, temperature=0.1, max_tokens=300)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {'action': 'flag', 'confidence': 0.5, 'reason': 'AI moderation unavailable', 'categories': []}


def generate_admin_insight(
    insight_type: str,
    data: Dict[str, Any],
    period: str = 'last 7 days',
) -> Dict[str, str]:
    """
    Generate an admin insight card (used in AdminInsight model).
    insight_type: revenue_drop | fraud_spike | churn_risk | growth_opportunity | anomaly
    Returns: {title, body, priority, action_label, action_url}
    """
    cache_key = f'admin_panel:openai:insight:{insight_type}:{hash(str(data)[:100])}'

    type_descriptions = {
        'revenue_drop':        'a significant revenue decrease that needs attention',
        'fraud_spike':         'a sudden increase in fraud activity requiring immediate action',
        'churn_risk':          'users at high risk of churning who need re-engagement',
        'growth_opportunity':  'a growth opportunity that the team should act on quickly',
        'anomaly':             'an unusual pattern detected in platform metrics',
        'payout_bottleneck':   'a bottleneck in the payout processing pipeline',
        'offer_performance':   'actionable insights about offer performance',
    }
    desc = type_descriptions.get(insight_type, 'an important platform insight')

    system = (
        "You generate concise admin insights for a CPA earning platform dashboard. "
        "Be specific with numbers, actionable, and urgent where appropriate. "
        "Return JSON with: title (max 80 chars), body (max 200 chars, 2-3 sentences), "
        "priority (critical/high/medium/low), action_label (max 30 chars), action_url (relative URL)."
    )
    user_prompt = (
        f"Insight type: {insight_type} — {desc}\n"
        f"Period: {period}\n"
        f"Data:\n{json.dumps(data, indent=2, default=str)}\n\n"
        "Generate an actionable admin insight card."
    )

    result = _call_openai(system, user_prompt, temperature=0.4, max_tokens=400, cache_key=cache_key)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            data_out = json.loads(clean)
            if 'title' in data_out and 'body' in data_out:
                return data_out
        except Exception:
            pass
    return {
        'title':        f'{insight_type.replace("_"," ").title()} Alert',
        'body':         f'Detected in period: {period}. Please review the data manually.',
        'priority':     'medium',
        'action_label': 'View Details',
        'action_url':   '/admin-panel/dashboard/',
    }


def bulk_classify_transactions(
    transactions: List[Dict],
) -> List[Dict]:
    """
    Classify a batch of transactions as legitimate/suspicious using AI.
    Processes in batches of 20. Returns transaction list with added 'ai_classification' field.
    """
    if not transactions:
        return []

    client = _get_client()
    if not client:
        return [{**t, 'ai_classification': 'unknown', 'ai_confidence': 0.0} for t in transactions]

    system = (
        "You classify financial transactions for a CPA earning platform. "
        "For each transaction, return: id, classification (legitimate/suspicious/review), "
        "confidence (0.0-1.0), reason (brief). "
        "Return a JSON array of objects."
    )
    results = []
    batch_size = 20

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        user_prompt = (
            f"Classify these {len(batch)} transactions:\n"
            f"{json.dumps(batch, default=str, indent=2)}"
        )
        try:
            raw = _call_openai(system, user_prompt, temperature=0.1, max_tokens=800)
            if raw:
                clean = raw.strip('`').replace('json\n', '').replace('```', '').strip()
                classifications = json.loads(clean)
                # Merge results back
                class_map = {str(c.get('id', '')): c for c in classifications}
                for txn in batch:
                    c = class_map.get(str(txn.get('id', txn.get('pk', ''))), {})
                    results.append({
                        **txn,
                        'ai_classification': c.get('classification', 'unknown'),
                        'ai_confidence':     c.get('confidence', 0.0),
                        'ai_reason':         c.get('reason', ''),
                    })
            else:
                results.extend([{**t, 'ai_classification': 'unknown'} for t in batch])
        except Exception as e:
            logger.error(f"[OpenAI] bulk_classify_transactions batch {i}: {e}")
            results.extend([{**t, 'ai_classification': 'unknown'} for t in batch])

    return results


def generate_withdrawal_risk_note(
    user_id: Any,
    amount: float,
    gateway: str,
    user_history: Dict,
) -> str:
    """
    Generate a risk assessment note for a withdrawal request.
    Used in payout admin panel to help reviewers make decisions.
    """
    cache_key = f'admin_panel:openai:withdrawal_risk:{user_id}:{int(amount)}'

    system = (
        "You write concise withdrawal risk assessment notes for a CPA earning platform admin. "
        "Be factual and specific. Max 2 sentences. "
        "Focus on: account age, earnings pattern, previous withdrawals, risk signals."
    )
    user_prompt = (
        f"Withdrawal Request:\n"
        f"User ID: {user_id}\n"
        f"Amount: ৳{amount:.2f}\n"
        f"Gateway: {gateway}\n"
        f"User History: {json.dumps(user_history, default=str)}\n\n"
        "Write a brief risk assessment for this withdrawal."
    )

    result = _call_openai(system, user_prompt, temperature=0.2, max_tokens=150, cache_key=cache_key)
    return result or f"User {user_id} withdrawal ৳{amount:.2f} via {gateway}. Standard review recommended."


def answer_admin_question(
    question: str,
    context: Dict = None,
) -> str:
    """
    AI assistant for admin questions about the platform.
    e.g. "Why did revenue drop yesterday?" or "Which countries have highest fraud?"
    """
    system = (
        "You are an AI assistant for the admin panel of a CPA earning platform. "
        "Answer questions about platform operations, metrics, and best practices. "
        "Be concise (max 3 sentences) and suggest actions where possible. "
        "If you need data you don't have, say so clearly."
    )
    context_text = json.dumps(context or {}, default=str)[:500] if context else ''
    user_prompt  = f"Platform context:\n{context_text}\n\nAdmin question: {question}"

    result = _call_openai(system, user_prompt, temperature=0.5, max_tokens=300)
    return result or "I need more data to answer this question. Please check the relevant dashboard section."


def summarize_kyc_document(
    document_type: str,
    extracted_text: str,
    user_submitted_info: Dict,
) -> Dict[str, Any]:
    """
    Summarize extracted text from a KYC document and flag inconsistencies.
    Returns: {summary, name_match, dob_match, inconsistencies, recommendation}
    """
    system = (
        "You review KYC documents for a mobile earning platform. "
        "Compare extracted document text against user-submitted info. "
        "Return JSON: summary (string), name_match (bool), dob_match (bool or null), "
        "inconsistencies (list of strings), recommendation (approve/reject/manual_review), "
        "confidence (0.0-1.0)."
    )
    user_prompt = (
        f"Document type: {document_type}\n"
        f"Extracted text: {extracted_text[:600]}\n"
        f"User-submitted info: {json.dumps(user_submitted_info, default=str)}\n\n"
        "Analyze and return JSON review."
    )

    result = _call_openai(system, user_prompt, temperature=0.1, max_tokens=400)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {
        'summary':           f'{document_type} document submitted',
        'name_match':        None,
        'dob_match':         None,
        'inconsistencies':   [],
        'recommendation':    'manual_review',
        'confidence':        0.0,
    }


def predict_offer_performance(
    offer_data: Dict,
    historical_similar: List[Dict] = None,
) -> Dict[str, Any]:
    """
    Predict expected performance of a new offer before approval.
    Returns: {predicted_cr, predicted_epc, predicted_daily_conversions, risk_level, notes}
    """
    cache_key = f'admin_panel:openai:offer_perf:{hash(str(offer_data))}'
    system = (
        "You predict CPA offer performance for a mobile earning platform. "
        "Based on offer details and historical similar offers, predict: "
        "conversion_rate (0.0-1.0), epc (earnings per click in USD), "
        "daily_conversions (integer estimate), risk_level (low/medium/high), "
        "notes (2-3 actionable notes). Return JSON."
    )
    hist_text = json.dumps((historical_similar or [])[:5], default=str)
    user_prompt = (
        f"New offer:\n{json.dumps(offer_data, default=str)}\n\n"
        f"Historical similar offers:\n{hist_text}\n\n"
        "Predict performance metrics."
    )

    result = _call_openai(system, user_prompt, temperature=0.3, max_tokens=400, cache_key=cache_key)
    if result:
        try:
            clean = result.strip('`').replace('json\n', '').replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            pass
    return {
        'predicted_cr':               0.05,
        'predicted_epc':              0.10,
        'predicted_daily_conversions': 50,
        'risk_level':                 'medium',
        'notes':                      ['Insufficient data for prediction. Monitor after launch.'],
    }