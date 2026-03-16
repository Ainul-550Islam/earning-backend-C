# api/promotions/utils/web_session_tracker.py
import logging, time, uuid
from django.core.cache import cache
logger = logging.getLogger('utils.session')

class WebSessionTracker:
    """User session tracking for task proof verification。"""
    SESSION_TTL = 3600 * 2   # 2 hours

    def start_session(self, user_id: int, campaign_id: int, task_url: str) -> str:
        session_id = uuid.uuid4().hex
        cache.set(f'session:{session_id}', {
            'user_id': user_id, 'campaign_id': campaign_id,
            'task_url': task_url, 'started_at': time.time(),
            'events': [], 'completed': False,
        }, timeout=self.SESSION_TTL)
        return session_id

    def record_event(self, session_id: str, event_type: str, data: dict = None) -> bool:
        s = cache.get(f'session:{session_id}')
        if not s: return False
        s['events'].append({'type': event_type, 'data': data or {}, 'ts': time.time()})
        s['events'] = s['events'][-50:]
        cache.set(f'session:{session_id}', s, timeout=self.SESSION_TTL)
        return True

    def mark_completed(self, session_id: str) -> bool:
        s = cache.get(f'session:{session_id}')
        if not s: return False
        s['completed']    = True
        s['completed_at'] = time.time()
        s['duration_sec'] = s['completed_at'] - s['started_at']
        cache.set(f'session:{session_id}', s, timeout=self.SESSION_TTL)
        return True

    def get_session(self, session_id: str) -> dict | None:
        return cache.get(f'session:{session_id}')

    def validate_time_on_task(self, session_id: str, min_seconds: int = 30) -> bool:
        s = cache.get(f'session:{session_id}')
        if not s or not s.get('completed'): return False
        return s.get('duration_sec', 0) >= min_seconds
