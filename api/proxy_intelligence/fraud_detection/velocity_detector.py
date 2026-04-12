"""Velocity Detector — fraud-specific velocity and rate-limit checks."""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Per-action velocity thresholds (action_type: {threshold, window_sec})
ACTION_THRESHOLDS = {
    'login':            {'threshold': 5,   'window': 60,   'action': 'block'},
    'offer_complete':   {'threshold': 10,  'window': 300,  'action': 'flag'},
    'withdrawal':       {'threshold': 3,   'window': 3600, 'action': 'block'},
    'api_call':         {'threshold': 120, 'window': 60,   'action': 'rate_limit'},
    'fingerprint':      {'threshold': 5,   'window': 300,  'action': 'flag'},
    'referral_signup':  {'threshold': 3,   'window': 3600, 'action': 'block'},
    'offer_click':      {'threshold': 20,  'window': 60,   'action': 'flag'},
    'task_submit':      {'threshold': 15,  'window': 300,  'action': 'flag'},
    'kyc_attempt':      {'threshold': 3,   'window': 3600, 'action': 'block'},
    'password_reset':   {'threshold': 3,   'window': 3600, 'action': 'block'},
    'reward_claim':     {'threshold': 5,   'window': 3600, 'action': 'block'},
}

DEFAULT_THRESHOLD = {'threshold': 60, 'window': 60, 'action': 'flag'}


class FraudVelocityDetector:
    """
    Checks request velocity for each action type and flags
    or blocks when thresholds are exceeded.
    """

    def __init__(self, ip_address: str, user=None, tenant=None):
        self.ip_address = ip_address
        self.user = user
        self.tenant = tenant

    def check(self, action_type: str) -> dict:
        """Check velocity for a specific action. Returns result dict."""
        config = ACTION_THRESHOLDS.get(action_type, DEFAULT_THRESHOLD)

        # Get per-IP count
        ip_key = f"pi:vel:{self.ip_address}:{action_type}:{config['window']}"
        ip_count = self._increment(ip_key, config['window'])

        # Get per-user count (if user present)
        user_count = 0
        if self.user:
            user_key = f"pi:vel:u{self.user.pk}:{action_type}:{config['window']}"
            user_count = self._increment(user_key, config['window'])

        exceeded = ip_count > config['threshold']
        combined_count = max(ip_count, user_count)

        result = {
            'ip_address': self.ip_address,
            'action_type': action_type,
            'ip_request_count': ip_count,
            'user_request_count': user_count,
            'threshold': config['threshold'],
            'window_seconds': config['window'],
            'exceeded': exceeded,
            'recommended_action': config['action'] if exceeded else 'allow',
        }

        if exceeded:
            self._persist(action_type, combined_count, config)

        return result

    def _increment(self, key: str, ttl: int) -> int:
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, ttl)
            count = 1
        return count

    def _persist(self, action_type: str, count: int, config: dict):
        """Write to DB (throttled: one write per window per IP+action)."""
        db_key = f"pi:vel_db:{self.ip_address}:{action_type}"
        if cache.get(db_key):
            return
        try:
            from ..models import VelocityMetric
            VelocityMetric.objects.create(
                ip_address=self.ip_address,
                user=self.user,
                action_type=action_type,
                window_seconds=config['window'],
                request_count=count,
                threshold=config['threshold'],
                exceeded=True,
                tenant=self.tenant,
            )
            cache.set(db_key, 1, config['window'])
        except Exception as e:
            logger.debug(f"VelocityMetric DB write failed: {e}")

    def get_current_rate(self, action_type: str) -> int:
        config = ACTION_THRESHOLDS.get(action_type, DEFAULT_THRESHOLD)
        key = f"pi:vel:{self.ip_address}:{action_type}:{config['window']}"
        return cache.get(key, 0)

    def reset(self, action_type: str):
        config = ACTION_THRESHOLDS.get(action_type, DEFAULT_THRESHOLD)
        key = f"pi:vel:{self.ip_address}:{action_type}:{config['window']}"
        cache.delete(key)

    @classmethod
    def check_all(cls, ip_address: str, actions: list,
                  user=None, tenant=None) -> dict:
        """Check multiple actions at once."""
        detector = cls(ip_address, user, tenant)
        results = {}
        any_exceeded = False
        for action in actions:
            r = detector.check(action)
            results[action] = r
            if r['exceeded']:
                any_exceeded = True
        return {
            'ip_address': ip_address,
            'any_exceeded': any_exceeded,
            'results': results,
        }
