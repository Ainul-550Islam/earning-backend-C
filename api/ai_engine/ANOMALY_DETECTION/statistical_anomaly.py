"""
api/ai_engine/ANOMALY_DETECTION/statistical_anomaly.py
=======================================================
Statistical Anomaly Detection — Z-score, IQR methods।
"""

import math
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class StatisticalAnomalyDetector:
    """Z-score এবং IQR-based anomaly detection।"""

    def __init__(self, method: str = 'zscore', threshold: float = 3.0):
        self.method    = method
        self.threshold = threshold

    def fit(self, data: List[float]):
        if not data:
            self.mean, self.std, self.q1, self.q3 = 0, 1, 0, 1
            return
        n = len(data)
        self.mean  = sum(data) / n
        self.std   = math.sqrt(sum((x - self.mean) ** 2 for x in data) / n) or 1e-9
        sorted_data = sorted(data)
        self.q1 = sorted_data[int(n * 0.25)]
        self.q3 = sorted_data[int(n * 0.75)]
        self.iqr = self.q3 - self.q1 or 1e-9

    def is_anomaly(self, value: float) -> bool:
        if self.method == 'zscore':
            return abs((value - self.mean) / self.std) > self.threshold
        elif self.method == 'iqr':
            lower = self.q1 - 1.5 * self.iqr
            upper = self.q3 + 1.5 * self.iqr
            return value < lower or value > upper
        return False

    def score(self, value: float) -> float:
        z = abs((value - self.mean) / self.std)
        return min(1.0, z / (self.threshold * 2))


"""
api/ai_engine/ANOMALY_DETECTION/click_anomaly_detector.py
==========================================================
Click Fraud / Anomaly Detector।
"""


class ClickAnomalyDetector:
    """Click pattern anomaly detection।"""

    def analyze(self, click_data: dict, user=None) -> dict:
        clicks_per_hour = click_data.get('clicks_per_hour', 0)
        unique_offers   = click_data.get('unique_offers', 1)
        avg_time_ms     = click_data.get('avg_click_time_ms', 1000)

        score = 0.0
        flags = []

        if clicks_per_hour > 200:
            score += 0.5; flags.append('excessive_clicks')
        elif clicks_per_hour > 100:
            score += 0.3; flags.append('high_click_rate')

        if avg_time_ms < 100:
            score += 0.4; flags.append('bot_speed_clicks')
        elif avg_time_ms < 300:
            score += 0.2; flags.append('fast_clicks')

        if unique_offers == 1 and clicks_per_hour > 20:
            score += 0.3; flags.append('single_offer_spam')

        return {
            'anomaly_score': round(min(1.0, score), 4),
            'is_fraud':      score >= 0.7,
            'flags':         flags,
            'clicks_per_hour': clicks_per_hour,
        }


"""
api/ai_engine/ANOMALY_DETECTION/transaction_anomaly.py
======================================================
Transaction Anomaly Detector।
"""


class TransactionAnomalyDetector:
    """Unusual transaction pattern detection।"""

    def analyze(self, transaction_data: dict, user=None) -> dict:
        amount = transaction_data.get('amount', 0)
        count_today = transaction_data.get('transactions_today', 0)
        avg_amount  = transaction_data.get('avg_amount', 100)
        max_amount  = transaction_data.get('max_ever', 1000)

        score = 0.0
        flags = []

        if avg_amount > 0 and amount > avg_amount * 10:
            score += 0.5; flags.append('amount_spike')
        if count_today > 20:
            score += 0.3; flags.append('rapid_transactions')
        if transaction_data.get('new_destination'):
            score += 0.2; flags.append('new_destination')
        if amount > 50000:
            score += 0.2; flags.append('large_amount')

        return {
            'anomaly_score': round(min(1.0, score), 4),
            'is_suspicious': score >= 0.6,
            'flags':         flags,
            'amount':        amount,
        }
