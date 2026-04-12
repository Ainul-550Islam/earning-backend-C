"""
api/ai_engine/TESTING_EVALUATION/online_evaluator.py
=====================================================
Online Evaluator — production model real-time performance monitoring।
Live feedback loop, prediction accuracy tracking, drift alerts।
"""

import logging
from typing import Dict, List, Optional
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class OnlineEvaluator:
    """
    Production model online evaluation।
    Real-time feedback collection + accuracy monitoring।
    """

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id

    def evaluate_window(self, hours: int = 24) -> dict:
        """Rolling time window evaluation।"""
        from ..repository import PredictionLogRepository
        stats = PredictionLogRepository.get_accuracy_stats(self.ai_model_id, days=max(1, hours // 24))

        health = self._health_status(stats["accuracy"], stats["total"])
        alerts = self._generate_alerts(stats, hours)

        return {
            "ai_model_id":   self.ai_model_id,
            "window_hours":  hours,
            "accuracy":      stats["accuracy"],
            "total":         stats["total"],
            "correct":       stats["correct"],
            "health":        health,
            "alerts":        alerts,
        }

    def _health_status(self, accuracy: float, total: int) -> str:
        if total < 10:    return "insufficient_data"
        if accuracy >= 0.85: return "excellent"
        if accuracy >= 0.75: return "good"
        if accuracy >= 0.65: return "acceptable"
        if accuracy >= 0.50: return "degraded"
        return "critical"

    def _generate_alerts(self, stats: dict, hours: int) -> List[str]:
        alerts = []
        acc = stats.get("accuracy", 1.0)
        total = stats.get("total", 0)

        if acc < 0.60 and total >= 50:
            alerts.append(f"CRITICAL: Accuracy {acc:.1%} below 60% threshold")
        elif acc < 0.70 and total >= 50:
            alerts.append(f"WARNING: Accuracy {acc:.1%} below 70% target")
        if total == 0:
            alerts.append(f"INFO: No predictions in last {hours}h — model may be idle")

        return alerts

    def track_prediction_feedback(self, request_id: str,
                                   actual_outcome: str,
                                   is_correct: bool) -> dict:
        """Prediction feedback online record করো।"""
        from ..repository import PredictionLogRepository
        PredictionLogRepository.update_ground_truth(request_id, actual_outcome, is_correct)
        return {"tracked": True, "request_id": request_id, "is_correct": is_correct}

    def get_confusion_matrix(self, hours: int = 24) -> dict:
        """Prediction confusion matrix।"""
        try:
            from ..models import PredictionLog
            since = timezone.now() - timedelta(hours=hours)
            logs  = PredictionLog.objects.filter(
                ai_model_id=self.ai_model_id,
                created_at__gte=since,
                is_correct__isnull=False,
            ).values("predicted_class", "actual_outcome", "is_correct")

            matrix: Dict[str, Dict] = {}
            for log in logs:
                pred   = log["predicted_class"] or "unknown"
                actual = log["actual_outcome"] or "unknown"
                if pred not in matrix:
                    matrix[pred] = {}
                matrix[pred][actual] = matrix[pred].get(actual, 0) + 1

            return {"confusion_matrix": matrix, "hours": hours}
        except Exception as e:
            logger.error(f"Confusion matrix error: {e}")
            return {"confusion_matrix": {}, "hours": hours}

    def monitor_latency(self, threshold_ms: float = 200) -> dict:
        """Inference latency SLA monitoring।"""
        try:
            from ..models import PredictionLog
            from django.db.models import Avg, Max
            since  = timezone.now() - timedelta(hours=1)
            result = PredictionLog.objects.filter(
                ai_model_id=self.ai_model_id,
                created_at__gte=since,
            ).aggregate(avg_ms=Avg("inference_ms"), max_ms=Max("inference_ms"))

            avg_ms = round(result.get("avg_ms") or 0, 2)
            max_ms = round(result.get("max_ms") or 0, 2)

            return {
                "avg_latency_ms":   avg_ms,
                "max_latency_ms":   max_ms,
                "threshold_ms":     threshold_ms,
                "within_sla":       avg_ms <= threshold_ms,
                "sla_alert":        avg_ms > threshold_ms,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_model_performance_report(self, days: int = 7) -> dict:
        """Weekly performance report।"""
        window = self.evaluate_window(hours=days * 24)
        latency = self.monitor_latency()

        return {
            "report_period":    f"Last {days} days",
            "model_id":         self.ai_model_id,
            "accuracy":         window["accuracy"],
            "health":           window["health"],
            "avg_latency_ms":   latency.get("avg_latency_ms", 0),
            "within_latency_sla": latency.get("within_sla", True),
            "alerts":           window["alerts"],
            "recommendation":   self._report_recommendation(window, latency),
        }

    def _report_recommendation(self, window: dict, latency: dict) -> str:
        health = window.get("health", "good")
        if health in ("critical", "degraded"):
            return "Immediate retraining required. Accuracy below acceptable threshold."
        if not latency.get("within_sla", True):
            return "Optimize model for inference speed. P99 latency exceeds SLA."
        if health == "acceptable":
            return "Schedule retraining within 2 weeks. Performance trending down."
        return "Model performing well. Continue monitoring."
