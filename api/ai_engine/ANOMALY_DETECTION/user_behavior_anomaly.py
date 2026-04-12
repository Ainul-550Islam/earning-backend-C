"""
api/ai_engine/ANOMALY_DETECTION/user_behavior_anomaly.py
=========================================================
User Behavior Anomaly Detector — abnormal user patterns।
Session patterns, earning patterns, click patterns।
Account takeover, collusion, automated behavior detect করো।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UserBehaviorAnomalyDetector:
    """
    User behavioral anomaly detection।
    Normal vs abnormal patterns identify করো।
    """

    def detect(self, user, behavior_data: dict,
                anomaly_type: str = "general") -> dict:
        """User behavior anomaly detect করো।"""
        detectors = {
            "session":     self._session_anomaly,
            "earning":     self._earning_anomaly,
            "click":       self._click_anomaly,
            "login":       self._login_anomaly,
            "withdrawal":  self._withdrawal_anomaly,
            "general":     self._general_anomaly,
        }
        detector = detectors.get(anomaly_type, self._general_anomaly)
        result   = detector(user, behavior_data)

        # Log if anomaly detected
        if result["is_anomaly"]:
            self._log_anomaly(user, anomaly_type, result)

        return result

    def _session_anomaly(self, user, data: dict) -> dict:
        score  = 0.0
        flags  = []
        sess_per_day = data.get("sessions_per_day", 0)
        avg_duration = data.get("avg_duration_seconds", 0)
        action_rate  = data.get("actions_per_second", 0)

        if sess_per_day > 100:
            score += 0.5; flags.append("excessive_daily_sessions")
        elif sess_per_day > 50:
            score += 0.3; flags.append("high_session_count")

        if action_rate > 5:
            score += 0.4; flags.append("bot_like_action_speed")

        if avg_duration < 1:
            score += 0.3; flags.append("unrealistically_short_sessions")

        return self._result(score, flags, data)

    def _earning_anomaly(self, user, data: dict) -> dict:
        score  = 0.0
        flags  = []
        daily_earn  = data.get("daily_earned", 0)
        avg_daily   = data.get("avg_daily_earned", 100)
        offers_completed_today = data.get("offers_completed_today", 0)

        if avg_daily > 0 and daily_earn > avg_daily * 10:
            score += 0.6; flags.append("earning_spike_10x")
        elif avg_daily > 0 and daily_earn > avg_daily * 5:
            score += 0.4; flags.append("earning_spike_5x")

        if offers_completed_today > 50:
            score += 0.4; flags.append("excessive_offer_completion")
        elif offers_completed_today > 20:
            score += 0.2; flags.append("high_offer_completion")

        return self._result(score, flags, data)

    def _click_anomaly(self, user, data: dict) -> dict:
        score  = 0.0
        flags  = []
        clicks_per_hour = data.get("clicks_per_hour", 0)
        avg_click_ms    = data.get("avg_click_interval_ms", 1000)
        unique_offers   = data.get("unique_offers_clicked", 1)

        if clicks_per_hour > 200:
            score += 0.6; flags.append("bot_speed_clicks")
        elif clicks_per_hour > 100:
            score += 0.4; flags.append("excessive_clicks")

        if avg_click_ms < 200:
            score += 0.4; flags.append("inhuman_click_speed")

        if clicks_per_hour > 50 and unique_offers <= 2:
            score += 0.3; flags.append("single_offer_spam_click")

        return self._result(score, flags, data)

    def _login_anomaly(self, user, data: dict) -> dict:
        score  = 0.0
        flags  = []
        if data.get("new_country"):     score += 0.35; flags.append("new_country_login")
        if data.get("new_device"):      score += 0.20; flags.append("new_device_login")
        if data.get("failed_attempts"): score += min(0.5, data["failed_attempts"] * 0.1); flags.append("failed_login_attempts")
        if data.get("unusual_time"):    score += 0.15; flags.append("odd_hour_login")
        if data.get("tor_detected"):    score += 0.40; flags.append("tor_login")
        return self._result(score, flags, data)

    def _withdrawal_anomaly(self, user, data: dict) -> dict:
        score  = 0.0
        flags  = []
        amount     = data.get("amount", 0)
        avg_amount = data.get("avg_withdrawal", 0)
        count_today = data.get("withdrawals_today", 0)

        if avg_amount > 0 and amount > avg_amount * 5:
            score += 0.5; flags.append("large_withdrawal_spike")
        if count_today > 3:
            score += 0.3; flags.append("multiple_withdrawals_today")
        if data.get("new_bank_account"):
            score += 0.2; flags.append("new_withdrawal_destination")
        return self._result(score, flags, data)

    def _general_anomaly(self, user, data: dict) -> dict:
        score = float(data.get("risk_score", 0.0))
        return self._result(score, [], data)

    def _result(self, score: float, flags: List[str], data: dict) -> dict:
        score = min(1.0, max(0.0, score))
        severity = "critical" if score >= 0.90 else "high" if score >= 0.70 else "medium" if score >= 0.50 else "low"
        return {
            "anomaly_score": round(score, 4),
            "is_anomaly":    score >= 0.70,
            "severity":      severity,
            "flags":         flags,
            "threshold":     0.70,
        }

    def _log_anomaly(self, user, anomaly_type: str, result: dict):
        try:
            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                anomaly_type=f"user_behavior_{anomaly_type}",
                severity=result["severity"],
                user=user,
                anomaly_score=result["anomaly_score"],
                threshold=result["threshold"],
                evidence_data={"flags": result["flags"]},
                auto_action_taken="flagged",
            )
        except Exception as e:
            logger.error(f"Anomaly log error: {e}")

    def bulk_detect(self, users_data: List[Dict],
                     anomaly_type: str = "general") -> List[Dict]:
        """Multiple users এর behavior একসাথে analyze করো।"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        results = []
        for item in users_data:
            try:
                user = User.objects.get(id=item["user_id"])
                result = self.detect(user, item.get("behavior", {}), anomaly_type)
                results.append({"user_id": item["user_id"], **result})
            except Exception as e:
                results.append({"user_id": item.get("user_id"), "error": str(e)})

        return results
