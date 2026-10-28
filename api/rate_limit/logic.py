# api/rate_limit/logic.py
"""Business logic helpers for rate limit module."""
import logging
logger = logging.getLogger(__name__)

class HealthMonitoring:
    """System health monitoring logic."""
    def __init__(self):
        self.checks = {}

    def run_checks(self):
        return {'status': 'healthy', 'checks': self.checks}

    def check_redis(self):
        try:
            from django.core.cache import cache
            cache.get('health_check')
            return True
        except Exception:
            return False

    def get_health_score(self):
        return 100 if self.check_redis() else 50


class AbuseDetectionLogic:
    """Core abuse detection logic."""
    THRESHOLDS = {
        'high_volume': 100,
        'rapid_requests': 50,
        'suspicious_pattern': 30,
    }

    def score(self, logs):
        return min(100, len(logs))

    def is_abusive(self, score, threshold=50):
        return score >= threshold


__all__ = ['HealthMonitoring', 'AbuseDetectionLogic']
