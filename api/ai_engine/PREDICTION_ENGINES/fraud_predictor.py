"""
api/ai_engine/PREDICTION_ENGINES/fraud_predictor.py
====================================================
Fraud Predictor — multi-signal fraud detection।
"""

import logging
from ..utils import days_since
from ..constants import DEFAULT_FRAUD_THRESHOLD

logger = logging.getLogger(__name__)


class FraudPredictor:
    """
    Multi-signal fraud scoring।
    IP, device, behavior, velocity signals combine করো।
    """

    WEIGHTS = {
        'ip_signals':       0.30,
        'device_signals':   0.25,
        'velocity_signals': 0.25,
        'behavior_signals': 0.20,
    }

    def score(self, user, metadata: dict) -> dict:
        ip_score       = self._ip_score(metadata)
        device_score   = self._device_score(user, metadata)
        velocity_score = self._velocity_score(metadata)
        behavior_score = self._behavior_score(user, metadata)

        final_score = (
            ip_score       * self.WEIGHTS['ip_signals'] +
            device_score   * self.WEIGHTS['device_signals'] +
            velocity_score * self.WEIGHTS['velocity_signals'] +
            behavior_score * self.WEIGHTS['behavior_signals']
        )
        final_score = min(1.0, final_score)

        return {
            'fraud_score':   round(final_score, 4),
            'is_fraud':      final_score >= DEFAULT_FRAUD_THRESHOLD,
            'signals': {
                'ip_score':       round(ip_score, 3),
                'device_score':   round(device_score, 3),
                'velocity_score': round(velocity_score, 3),
                'behavior_score': round(behavior_score, 3),
            },
            'threshold': DEFAULT_FRAUD_THRESHOLD,
        }

    def _ip_score(self, meta: dict) -> float:
        score = 0.0
        if meta.get('is_vpn'):   score += 0.4
        if meta.get('is_proxy'): score += 0.4
        if meta.get('is_tor'):   score += 0.6
        if meta.get('ip_blacklisted'): score += 0.8
        return min(1.0, score)

    def _device_score(self, user, meta: dict) -> float:
        score = 0.0
        device_count = meta.get('device_count', 1)
        if device_count > 5:  score += 0.5
        elif device_count > 3: score += 0.3
        if meta.get('emulator_detected'): score += 0.6
        if meta.get('rooted_device'):     score += 0.3
        return min(1.0, score)

    def _velocity_score(self, meta: dict) -> float:
        score = 0.0
        clicks_1h = meta.get('clicks_1h', 0)
        if clicks_1h > 100: score += 0.7
        elif clicks_1h > 50: score += 0.4
        elif clicks_1h > 20: score += 0.2
        reqs_per_min = meta.get('requests_per_minute', 0)
        if reqs_per_min > 60: score += 0.5
        return min(1.0, score)

    def _behavior_score(self, user, meta: dict) -> float:
        score = 0.0
        account_age = days_since(getattr(user, 'date_joined', None))
        if account_age < 1:   score += 0.4
        elif account_age < 7: score += 0.2
        if meta.get('same_ip_multiple_accounts'): score += 0.5
        if meta.get('account_sharing_detected'):  score += 0.6
        return min(1.0, score)
