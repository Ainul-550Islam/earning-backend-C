"""Behavior Analyzer — analyses user action patterns for fraud signals."""
import logging, statistics
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

class BehaviorAnalyzer:
    def __init__(self, user=None, ip_address: str = '', tenant=None):
        self.user = user
        self.ip_address = ip_address
        self.tenant = tenant

    def analyze(self) -> dict:
        score = 0
        signals = []

        click_rate = self._get_click_rate()
        if click_rate > 20:
            score += 25; signals.append(f'high_click_rate:{click_rate}/min')

        session_count = self._get_session_count()
        if session_count > 5:
            score += 15; signals.append(f'multiple_sessions:{session_count}')

        if self.user:
            fraud_count = self._get_fraud_history()
            if fraud_count > 0:
                score += min(fraud_count * 10, 40)
                signals.append(f'fraud_history:{fraud_count}')

        return {
            'behavior_risk_score': min(score, 100),
            'signals': signals,
            'click_rate_per_min': click_rate,
            'active_sessions': session_count,
        }

    def _get_click_rate(self) -> int:
        return cache.get(f"pi:clicks:{self.ip_address}", 0)

    def _get_session_count(self) -> int:
        return cache.get(f"pi:sessions:{self.ip_address}", 0)

    def _get_fraud_history(self) -> int:
        try:
            from ..models import FraudAttempt
            return FraudAttempt.objects.filter(
                user=self.user, status='confirmed'
            ).count()
        except Exception:
            return 0
