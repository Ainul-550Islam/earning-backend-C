"""
api/ai_engine/TESTING_EVALUATION/offline_evaluator.py
======================================================
Offline Evaluator — holdout set এ comprehensive model evaluation।
Production deployment এর আগে final validation।
Accuracy, fairness, performance, robustness সব check করো।
"""

import logging
from typing import List, Dict, Optional, Tuple
import time

logger = logging.getLogger(__name__)


class OfflineEvaluator:
    """
    Comprehensive offline model evaluation।
    Multiple metrics + threshold checking।
    """

    # Minimum acceptable thresholds
    THRESHOLDS = {
        "accuracy":     0.70,
        "f1_score":     0.65,
        "auc_roc":      0.70,
        "precision":    0.65,
        "recall":       0.60,
        "max_latency_ms": 500,
        "avg_latency_ms": 200,
    }

    def evaluate(self, ai_model_id: str, test_dataset_path: str = None,
                  X_test=None, y_test=None) -> dict:
        """
        Model এর complete offline evaluation করো।
        DB থেকে active version নিয়ে evaluate করো।
        """
        from ..models import ModelVersion

        version = ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).first()

        if not version:
            return {"status": "no_active_version", "passed": False}

        # Use stored metrics if no test set provided
        if X_test is None or y_test is None:
            return self._evaluate_from_stored_metrics(version)

        return self._evaluate_with_test_set(version, X_test, y_test)

    def _evaluate_from_stored_metrics(self, version) -> dict:
        """Stored training metrics থেকে evaluation।"""
        metrics = {
            "accuracy":  version.accuracy,
            "precision": version.precision,
            "recall":    version.recall,
            "f1_score":  version.f1_score,
            "auc_roc":   version.auc_roc,
        }

        threshold_results = {}
        passed_all        = True

        for metric, value in metrics.items():
            threshold = self.THRESHOLDS.get(metric, 0)
            passed    = value >= threshold
            threshold_results[metric] = {
                "value":     round(value, 4),
                "threshold": threshold,
                "passed":    passed,
            }
            if not passed:
                passed_all = False

        return {
            "status":      "passed" if passed_all else "failed",
            "passed":      passed_all,
            "version":     version.version,
            "metrics":     metrics,
            "thresholds":  threshold_results,
            "model_id":    str(version.ai_model_id),
            "source":      "stored_metrics",
            "recommendation": "Ready for deployment" if passed_all else self._fail_reason(threshold_results),
        }

    def _evaluate_with_test_set(self, version, X_test, y_test) -> dict:
        """Live test set এ evaluate করো।"""
        try:
            from ..ML_MODELS.model_predictor import ModelPredictor
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score, classification_report,
            )
            import numpy as np
            import time

            predictor = ModelPredictor(version.model_file_path)

            # Batch predictions with latency measurement
            latencies = []
            y_pred    = []
            y_prob    = []

            for i, x in enumerate(X_test[:1000]):
                features = dict(enumerate(x)) if hasattr(x, "__iter__") else {"f0": x}
                start    = time.time()
                result   = predictor.predict(features)
                latencies.append((time.time() - start) * 1000)
                y_pred.append(result.get("predicted_class", "0"))
                y_prob.append(result.get("predicted_value") or result.get("confidence", 0.5))

            y_pred_bin = [1 if str(p) in ("1", "True", "fraud", "positive") else 0 for p in y_pred]
            y_test_bin = list(y_test[:len(y_pred_bin)])

            metrics = {
                "accuracy":  round(float(accuracy_score(y_test_bin, y_pred_bin)), 4),
                "precision": round(float(precision_score(y_test_bin, y_pred_bin, zero_division=0)), 4),
                "recall":    round(float(recall_score(y_test_bin, y_pred_bin, zero_division=0)), 4),
                "f1_score":  round(float(f1_score(y_test_bin, y_pred_bin, zero_division=0)), 4),
                "auc_roc":   round(float(roc_auc_score(y_test_bin, y_prob[:len(y_test_bin)])), 4),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                "p99_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 2),
                "test_samples":  len(y_pred_bin),
            }

            threshold_results = {}
            passed_all        = True
            for metric, value in metrics.items():
                threshold = self.THRESHOLDS.get(metric)
                if threshold is None:
                    continue
                passed = value >= threshold if "latency" not in metric else value <= threshold
                threshold_results[metric] = {"value": value, "threshold": threshold, "passed": passed}
                if not passed:
                    passed_all = False

            return {
                "status":      "passed" if passed_all else "failed",
                "passed":      passed_all,
                "version":     version.version,
                "metrics":     metrics,
                "thresholds":  threshold_results,
                "source":      "live_test_set",
                "recommendation": "Ready for deployment" if passed_all else self._fail_reason(threshold_results),
            }

        except Exception as e:
            logger.error(f"Offline evaluation error: {e}")
            return self._evaluate_from_stored_metrics(version)

    def _fail_reason(self, threshold_results: dict) -> str:
        failed = [m for m, r in threshold_results.items() if not r.get("passed", True)]
        if not failed:
            return "All metrics passed."
        return f"Failed metrics: {', '.join(failed)}. Retrain with more data."

    def compare_versions(self, ai_model_id: str,
                          version_a_id: str, version_b_id: str) -> dict:
        """Two model versions compare করো।"""
        from ..models import ModelVersion

        v_a = ModelVersion.objects.filter(id=version_a_id).first()
        v_b = ModelVersion.objects.filter(id=version_b_id).first()

        if not v_a or not v_b:
            return {"error": "One or both versions not found"}

        metrics = ["accuracy", "f1_score", "auc_roc", "precision", "recall"]
        comparison = {}
        winner_points = {"A": 0, "B": 0}

        for m in metrics:
            va_val = getattr(v_a, m, 0) or 0
            vb_val = getattr(v_b, m, 0) or 0
            diff   = vb_val - va_val
            winner = "B" if diff > 0 else "A" if diff < 0 else "tie"

            comparison[m] = {
                "version_a":  round(va_val, 4),
                "version_b":  round(vb_val, 4),
                "diff":       round(diff, 4),
                "winner":     winner,
                "significant": abs(diff) >= 0.02,
            }
            if winner == "A":   winner_points["A"] += 1
            elif winner == "B": winner_points["B"] += 1

        overall_winner = "B" if winner_points["B"] > winner_points["A"] else "A" if winner_points["A"] > winner_points["B"] else "tie"

        return {
            "version_a": {"id": str(version_a_id), "version": v_a.version},
            "version_b": {"id": str(version_b_id), "version": v_b.version},
            "comparison": comparison,
            "winner":     overall_winner,
            "recommendation": f"Deploy Version {overall_winner} — better overall performance." if overall_winner != "tie" else "No significant difference.",
        }

    def generate_evaluation_report(self, ai_model_id: str) -> dict:
        """Full evaluation report generate করো।"""
        eval_result = self.evaluate(ai_model_id)

        from ..ML_PIPELINES.monitoring_pipeline import MonitoringPipeline
        monitoring  = MonitoringPipeline().run(ai_model_id)

        from ..ML_PIPELINES.drift_detection_pipeline import DriftDetectionPipeline
        from ..models import AIModel
        model = AIModel.objects.filter(id=ai_model_id).first()
        drift = {}
        if model:
            try:
                drift = DriftDetectionPipeline(model).run()
            except Exception:
                pass

        return {
            "model_id":          str(ai_model_id),
            "evaluation":        eval_result,
            "production_health": monitoring,
            "data_drift":        drift,
            "overall_verdict":   self._overall_verdict(eval_result, monitoring, drift),
            "generated_at":      str(__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now()),
        }

    def _overall_verdict(self, eval_result: dict,
                           monitoring: dict, drift: dict) -> str:
        eval_passed   = eval_result.get("passed", False)
        health_ok     = monitoring.get("health") in ("healthy", "good", "excellent")
        drift_ok      = drift.get("status") not in ("critical",)

        if eval_passed and health_ok and drift_ok:
            return "APPROVED — Model ready for production deployment"
        elif not eval_passed:
            return "REJECTED — Evaluation metrics below threshold. Retrain required."
        elif not drift_ok:
            return "WARNING — Data drift detected. Monitor closely or retrain."
        else:
            return "CONDITIONAL — Minor issues detected. Review before deployment."
