# earning_backend/api/notifications/openai.py
"""
OpenAI Integration — AI-powered notification content generation.

Uses OpenAI GPT to:
  1. Auto-generate notification titles and messages from event context
  2. Improve existing notification copy
  3. Generate A/B test variants automatically
  4. Translate notifications to Bangla (BN)
  5. Suggest optimal send time based on user behavior description

Settings:
    OPENAI_API_KEY          — OpenAI API key
    OPENAI_NOTIFICATION_MODEL — e.g. 'gpt-4o-mini' (default)
    OPENAI_MAX_TOKENS       — max tokens per completion (default: 300)
"""

import logging
from typing import Dict, List, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# Default model — use a fast, cheap model for notification generation
DEFAULT_MODEL = getattr(settings, 'OPENAI_NOTIFICATION_MODEL', 'gpt-4o-mini')
DEFAULT_MAX_TOKENS = getattr(settings, 'OPENAI_MAX_TOKENS', 300)


class NotificationAIGenerator:
    """
    AI-powered notification content generator using OpenAI.

    Handles:
    - Title + message generation from event context
    - Copy improvement (make it more engaging)
    - A/B variant generation
    - Bengali (BN) translation
    - Personalisation with user data
    """

    def __init__(self):
        self._client = None
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self._available = bool(api_key)
        if not self._available:
            logger.info('NotificationAIGenerator: OPENAI_API_KEY not set — AI features disabled.')

    def is_available(self) -> bool:
        return self._available

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                raise ImportError('openai package not installed. Run: pip install openai')
        return self._client

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    # ------------------------------------------------------------------
    # Core generation methods
    # ------------------------------------------------------------------

    def generate_notification(
        self,
        event_type: str,
        context: Dict,
        channel: str = 'in_app',
        language: str = 'en',
    ) -> Dict:
        """
        Generate a notification title and message for a given event.

        Args:
            event_type: e.g. 'withdrawal_completed', 'task_approved'
            context:    Event data dict, e.g. {'amount': 500, 'username': 'John'}
            channel:    'push' | 'email' | 'sms' | 'in_app'
            language:   'en' | 'bn'

        Returns:
            {'title': '...', 'message': '...'}
        """
        if not self._available:
            return self._fallback_content(event_type, context)

        lang_note = '(Write in Bangla/Bengali)' if language == 'bn' else '(Write in English)'
        channel_note = {
            'push': 'Very short push notification (title max 50 chars, message max 100 chars)',
            'sms':  'SMS: message only, max 160 characters, no markdown',
            'email': 'Email: subject (title) and body (message), can be slightly longer',
            'in_app': 'In-app notification: clear, concise, friendly',
        }.get(channel, 'In-app notification')

        system = (
            f'You are a notification copywriter for an earning site in Bangladesh. '
            f'{lang_note}. Format: {channel_note}. '
            f'Return ONLY JSON: {{"title": "...", "message": "..."}}. No extra text.'
        )
        user_msg = (
            f'Event: {event_type}\n'
            f'Context: {context}\n'
            f'Write a compelling, friendly notification for this event.'
        )

        try:
            raw = self._chat(system, user_msg)
            import json
            data = json.loads(raw.strip('`').replace('json\n', ''))
            return {'title': data.get('title', ''), 'message': data.get('message', '')}
        except Exception as exc:
            logger.warning(f'NotificationAIGenerator.generate_notification: {exc}')
            return self._fallback_content(event_type, context)

    def generate_ab_variants(self, notification_type: str, context: Dict) -> Tuple[Dict, Dict]:
        """
        Generate two A/B test variants for a notification.
        Returns (variant_a, variant_b) — each is {'title': ..., 'message': ...}.
        """
        if not self._available:
            base = self._fallback_content(notification_type, context)
            return base, {**base, 'title': base['title'] + ' 🎉'}

        system = (
            'You are a notification A/B testing specialist for an earning site. '
            'Generate TWO distinct notification variants. '
            'Variant A: formal, factual. Variant B: casual, emoji-rich, engaging. '
            'Return ONLY JSON: {"a": {"title":"...","message":"..."}, "b": {"title":"...","message":"..."}}'
        )
        user_msg = f'Notification type: {notification_type}\nContext: {context}'

        try:
            raw = self._chat(system, user_msg)
            import json
            data = json.loads(raw.strip('`').replace('json\n', ''))
            return data.get('a', {}), data.get('b', {})
        except Exception as exc:
            logger.warning(f'generate_ab_variants: {exc}')
            base = self._fallback_content(notification_type, context)
            return base, base

    def improve_copy(self, title: str, message: str, goal: str = 'engagement') -> Dict:
        """
        Improve existing notification copy.

        Args:
            title:   Current notification title.
            message: Current notification message.
            goal:    'engagement' | 'clarity' | 'urgency' | 'shorter'

        Returns:
            {'title': '...', 'message': '...', 'improvements': [...]}
        """
        if not self._available:
            return {'title': title, 'message': message, 'improvements': []}

        system = (
            f'You are a notification copywriter. '
            f'Improve the notification copy for goal: {goal}. '
            f'Return ONLY JSON: {{"title":"...","message":"...","improvements":["..."]}}'
        )
        user_msg = f'Current title: {title}\nCurrent message: {message}'

        try:
            raw = self._chat(system, user_msg)
            import json
            return json.loads(raw.strip('`').replace('json\n', ''))
        except Exception as exc:
            logger.warning(f'improve_copy: {exc}')
            return {'title': title, 'message': message, 'improvements': []}

    def translate_to_bangla(self, title: str, message: str) -> Dict:
        """
        Translate notification content to Bangla.
        Returns {'title_bn': '...', 'message_bn': '...'}
        """
        if not self._available:
            return {'title_bn': title, 'message_bn': message}

        system = (
            'You are a professional Bangla translator specialising in mobile notifications. '
            'Translate naturally, not word-for-word. Keep it friendly and clear. '
            'Return ONLY JSON: {"title_bn":"...","message_bn":"..."}'
        )
        user_msg = f'English title: {title}\nEnglish message: {message}'

        try:
            raw = self._chat(system, user_msg)
            import json
            return json.loads(raw.strip('`').replace('json\n', ''))
        except Exception as exc:
            logger.warning(f'translate_to_bangla: {exc}')
            return {'title_bn': title, 'message_bn': message}

    def suggest_subject_line(self, notification_type: str, context: Dict) -> str:
        """Generate an email subject line for a notification type."""
        if not self._available:
            return context.get('title', notification_type.replace('_', ' ').title())

        system = 'Write a short, compelling email subject line (max 60 chars). Return ONLY the subject line text.'
        user_msg = f'Notification type: {notification_type}\nContext: {context}'

        try:
            return self._chat(system, user_msg)[:60]
        except Exception as exc:
            logger.warning(f'suggest_subject_line: {exc}')
            return notification_type.replace('_', ' ').title()

    # ------------------------------------------------------------------
    # Fallback content (when OpenAI is unavailable)
    # ------------------------------------------------------------------

    FALLBACK_TEMPLATES = {
        'withdrawal_success': {'title': 'Withdrawal Successful 💰', 'message': 'Your withdrawal has been processed.'},
        'task_approved': {'title': 'Task Approved! 🎉', 'message': 'Your task submission has been approved.'},
        'kyc_approved': {'title': 'KYC Verified ✅', 'message': 'Your identity has been verified.'},
        'referral_reward': {'title': 'Referral Bonus! 🎁', 'message': 'You earned a referral bonus.'},
        'level_up': {'title': 'Level Up! 🚀', 'message': 'Congratulations on reaching a new level!'},
        'offer_completed': {'title': 'Offer Completed! 🎯', 'message': 'You completed an offer and earned a reward.'},
        'default': {'title': 'New Notification', 'message': 'You have a new notification.'},
    }

    def _fallback_content(self, notification_type: str, context: Dict) -> Dict:
        template = self.FALLBACK_TEMPLATES.get(notification_type, self.FALLBACK_TEMPLATES['default'])
        try:
            title = template['title'].format(**context)
            message = template['message'].format(**context)
        except (KeyError, ValueError):
            title, message = template['title'], template['message']
        return {'title': title, 'message': message}


# Singleton
ai_generator = NotificationAIGenerator()
