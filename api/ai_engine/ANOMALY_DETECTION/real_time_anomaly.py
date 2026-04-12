"""
api/ai_engine/ANOMALY_DETECTION/real_time_anomaly.py
=====================================================
Real-Time Anomaly Detector — low-latency anomaly scoring।
"""

import logging
from ..constants import DEFAULT_ANOMALY_THRESHOLD

logger = logging.getLogger(__name__)


class RealTimeAnomalyDetector:
    """
    Real-time anomaly detection engine।
    Rule-based + statistical signals combine করো।
    """

    def __init__(self, anomaly_type: str = 'general'):
        self.anomaly_type = anomaly_type

    def score(self, data: dict) -> float:
        """0.0-1.0 anomaly score।"""
        detectors = {
            'fraud_click':    self._score_click_fraud,
            'unusual_login':  self._score_login_anomaly,
            'bulk_request':   self._score_bulk_request,
            'transaction':    self._score_transaction,
            'user_behavior':  self._score_behavior,
        }
        fn = detectors.get(self.anomaly_type, self._score_general)
        return min(1.0, max(0.0, fn(data)))

    def is_anomaly(self, data: dict, threshold: float = None) -> bool:
        thr = threshold or DEFAULT_ANOMALY_THRESHOLD
        return self.score(data) >= thr

    def _score_click_fraud(self, d: dict) -> float:
        score = 0.0
        if d.get('is_vpn'):   score += 0.3
        if d.get('is_proxy'): score += 0.3
        if d.get('is_tor'):   score += 0.4
        clicks = d.get('clicks_per_hour', 0)
        if clicks > 100: score += 0.4
        elif clicks > 50: score += 0.2
        if d.get('same_offer_multiple_times'): score += 0.3
        return score

    def _score_login_anomaly(self, d: dict) -> float:
        score = 0.0
        if d.get('new_country'):     score += 0.35
        if d.get('new_device'):      score += 0.20
        if d.get('failed_attempts'): score += min(0.4, d['failed_attempts'] * 0.1)
        if d.get('unusual_time'):    score += 0.15
        return score

    def _score_bulk_request(self, d: dict) -> float:
        rps = d.get('requests_per_second', 0)
        if rps > 50:  return 0.95
        if rps > 20:  return 0.75
        if rps > 10:  return 0.50
        if rps > 5:   return 0.25
        return 0.0

    def _score_transaction(self, d: dict) -> float:
        score = 0.0
        amount = d.get('amount', 0)
        avg    = d.get('avg_transaction', 100)
        if avg > 0 and amount > avg * 5: score += 0.5
        if d.get('rapid_transactions'):  score += 0.3
        if d.get('new_payment_method'):  score += 0.2
        return score

    def _score_behavior(self, d: dict) -> float:
        score = 0.0
        sess = d.get('sessions_per_day', 1)
        if sess > 50: score += 0.4
        if d.get('bot_fingerprint'): score += 0.6
        return score

    def _score_general(self, d: dict) -> float:
        return d.get('risk_score', 0.0)
