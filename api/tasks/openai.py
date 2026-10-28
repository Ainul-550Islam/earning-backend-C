"""
api/tasks/openai.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenAI / LLM integration for AI-powered task features.
  • AI-generated task descriptions
  • Fraud explanation generation
  • Personalized offer recommendations (LLM-powered)
  • Auto-generate quiz questions
  • Support chatbot integration

All API calls are async via Celery to avoid blocking.
Requires: openai>=1.0.0 (pip install openai)
Set: OPENAI_API_KEY in settings/environment
"""

import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_openai_client():
    """Get the OpenAI client. Returns None if not configured."""
    try:
        from openai import OpenAI
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            logger.debug("[OPENAI] OPENAI_API_KEY not set")
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.debug("[OPENAI] openai package not installed")
        return None


def generate_task_description(
    task_name: str,
    task_type: str,
    reward_amount: str,
    max_tokens: int = 150,
) -> str:
    """
    Generate an engaging task description using GPT.
    Cached for 24h per task_name.
    """
    cache_key = f'openai_task_desc_{task_name[:50].lower().replace(" ", "_")}'
    cached    = cache.get(cache_key)
    if cached:
        return cached

    client = get_openai_client()
    if not client:
        return f"Complete this {task_type} task to earn ${reward_amount}."

    try:
        model  = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        resp   = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a CPA offer copywriter. Write engaging, clear, '
                        'brief task descriptions (max 2 sentences). Be honest and direct.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'Write a brief description for this earning task:\n'
                        f'Name: {task_name}\nType: {task_type}\n'
                        f'Reward: ${reward_amount}\n'
                        f'Keep it under 30 words, exciting but honest.'
                    ),
                },
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        description = resp.choices[0].message.content.strip()
        cache.set(cache_key, description, timeout=86400)
        return description
    except Exception as e:
        logger.error(f"[OPENAI] generate_task_description: {e}")
        return f"Complete this {task_type} task and earn ${reward_amount} instantly."


def generate_fraud_explanation(
    fraud_score: int,
    signals: Dict[str, Any],
) -> str:
    """
    Generate a human-readable fraud explanation for admin review.
    """
    client = get_openai_client()
    if not client:
        return f"Fraud score {fraud_score}/100. Signals: {signals}"

    try:
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        resp  = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a fraud analyst. Explain fraud risk signals concisely for admin review.',
                },
                {
                    'role': 'user',
                    'content': (
                        f'Fraud score: {fraud_score}/100\n'
                        f'Signals: {signals}\n'
                        f'Provide a 2-3 sentence analysis of why this account may be fraudulent.'
                    ),
                },
            ],
            max_tokens=150,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[OPENAI] generate_fraud_explanation: {e}")
        return f"Score {fraud_score}/100 — automated fraud signals detected."


def generate_quiz_questions(
    quiz_topic: str,
    num_questions: int = 5,
    options_per_question: int = 4,
) -> List[Dict]:
    """
    Generate personality quiz questions using GPT.
    Returns list of {text, options, weights} dicts.
    """
    cache_key = f'openai_quiz_{quiz_topic[:40].lower().replace(" ", "_")}_{num_questions}'
    cached    = cache.get(cache_key)
    if cached:
        return cached

    client = get_openai_client()
    if not client:
        return _default_quiz_questions(quiz_topic, num_questions)

    try:
        import json
        model  = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        resp   = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a personality quiz designer. Return ONLY valid JSON. '
                        'Create engaging, viral social media quiz questions.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'Create {num_questions} personality quiz questions for: "{quiz_topic}"\n'
                        f'Each question has exactly {options_per_question} options.\n'
                        f'Return JSON array: [{{"id":"q1","text":"...","options":["A","B","C","D"]}}]'
                    ),
                },
            ],
            max_tokens=800,
            temperature=0.8,
        )
        text      = resp.choices[0].message.content.strip()
        questions = json.loads(text)
        cache.set(cache_key, questions, timeout=86400 * 7)
        return questions
    except Exception as e:
        logger.error(f"[OPENAI] generate_quiz_questions: {e}")
        return _default_quiz_questions(quiz_topic, num_questions)


def generate_offer_recommendations(
    user_profile: Dict,
    available_offers: List[Dict],
    max_recommendations: int = 5,
) -> List[str]:
    """
    Use LLM to rank offers for a specific user profile.
    Returns list of offer_ids in recommended order.
    """
    if not available_offers:
        return []

    client = get_openai_client()
    if not client:
        return [o.get('offer_id', '') for o in available_offers[:max_recommendations]]

    try:
        import json
        model    = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        offer_summary = [
            {'id': o.get('offer_id'), 'name': o.get('name'), 'payout': str(o.get('payout', 0))}
            for o in available_offers[:20]
        ]
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a CPA offer recommendation engine. Return ONLY a JSON array of offer IDs.',
                },
                {
                    'role': 'user',
                    'content': (
                        f'User profile:\n{json.dumps(user_profile)}\n\n'
                        f'Available offers:\n{json.dumps(offer_summary)}\n\n'
                        f'Return the top {max_recommendations} offer IDs as JSON array: ["id1","id2",...]'
                    ),
                },
            ],
            max_tokens=200,
            temperature=0.3,
        )
        ids = json.loads(resp.choices[0].message.content.strip())
        return ids[:max_recommendations]
    except Exception as e:
        logger.error(f"[OPENAI] generate_offer_recommendations: {e}")
        return [o.get('offer_id', '') for o in available_offers[:max_recommendations]]


def explain_task_rejection(
    task_id: str,
    rejection_reason: str,
    user_context: Dict,
) -> str:
    """Generate a user-friendly explanation for task rejection."""
    client = get_openai_client()
    if not client:
        return f"Task was rejected: {rejection_reason}"

    try:
        model  = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        resp   = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': 'Explain task rejections in a friendly, helpful way. Max 2 sentences.',
                },
                {
                    'role': 'user',
                    'content': f'Task {task_id} was rejected. Reason: {rejection_reason}. Explain to user.',
                },
            ],
            max_tokens=100,
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"This task could not be credited. Reason: {rejection_reason}"


def _default_quiz_questions(topic: str, count: int) -> List[Dict]:
    """Fallback quiz questions when OpenAI is unavailable."""
    return [
        {
            'id':      f'q{i+1}',
            'text':    f'Question {i+1} about {topic}',
            'options': ['Option A', 'Option B', 'Option C', 'Option D'],
        }
        for i in range(count)
    ]


__all__ = [
    'get_openai_client', 'generate_task_description', 'generate_fraud_explanation',
    'generate_quiz_questions', 'generate_offer_recommendations',
    'explain_task_rejection',
]
