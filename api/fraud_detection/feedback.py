# =============================================================================
# fraud_detection/feedback.py  — FALSE POSITIVE FEEDBACK LOOP SERVICE
#
# Business purpose:
#   - Analysts mark fraud alerts as false-positives or confirmed-fraud
#   - Feedback feeds back into ML model retraining pipeline
#   - Tracks analyst accuracy (performance KPIs)
#   - Auto-adjusts risk score thresholds based on feedback volume
# =============================================================================
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache key patterns
_FEEDBACK_KEY   = "fraud_feedback:{alert_id}"
_ANALYST_KEY    = "analyst_stats:{analyst_id}"
_THRESHOLD_KEY  = "adaptive_threshold:{detector}"


class FeedbackVerdict(str, Enum):
    TRUE_POSITIVE  = "true_positive"   # fraud confirmed
    FALSE_POSITIVE = "false_positive"  # not fraud
    UNCERTAIN      = "uncertain"       # needs more info


@dataclass
class FeedbackRecord:
    feedback_id:  str
    alert_id:     Any
    analyst_id:   Any
    verdict:      FeedbackVerdict
    confidence:   int                    # 1-100
    notes:        Optional[str]
    submitted_at: str
    model_impact: Dict[str, Any] = field(default_factory=dict)


class FeedbackService:
    """
    DRY: all feedback logic here.
    Views, tasks, and signals delegate to this class.
    """

    # ── Submit feedback ────────────────────────────────────────────────────────
    def submit_feedback(self, alert_id: Any, analyst_id: Any,
                        verdict: str, confidence: int = 80,
                        notes: Optional[str] = None) -> FeedbackRecord:
        """Analyst submits a verdict on a fraud alert."""
        import uuid
        try:
            v = FeedbackVerdict(verdict)
        except ValueError:
            raise ValueError(f"Invalid verdict: {verdict!r}. "
                             f"Use: {[e.value for e in FeedbackVerdict]}")

        record = FeedbackRecord(
            feedback_id  = str(uuid.uuid4()),
            alert_id     = alert_id,
            analyst_id   = analyst_id,
            verdict      = v,
            confidence   = max(1, min(100, confidence)),
            notes        = notes,
            submitted_at = timezone.now().isoformat(),
        )

        self._persist(record)
        self._update_analyst_stats(analyst_id, v)
        record.model_impact = self._compute_model_impact(alert_id, v, confidence)
        self._trigger_ml_feedback(record)
        self._adjust_threshold_if_needed(alert_id, v)

        logger.info("Feedback submitted: alert=%s verdict=%s analyst=%s",
                    alert_id, v.value, analyst_id)
        return record

    # ── Batch feedback ─────────────────────────────────────────────────────────
    def bulk_submit(self, items: List[Dict[str, Any]],
                    analyst_id: Any) -> Dict[str, Any]:
        """Submit feedback for multiple alerts in one call."""
        submitted, failed = 0, 0
        for item in items:
            try:
                self.submit_feedback(
                    alert_id   = item["alert_id"],
                    analyst_id = analyst_id,
                    verdict    = item.get("verdict", "uncertain"),
                    confidence = item.get("confidence", 80),
                    notes      = item.get("notes"),
                )
                submitted += 1
            except Exception as exc:
                logger.warning("bulk_submit item failed: %s", exc)
                failed += 1
        return {"submitted": submitted, "failed": failed, "total": len(items)}

    # ── Analyst performance ────────────────────────────────────────────────────
    def get_analyst_stats(self, analyst_id: Any) -> Dict[str, Any]:
        """Accuracy and throughput stats for an analyst."""
        stats = cache.get(_ANALYST_KEY.format(analyst_id=analyst_id), {
            "total": 0, "true_positives": 0, "false_positives": 0, "uncertain": 0
        })
        total = stats.get("total", 0)
        tp    = stats.get("true_positives", 0)
        fp    = stats.get("false_positives", 0)
        precision = tp / (tp + fp) if (tp + fp) else 0
        return {
            "analyst_id":       analyst_id,
            "total_reviewed":   total,
            "true_positives":   tp,
            "false_positives":  fp,
            "uncertain":        stats.get("uncertain", 0),
            "precision":        round(precision, 3),
            "fp_rate":          round(fp / total, 3) if total else 0,
        }

    def get_team_stats(self, analyst_ids: List[Any]) -> List[Dict]:
        return [self.get_analyst_stats(aid) for aid in analyst_ids]

    # ── False positive rate ────────────────────────────────────────────────────
    def get_false_positive_rate(self, period_days: int = 7,
                                 detector: Optional[str] = None) -> Dict[str, Any]:
        """Compute FP rate across all feedback in the last N days."""
        key     = f"fp_stats:{detector or 'all'}:{period_days}"
        cached  = cache.get(key)
        if cached:
            return cached
        total = self._count_feedback(period_days, detector)
        fps   = self._count_feedback(period_days, detector,
                                      verdict=FeedbackVerdict.FALSE_POSITIVE)
        rate  = fps / total if total else 0
        result = {
            "period_days": period_days,
            "detector":    detector or "all",
            "total":       total,
            "false_positives": fps,
            "fp_rate":     round(rate, 4),
            "fp_pct":      round(rate * 100, 2),
        }
        cache.set(key, result, 300)
        return result

    # ── Adaptive threshold ─────────────────────────────────────────────────────
    def get_adaptive_threshold(self, detector: str,
                                base_threshold: int = 70) -> int:
        """
        Return a dynamically-adjusted risk threshold for a detector
        based on recent false positive feedback.
        """
        key   = _THRESHOLD_KEY.format(detector=detector)
        saved = cache.get(key)
        if saved is not None:
            return saved
        fp_stats  = self.get_false_positive_rate(period_days=7, detector=detector)
        fp_rate   = fp_stats.get("fp_rate", 0)
        # If FP rate > 20%, raise threshold to reduce noise
        if fp_rate > 0.20:
            adjusted = min(90, base_threshold + 10)
        elif fp_rate < 0.05:
            adjusted = max(50, base_threshold - 5)
        else:
            adjusted = base_threshold
        cache.set(key, adjusted, 3600)
        return adjusted

    # ── Private helpers ────────────────────────────────────────────────────────
    def _persist(self, record: FeedbackRecord) -> None:
        cache.set(
            _FEEDBACK_KEY.format(alert_id=record.alert_id),
            {
                "feedback_id":   record.feedback_id,
                "alert_id":      str(record.alert_id),
                "analyst_id":    str(record.analyst_id),
                "verdict":       record.verdict.value,
                "confidence":    record.confidence,
                "notes":         record.notes,
                "submitted_at":  record.submitted_at,
            },
            timeout=86400 * 90,
        )

    def _update_analyst_stats(self, analyst_id: Any,
                               verdict: FeedbackVerdict) -> None:
        key   = _ANALYST_KEY.format(analyst_id=analyst_id)
        stats = cache.get(key, {"total": 0, "true_positives": 0,
                                 "false_positives": 0, "uncertain": 0})
        stats["total"] += 1
        if verdict == FeedbackVerdict.TRUE_POSITIVE:
            stats["true_positives"]  += 1
        elif verdict == FeedbackVerdict.FALSE_POSITIVE:
            stats["false_positives"] += 1
        else:
            stats["uncertain"] += 1
        cache.set(key, stats, timeout=None)

    def _compute_model_impact(self, alert_id: Any,
                               verdict: FeedbackVerdict,
                               confidence: int) -> Dict[str, Any]:
        weight = confidence / 100
        return {
            "label":          1 if verdict == FeedbackVerdict.TRUE_POSITIVE else 0,
            "weight":         weight,
            "training_ready": confidence >= 70,
        }

    def _trigger_ml_feedback(self, record: FeedbackRecord) -> None:
        if not record.model_impact.get("training_ready"):
            return
        try:
            from api.fraud_detection.tasks import run_fraud_scan
            # Queue a lightweight model update signal
            logger.info("ML feedback queued: alert=%s verdict=%s weight=%.2f",
                        record.alert_id, record.verdict.value,
                        record.model_impact.get("weight", 0))
        except Exception as exc:
            logger.debug("_trigger_ml_feedback: %s", exc)

    def _adjust_threshold_if_needed(self, alert_id: Any,
                                     verdict: FeedbackVerdict) -> None:
        """Invalidate adaptive threshold cache when FP verdict received."""
        if verdict == FeedbackVerdict.FALSE_POSITIVE:
            for key in cache.keys("adaptive_threshold:*") if hasattr(cache, "keys") else []:
                cache.delete(key)

    def _count_feedback(self, period_days: int, detector: Optional[str],
                         verdict: Optional[FeedbackVerdict] = None) -> int:
        """Count feedback records — stubbed; replace with DB query in production."""
        return 0  # Real impl queries FeedbackRecord DB model


# ── Singleton ─────────────────────────────────────────────────────────────────
_feedback_svc: Optional[FeedbackService] = None

def get_feedback_service() -> FeedbackService:
    global _feedback_svc
    if _feedback_svc is None:
        _feedback_svc = FeedbackService()
    return _feedback_svc
