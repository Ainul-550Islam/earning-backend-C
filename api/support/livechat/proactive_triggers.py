"""
api/support/livechat/proactive_triggers.py
FILE 21/70 — Proactive Chat Triggers

User নির্দিষ্ট condition-এ থাকলে auto chat popup করো।
CPAlead, Intercom-এর মতো proactive engagement।

Triggers:
- User X seconds একটি page-এ থাকলে
- User checkout/withdrawal page-এ stuck হলে
- User multiple failed attempts করলে
- High-value user detected হলে
- User exit intent detect হলে

Frontend JS widget এই API-কে call করবে।
Settings:
    PROACTIVE_CHAT_ENABLED = True
    PROACTIVE_IDLE_SECONDS = 30
"""
import logging
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

PROACTIVE_ENABLED     = getattr(settings, 'PROACTIVE_CHAT_ENABLED', True)
IDLE_SECONDS          = getattr(settings, 'PROACTIVE_IDLE_SECONDS', 30)
EXIT_INTENT_THRESHOLD = getattr(settings, 'PROACTIVE_EXIT_INTENT_THRESHOLD', 3)


class ProactiveChatTriggerEngine:
    """
    Proactive chat trigger evaluation engine।
    User behaviour analyze করো এবং সঠিক সময়ে chat open করো।
    """

    # ──────────────────────────────────────────
    # TRIGGER DEFINITIONS
    # ──────────────────────────────────────────
    TRIGGERS = {
        'idle_on_checkout': {
            'name':        'Idle on Checkout/Withdrawal',
            'description': 'User idle 30s on withdrawal/checkout page',
            'pages':       ['/withdraw', '/checkout', '/payment', '/wallet'],
            'idle_seconds':30,
            'message':     'Need help with your withdrawal? Our team is here! 💬',
            'priority':    'high',
        },
        'idle_on_kyc': {
            'name':        'Idle on KYC Page',
            'description': 'User idle 45s on KYC page',
            'pages':       ['/kyc', '/verification', '/verify'],
            'idle_seconds':45,
            'message':     'Having trouble with verification? We can help you complete it! 📋',
            'priority':    'medium',
        },
        'multiple_failed_actions': {
            'name':        'Multiple Failed Attempts',
            'description': 'User failed same action 3+ times',
            'threshold':   3,
            'message':     'It looks like you\'re having trouble. Let us help! 🆘',
            'priority':    'high',
        },
        'exit_intent': {
            'name':        'Exit Intent',
            'description': 'User moving mouse towards browser close/back',
            'message':     'Before you go — can we help with anything? 👋',
            'priority':    'medium',
        },
        'long_session': {
            'name':        'Long Session Without Action',
            'description': 'User browsing 5+ minutes without completing action',
            'minutes':     5,
            'message':     'Looking for something specific? We\'re here to help! 🔍',
            'priority':    'low',
        },
        'returning_with_issue': {
            'name':        'Returning User with Open Ticket',
            'description': 'User with unresolved ticket visits site',
            'message':     'Welcome back! We\'re still working on your ticket. Want an update? 🎫',
            'priority':    'high',
        },
        'high_value_user': {
            'name':        'High Value User',
            'description': 'VIP/high-earning user detected',
            'message':     'Welcome back, valued member! Is there anything we can help you with? ⭐',
            'priority':    'medium',
        },
    }

    # ──────────────────────────────────────────
    # EVALUATE TRIGGERS
    # ──────────────────────────────────────────
    def evaluate(self, user_id: str, page_url: str, session_data: dict) -> dict | None:
        """
        User-এর current context evaluate করো।
        Matching trigger থাকলে chat prompt data return করো।
        Returns: {trigger_id, message, priority} or None
        """
        if not PROACTIVE_ENABLED:
            return None

        # Already shown → skip
        if self._already_triggered(user_id, page_url):
            return None

        # Evaluate each trigger
        for trigger_id, trigger in self.TRIGGERS.items():
            if self._matches(trigger_id, trigger, user_id, page_url, session_data):
                self._mark_triggered(user_id, page_url, trigger_id)

                return {
                    'trigger_id': trigger_id,
                    'trigger_name':trigger['name'],
                    'message':    trigger['message'],
                    'priority':   trigger['priority'],
                    'show_after_seconds': trigger.get('idle_seconds', 3),
                    'auto_open':  trigger['priority'] == 'high',
                }

        return None

    def evaluate_batch(self, events: list) -> list:
        """
        Multiple events process করো।
        events = [{user_id, page_url, session_data, event_type}]
        """
        results = []
        for event in events:
            result = self.evaluate(
                event.get('user_id', ''),
                event.get('page_url', ''),
                event.get('session_data', {}),
            )
            if result:
                results.append({**result, 'user_id': event.get('user_id')})
        return results

    # ──────────────────────────────────────────
    # TRIGGER MATCHERS
    # ──────────────────────────────────────────
    def _matches(self, trigger_id: str, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        method = getattr(self, f'_check_{trigger_id}', None)
        if not method:
            return False
        try:
            return method(trigger, user_id, page_url, session)
        except Exception as e:
            logger.warning(f'Trigger check failed [{trigger_id}]: {e}')
            return False

    def _check_idle_on_checkout(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        # Page match
        is_target_page = any(p in page_url for p in trigger['pages'])
        if not is_target_page:
            return False
        # Idle time check
        idle_secs = session.get('idle_seconds', 0)
        return idle_secs >= trigger['idle_seconds']

    def _check_idle_on_kyc(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        is_target_page = any(p in page_url for p in trigger['pages'])
        if not is_target_page:
            return False
        idle_secs = session.get('idle_seconds', 0)
        return idle_secs >= trigger['idle_seconds']

    def _check_multiple_failed_actions(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        failed_count = session.get('failed_attempts', 0)
        return failed_count >= trigger['threshold']

    def _check_exit_intent(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        return session.get('exit_intent', False)

    def _check_long_session(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        session_minutes = session.get('session_minutes', 0)
        has_action      = session.get('completed_action', False)
        return session_minutes >= trigger['minutes'] and not has_action

    def _check_returning_with_issue(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        if not user_id:
            return False
        try:
            from api.support.models import SupportTicket
            from django.contrib.auth import get_user_model
            User   = get_user_model()
            user   = User.objects.filter(id=user_id).first()
            if not user:
                return False
            return SupportTicket.objects.filter(
                user     = user,
                status__in = ['open', 'in_progress', 'waiting_user'],
            ).exists()
        except Exception:
            return False

    def _check_high_value_user(self, trigger: dict, user_id: str, page_url: str, session: dict) -> bool:
        if not user_id:
            return False
        # Check user tier/value
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first()
            if not user:
                return False
            # Check if VIP (has made 5+ withdrawals or high earnings)
            user_tier = getattr(getattr(user, 'profile', None), 'tier', None)
            return user_tier in ['gold', 'platinum', 'vip']
        except Exception:
            return False

    # ──────────────────────────────────────────
    # STATE MANAGEMENT
    # ──────────────────────────────────────────
    def _already_triggered(self, user_id: str, page_url: str) -> bool:
        """Same page-এ already trigger হয়েছে কিনা (24hr window)"""
        key = f'proactive_triggered:{user_id}:{hash(page_url)}'
        return bool(cache.get(key))

    def _mark_triggered(self, user_id: str, page_url: str, trigger_id: str) -> None:
        key = f'proactive_triggered:{user_id}:{hash(page_url)}'
        cache.set(key, trigger_id, timeout=86400)  # 24 hours

    def track_page_time(self, user_id: str, page_url: str, seconds: int) -> None:
        """Page-এ কতক্ষণ আছে track করো"""
        key = f'page_time:{user_id}:{hash(page_url)}'
        cache.set(key, seconds, timeout=3600)

    def get_page_time(self, user_id: str, page_url: str) -> int:
        key = f'page_time:{user_id}:{hash(page_url)}'
        return cache.get(key, 0)

    def track_failed_attempt(self, user_id: str, action: str) -> int:
        """Failed attempt count করো"""
        key   = f'failed:{user_id}:{action}'
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=3600)
        return count

    # ──────────────────────────────────────────
    # ANALYTICS
    # ──────────────────────────────────────────
    def get_trigger_stats(self) -> dict:
        """Trigger effectiveness stats"""
        # In production, track in DB
        return {
            'triggers_configured': len(self.TRIGGERS),
            'enabled':             PROACTIVE_ENABLED,
            'idle_threshold_sec':  IDLE_SECONDS,
        }

    def get_best_messages(self, category: str = None) -> list:
        """Best performing proactive messages"""
        messages = []
        for tid, trigger in self.TRIGGERS.items():
            messages.append({
                'trigger_id': tid,
                'name':       trigger['name'],
                'message':    trigger['message'],
                'priority':   trigger['priority'],
            })
        return messages


# ──────────────────────────────────────────
# API VIEW HELPERS
# ──────────────────────────────────────────
def evaluate_proactive_trigger(request_data: dict) -> dict | None:
    """
    View থেকে call করো।
    POST /support/chat/proactive-check/
    """
    engine = ProactiveChatTriggerEngine()
    return engine.evaluate(
        user_id      = str(request_data.get('user_id', '')),
        page_url     = request_data.get('page_url', ''),
        session_data = request_data.get('session_data', {}),
    )


# Singleton
proactive_trigger_engine = ProactiveChatTriggerEngine()