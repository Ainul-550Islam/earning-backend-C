"""
api/support/livechat/visitor_tracking.py
FILE 22/70 — Visitor Tracking

User-এর page visit, time spent, clicks track করো।
Agent dashboard-এ real-time visitor info দেখাবে।
Proactive chat trigger-এর জন্য data collect করো।

Features:
- Page visit tracking
- Session duration tracking
- Current page showing in agent dashboard
- Failed action tracking
- Exit intent detection

JS Widget send করবে:
POST /support/tracking/event/
{
  "event": "page_view"|"idle"|"exit_intent"|"action_failed",
  "page_url": "/withdraw",
  "user_id": "123",
  "session_id": "abc123",
  "data": {...}
}
"""
import logging
import uuid
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SESSION_TTL    = 1800   # 30 minutes
VISITOR_TTL    = 86400  # 24 hours


class VisitorTracker:
    """
    Real-time visitor tracking।
    Redis-based session state।
    """

    # ──────────────────────────────────────────
    # TRACK EVENTS
    # ──────────────────────────────────────────
    def track_event(self, event_type: str, session_id: str, user_id: str,
                    page_url: str, data: dict = None) -> dict:
        """
        Visitor event process করো।
        Returns: {should_trigger_chat: bool, trigger_data: dict|None}
        """
        data = data or {}
        result = {'should_trigger_chat': False, 'trigger_data': None}

        # Update session state
        session = self._get_session(session_id)
        session['user_id']    = user_id
        session['last_page']  = page_url
        session['last_seen']  = timezone.now().isoformat()
        session['event_count']= session.get('event_count', 0) + 1

        if event_type == 'page_view':
            self._handle_page_view(session, page_url, data)

        elif event_type == 'idle':
            idle_seconds = data.get('idle_seconds', 0)
            session['idle_seconds'] = idle_seconds
            result = self._check_proactive_trigger(session, user_id, page_url)

        elif event_type == 'exit_intent':
            session['exit_intent'] = True
            result = self._check_proactive_trigger(session, user_id, page_url)

        elif event_type == 'action_failed':
            action = data.get('action', 'unknown')
            session['failed_attempts'] = session.get('failed_attempts', {})
            session['failed_attempts'][action] = session['failed_attempts'].get(action, 0) + 1
            total_failures = sum(session['failed_attempts'].values())
            session['total_failed_attempts'] = total_failures

            if total_failures >= 3:
                result = self._check_proactive_trigger(session, user_id, page_url)

        elif event_type == 'chat_opened':
            session['chat_opened'] = True
            self._mark_chat_opened(user_id)

        elif event_type == 'action_completed':
            session['completed_action'] = True

        elif event_type == 'session_start':
            session['started_at']    = timezone.now().isoformat()
            session['session_id']    = session_id
            session['pages_visited'] = []
            session['user_agent']    = data.get('user_agent', '')
            session['referrer']      = data.get('referrer', '')

        # Save session
        self._save_session(session_id, session)

        # Update visitor record
        if user_id:
            self._update_visitor(user_id, session)

        return result

    # ──────────────────────────────────────────
    # PAGE VIEW
    # ──────────────────────────────────────────
    def _handle_page_view(self, session: dict, page_url: str, data: dict) -> None:
        """Page view process করো"""
        pages = session.get('pages_visited', [])
        pages.append({
            'url':       page_url,
            'timestamp': timezone.now().isoformat(),
            'title':     data.get('title', ''),
        })
        session['pages_visited'] = pages[-20:]  # Keep last 20 pages
        session['idle_seconds']  = 0  # Reset idle on page view
        session['exit_intent']   = False

        # Track session duration
        started = session.get('started_at')
        if started:
            from datetime import datetime
            try:
                start_dt = datetime.fromisoformat(started)
                now      = timezone.now()
                if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo is None:
                    from django.utils.timezone import make_aware
                    start_dt = make_aware(start_dt)
                session['session_minutes'] = round(
                    (now - start_dt).total_seconds() / 60, 1
                )
            except Exception:
                pass

    # ──────────────────────────────────────────
    # PROACTIVE TRIGGER CHECK
    # ──────────────────────────────────────────
    def _check_proactive_trigger(self, session: dict, user_id: str, page_url: str) -> dict:
        """Should proactive chat trigger?"""
        result = {'should_trigger_chat': False, 'trigger_data': None}

        # Already opened chat
        if session.get('chat_opened') or self._chat_already_opened(user_id):
            return result

        try:
            from api.support.livechat.proactive_triggers import proactive_trigger_engine
            trigger = proactive_trigger_engine.evaluate(user_id, page_url, session)
            if trigger:
                result['should_trigger_chat'] = True
                result['trigger_data']        = trigger
        except Exception as e:
            logger.warning(f'Proactive trigger check failed: {e}')

        return result

    # ──────────────────────────────────────────
    # ACTIVE VISITORS (Agent Dashboard)
    # ──────────────────────────────────────────
    def get_active_visitors(self, limit: int = 50) -> list:
        """
        Currently online visitors।
        Agent dashboard-এ real-time দেখাবে।
        """
        try:
            # Get all active visitor keys from cache
            # In production use Redis SCAN
            visitors = []
            # Sample implementation — in production use Redis
            return visitors
        except Exception:
            return []

    def get_visitor_info(self, user_id: str) -> dict:
        """Specific user-এর current session info"""
        visitor_key = f'visitor:{user_id}'
        visitor     = cache.get(visitor_key, {})
        if not visitor:
            return {'user_id': user_id, 'online': False}

        return {
            'user_id':       user_id,
            'online':        True,
            'current_page':  visitor.get('last_page', ''),
            'session_min':   visitor.get('session_minutes', 0),
            'pages_visited': visitor.get('page_count', 0),
            'has_open_ticket':self._has_open_ticket(user_id),
            'last_seen':     visitor.get('last_seen', ''),
        }

    def get_page_visitors(self, page_url: str) -> int:
        """Specific page-এ কতজন visitors আছে"""
        key = f'page_visitors:{hash(page_url)}'
        return cache.get(key, 0)

    # ──────────────────────────────────────────
    # SESSION MANAGEMENT
    # ──────────────────────────────────────────
    def create_session(self, user_id: str = None, ip: str = None, user_agent: str = None) -> str:
        """New visitor session create করো"""
        session_id = str(uuid.uuid4())[:16]
        session    = {
            'session_id':    session_id,
            'user_id':       user_id or '',
            'ip':            ip or '',
            'user_agent':    user_agent or '',
            'started_at':    timezone.now().isoformat(),
            'pages_visited': [],
            'event_count':   0,
        }
        self._save_session(session_id, session)
        return session_id

    def end_session(self, session_id: str) -> None:
        """Session end করো"""
        cache.delete(f'session:{session_id}')

    def _get_session(self, session_id: str) -> dict:
        return cache.get(f'session:{session_id}', {})

    def _save_session(self, session_id: str, data: dict) -> None:
        cache.set(f'session:{session_id}', data, timeout=SESSION_TTL)

    def _update_visitor(self, user_id: str, session: dict) -> None:
        """Visitor record update করো"""
        key     = f'visitor:{user_id}'
        visitor = cache.get(key, {})
        visitor.update({
            'user_id':        user_id,
            'last_page':      session.get('last_page', ''),
            'last_seen':      session.get('last_seen', ''),
            'session_minutes':session.get('session_minutes', 0),
            'page_count':     len(session.get('pages_visited', [])),
        })
        cache.set(key, visitor, timeout=VISITOR_TTL)

    def _mark_chat_opened(self, user_id: str) -> None:
        key = f'chat_opened:{user_id}'
        cache.set(key, True, timeout=86400)  # 24 hours

    def _chat_already_opened(self, user_id: str) -> bool:
        key = f'chat_opened:{user_id}'
        return bool(cache.get(key))

    def _has_open_ticket(self, user_id: str) -> bool:
        try:
            from api.support.models import SupportTicket
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first()
            if not user:
                return False
            return SupportTicket.objects.filter(
                user=user, status__in=['open','in_progress','waiting_user']
            ).exists()
        except Exception:
            return False

    # ──────────────────────────────────────────
    # STATS
    # ──────────────────────────────────────────
    def get_tracking_stats(self) -> dict:
        return {
            'session_ttl_minutes':  SESSION_TTL // 60,
            'visitor_ttl_hours':    VISITOR_TTL // 3600,
            'tracking_enabled':     True,
        }


# Singleton
visitor_tracker = VisitorTracker()