"""Session Analysis — tracks and analyses user session behaviour."""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SessionAnalyzer:
    """
    Analyses session-level behaviour for fraud signals.
    Uses Redis to track session state across requests.
    """
    def __init__(self, session_id: str, ip_address: str, user=None):
        self.session_id = session_id
        self.ip_address = ip_address
        self.user = user
        self.key = f"pi:session:{session_id}"

    def record_action(self, action_type: str, metadata: dict = None):
        session = cache.get(self.key, {
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'actions': [],
            'start_time': timezone.now().isoformat(),
        })
        session['actions'].append({
            'type': action_type,
            'time': timezone.now().isoformat(),
            'meta': metadata or {},
        })
        session['actions'] = session['actions'][-50:]  # keep last 50
        cache.set(self.key, session, 3600)
        return session

    def get_action_count(self, action_type: str = None) -> int:
        session = cache.get(self.key, {})
        actions = session.get('actions', [])
        if action_type:
            return sum(1 for a in actions if a['type'] == action_type)
        return len(actions)

    def is_suspicious(self) -> bool:
        count = self.get_action_count()
        return count > 100  # >100 actions in one session

    def get_summary(self) -> dict:
        session = cache.get(self.key, {})
        return {
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'total_actions': len(session.get('actions', [])),
            'is_suspicious': self.is_suspicious(),
            'start_time': session.get('start_time', ''),
        }
