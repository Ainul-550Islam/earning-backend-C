# api/offer_inventory/user_behavior_analysis/session_replay_logger.py
"""
Session Replay Logger — Lightweight event recorder per user session.
Records: page views, offer views, clicks, errors per session.
NOT full screen recording — just structured events for analysis.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SESSION_TTL    = 3600 * 2    # 2-hour session window
MAX_EVENTS     = 200          # Max events stored per session


class SessionReplayLogger:
    """Record structured user session events for analysis."""

    @staticmethod
    def start_session(user_id, session_id: str,
                       device: str = '', ip: str = '',
                       user_agent: str = '') -> bool:
        """Start recording a new session."""
        session = {
            'user_id'   : str(user_id),
            'session_id': session_id,
            'started_at': timezone.now().isoformat(),
            'device'    : device,
            'ip'        : ip,
            'user_agent': user_agent[:200],
            'events'    : [],
            'page_views': 0,
            'offer_views': 0,
            'clicks'    : 0,
        }
        cache.set(f'session:{session_id}', session, SESSION_TTL)
        return True

    @staticmethod
    def record_event(session_id: str, event_type: str,
                      data: dict = None) -> bool:
        """Record an event in an active session."""
        key     = f'session:{session_id}'
        session = cache.get(key)
        if not session:
            return False

        event = {
            'type'     : event_type,
            'data'     : data or {},
            'timestamp': timezone.now().isoformat(),
        }
        session['events'].append(event)
        session['events'] = session['events'][-MAX_EVENTS:]

        # Update counters
        if event_type == 'page_view':
            session['page_views'] = session.get('page_views', 0) + 1
        elif event_type == 'offer_view':
            session['offer_views'] = session.get('offer_views', 0) + 1
        elif event_type == 'click':
            session['clicks'] = session.get('clicks', 0) + 1

        cache.set(key, session, SESSION_TTL)
        return True

    @staticmethod
    def record_page_view(session_id: str, path: str,
                          referrer: str = '') -> bool:
        """Record a page view event."""
        return SessionReplayLogger.record_event(
            session_id, 'page_view',
            {'path': path, 'referrer': referrer}
        )

    @staticmethod
    def record_offer_view(session_id: str, offer_id: str,
                           offer_title: str = '') -> bool:
        """Record an offer impression event."""
        return SessionReplayLogger.record_event(
            session_id, 'offer_view',
            {'offer_id': offer_id, 'title': offer_title}
        )

    @staticmethod
    def record_offer_click(session_id: str, offer_id: str) -> bool:
        """Record an offer click event."""
        return SessionReplayLogger.record_event(
            session_id, 'click', {'offer_id': offer_id}
        )

    @staticmethod
    def record_error(session_id: str, error_msg: str,
                      path: str = '') -> bool:
        """Record a client-side error."""
        return SessionReplayLogger.record_event(
            session_id, 'error',
            {'message': error_msg[:200], 'path': path}
        )

    @staticmethod
    def get_session(session_id: str) -> dict:
        """Retrieve active session data."""
        return cache.get(f'session:{session_id}', {})

    @staticmethod
    def end_session(session_id: str) -> dict:
        """End a session and return its summary."""
        key     = f'session:{session_id}'
        session = cache.get(key) or {}
        if session:
            session['ended_at'] = timezone.now().isoformat()
            duration = None
            if session.get('started_at'):
                from datetime import datetime
                try:
                    start    = datetime.fromisoformat(session['started_at'])
                    end      = datetime.fromisoformat(session['ended_at'])
                    duration = round((end - start).total_seconds())
                except Exception:
                    pass
            session['duration_seconds'] = duration
            cache.delete(key)
        return session

    @staticmethod
    def get_session_stats(session: dict) -> dict:
        """Compute stats from a session dict."""
        events     = session.get('events', [])
        page_paths = [e['data'].get('path', '') for e in events if e['type'] == 'page_view']
        offers_viewed = [e['data'].get('offer_id', '') for e in events if e['type'] == 'offer_view']
        return {
            'total_events' : len(events),
            'page_views'   : session.get('page_views', 0),
            'offer_views'  : session.get('offer_views', 0),
            'clicks'       : session.get('clicks', 0),
            'unique_pages' : len(set(page_paths)),
            'unique_offers': len(set(offers_viewed)),
            'has_errors'   : any(e['type'] == 'error' for e in events),
        }
