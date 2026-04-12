"""
api/ai_engine/ANOMALY_DETECTION/transaction_anomaly.py
========================================================
Transaction Anomaly Detector — payment/withdrawal anomalies।
Unusual amounts, velocity, patterns।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class TransactionAnomalyDetector:
    """Transaction-level anomaly detection।"""

    def detect(self, transaction: dict, user_history: dict = None) -> dict:
        user_history = user_history or {}
        score  = 0.0
        flags  = []
        amount = float(transaction.get("amount", 0))

        # Amount anomaly
        avg_amount = float(user_history.get("avg_transaction", amount))
        if avg_amount > 0:
            ratio = amount / avg_amount
            if ratio > 10: score += 0.60; flags.append(f"amount_spike_{ratio:.0f}x")
            elif ratio > 5: score += 0.35; flags.append(f"amount_spike_{ratio:.0f}x")

        # Velocity anomaly
        txn_per_day = int(user_history.get("transactions_today", 0))
        if txn_per_day > 20: score += 0.40; flags.append("excessive_daily_transactions")
        elif txn_per_day > 10: score += 0.20; flags.append("high_daily_transactions")

        # Unusual time
        hour = int(transaction.get("hour", 12))
        if hour < 3 or hour > 23: score += 0.15; flags.append("unusual_transaction_time")

        # New destination
        if transaction.get("new_destination"): score += 0.25; flags.append("new_payment_destination")

        # Round number (possible money laundering signal)
        if amount > 1000 and amount % 1000 == 0: score += 0.10; flags.append("suspicious_round_amount")

        score = min(1.0, score)
        return {
            "is_anomaly":    score >= 0.60,
            "anomaly_score": round(score, 4),
            "severity":      "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.45 else "low",
            "flags":         flags,
            "recommendation": "block" if score >= 0.85 else "review" if score >= 0.60 else "monitor",
        }

    def analyze_pattern(self, transactions: List[Dict]) -> dict:
        if not transactions: return {"pattern": "no_data"}
        amounts  = [float(t.get("amount", 0)) for t in transactions]
        mean     = sum(amounts) / len(amounts)
        std      = math.sqrt(sum((a-mean)**2 for a in amounts) / max(len(amounts)-1, 1))
        outliers = [a for a in amounts if abs(a - mean) > 3 * std]
        return {
            "total_transactions": len(transactions),
            "avg_amount":         round(mean, 2),
            "std_amount":         round(std, 2),
            "outlier_count":      len(outliers),
            "pattern":            "normal" if len(outliers) < 2 else "suspicious",
        }

    def velocity_check(self, user_id: str, amount: float,
                        window_minutes: int = 60) -> dict:
        from ..models import PredictionLog
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(minutes=window_minutes)
        try:
            recent_count = PredictionLog.objects.filter(
                prediction_type="withdrawal",
                created_at__gte=since,
            ).count()
        except Exception:
            recent_count = 0

        velocity_anomaly = recent_count > 5
        return {
            "transactions_in_window": recent_count,
            "window_minutes":         window_minutes,
            "velocity_anomaly":       velocity_anomaly,
            "action":                 "block" if velocity_anomaly else "allow",
        }
