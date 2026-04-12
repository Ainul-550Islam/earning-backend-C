"""
api/ai_engine/TESTING_EVALUATION/canary_testing.py
====================================================
Canary Testing — gradual model rollout with monitoring।
Automatic rollback on degradation detection।
Zero-downtime production model updates।
"""
import logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)

class CanaryTester:
    """Gradual model rollout with automatic rollback।"""

    DEFAULT_CANARY_PCT  = 0.05   # 5% initial traffic
    ROLLBACK_THRESHOLD  = 0.10   # 10% accuracy drop triggers rollback
    MAX_CANARY_PCT      = 1.0    # 100% = full rollout

    def run_canary(self, new_model_id: str,
                   prod_model_id: str = None,
                   canary_pct: float = None,
                   monitoring_hours: int = 24) -> dict:
        canary_pct = canary_pct or self.DEFAULT_CANARY_PCT
        from ..ML_PIPELINES.monitoring_pipeline import MonitoringPipeline

        monitor = MonitoringPipeline(new_model_id if hasattr(MonitoringPipeline, "__init__") else None)
        try:
            metrics = monitor.run(new_model_id)
        except Exception:
            metrics = {"health": "unknown"}

        health = metrics.get("health", "unknown")
        if health in ("critical", "unhealthy"):
            return {
                "status":      "rollback",
                "reason":      f"Health check failed: {health}",
                "canary_pct":  canary_pct,
                "next_action": "investigate_and_fix",
                "metrics":     metrics,
            }

        # Gradual ramp-up strategy
        if canary_pct >= self.MAX_CANARY_PCT:
            return {
                "status":          "full_rollout_complete",
                "canary_pct":      1.0,
                "new_model_id":    new_model_id,
                "recommendation":  "Decommission old model",
            }

        next_pct = min(canary_pct * 2, self.MAX_CANARY_PCT)
        return {
            "status":                "proceed",
            "current_canary_pct":    canary_pct,
            "next_canary_pct":       next_pct,
            "ready_for_full_rollout": next_pct >= self.MAX_CANARY_PCT,
            "monitoring_hours":       monitoring_hours,
            "metrics":               metrics,
            "recommendation":         f"Increase traffic to {next_pct:.0%} after {monitoring_hours}h",
        }

    def rollback(self, current_model_id: str,
                 stable_model_id: str) -> dict:
        """Rollback to stable model।"""
        try:
            from ..models import AIModel
            AIModel.objects.filter(id=current_model_id).update(status="deprecated")
            AIModel.objects.filter(id=stable_model_id).update(status="deployed")
            logger.warning(f"ROLLBACK: {current_model_id} → {stable_model_id}")
            return {
                "rolled_back_from": current_model_id,
                "rolled_back_to":   stable_model_id,
                "status":           "rollback_complete",
            }
        except Exception as e:
            return {"error": str(e), "status": "rollback_failed"}

    def detect_degradation(self, baseline_metrics: dict,
                            current_metrics: dict,
                            threshold: float = None) -> dict:
        threshold = threshold or self.ROLLBACK_THRESHOLD
        baseline_acc = float(baseline_metrics.get("accuracy", 1.0))
        current_acc  = float(current_metrics.get("accuracy", 1.0))
        degradation  = (baseline_acc - current_acc) / max(baseline_acc, 0.001)
        return {
            "degraded":          degradation >= threshold,
            "degradation_pct":   round(degradation * 100, 2),
            "threshold_pct":     round(threshold * 100, 2),
            "baseline_accuracy": baseline_acc,
            "current_accuracy":  current_acc,
            "action":            "rollback" if degradation >= threshold else "continue",
        }

    def traffic_split(self, user_id: str, canary_pct: float) -> str:
        """User কে canary বা production model assign করো।"""
        import hashlib
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
        pct      = (hash_val % 10000) / 10000.0
        return "canary" if pct < canary_pct else "production"

    def canary_schedule(self, total_hours: int = 168) -> list:
        """7-day progressive rollout schedule।"""
        schedule = []
        pcts = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 1.00]
        per_step = total_hours / len(pcts)
        for i, pct in enumerate(pcts):
            schedule.append({
                "hour":       int(i * per_step),
                "canary_pct": pct,
                "description": f"{pct:.0%} traffic to new model",
            })
        return schedule
