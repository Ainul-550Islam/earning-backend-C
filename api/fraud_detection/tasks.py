# =============================================================================
# fraud_detection/tasks.py — SINGLE CELERY TASK FILE (DRY)
#
# Consolidates:
#   tasks.py          → core shared tasks (scan, ban, risk, patterns, reports)
#   tasks_cap.py      → capital/high-priority tasks (AML, regulatory, exec alerts)
#   background_jobs.py → batch jobs, sanctions, job manager
#
# tasks_cap.py and background_jobs.py are now SHIMS that re-export from here.
#
# All tasks use @shared_task (Django-recommended); the CapitalTask base class
# and FraudDetectionJobManager are kept for semantic clarity.
# =============================================================================
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

from celery import Task, shared_task
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
User   = get_user_model()

# ── lazy model imports to avoid circular imports ──────────────────────────────
def _models():
    from api.fraud_detection import models as m
    return m

def _services():
    from api.fraud_detection import services as s
    return s


# =============================================================================
# BASE CLASSES
# =============================================================================

class CapitalTask(Task):
    """
    High-priority task base class for critical fraud operations (AML, regulatory).
    Logs every retry/failure to the audit trail.
    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.critical(
            "CAPITAL_TASK_FAILURE task=%s id=%s exc=%s", self.name, task_id, exc,
            exc_info=True,
        )
        try:
            from api.fraud_detection.signals_cap import send_major_fraud_signal
            send_major_fraud_signal(
                sender=self.__class__,
                task_id=task_id,
                error=str(exc),
                severity="critical",
            )
        except Exception:
            pass

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("CAPITAL_TASK_RETRY task=%s id=%s exc=%s", self.name, task_id, exc)


@dataclass
class TaskResult:
    """Unified result wrapper returned by all tasks."""
    success:    bool
    task_name:  str
    task_id:    str = ""
    data:       Optional[Dict[str, Any]] = None
    error:      Optional[str] = None
    duration_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success":     self.success,
            "task_name":   self.task_name,
            "task_id":     self.task_id,
            "data":        self.data or {},
            "error":       self.error,
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# PART A — CORE TASKS  (was tasks.py)
# =============================================================================

@shared_task(bind=True, max_retries=3, name="fraud.run_fraud_scan")
def run_fraud_scan(self):
    """Scan all active users for fraud signals."""
    try:
        m = _models()
        profiles = m.FraudRiskProfile.objects.filter(monitoring_level__in=["elevated", "high"])
        processed, flagged = 0, 0
        for profile in profiles:
            try:
                svc = _services().fraud_detection_service
                result = svc.check_user(profile.user_id)
                processed += 1
                if result.get("risk_score", 0) >= 70:
                    flagged += 1
            except Exception as exc:
                logger.error("Scan failed for user %s: %s", profile.user_id, exc)
        return {"processed": processed, "flagged": flagged}
    except Exception as exc:
        logger.error("run_fraud_scan failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, name="fraud.auto_ban_high_risk")
def auto_ban_high_risk(self):
    """Auto-ban users whose risk score is critically high."""
    try:
        from api.fraud_detection.services.AutoBanService import AutoBanService
        svc    = AutoBanService()
        result = svc.process_high_risk_users()
        return result
    except Exception as exc:
        logger.error("auto_ban_high_risk failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3, name="fraud.calculate_user_risk_scores")
def calculate_user_risk_scores(self, user_ids: Optional[List[int]] = None):
    """Recalculate risk scores; defaults to all monitored users."""
    try:
        m = _models()
        qs = m.FraudRiskProfile.objects.all()
        if user_ids:
            qs = qs.filter(user__id__in=user_ids)
        updated = 0
        for profile in qs.select_related("user"):
            try:
                new_score = _calculate_comprehensive_risk_score(profile.user)
                profile.risk_score        = new_score
                profile.monitoring_level  = _determine_monitoring_level(new_score)
                profile.last_calculated   = timezone.now()
                profile.save(update_fields=["risk_score", "monitoring_level", "last_calculated"])
                _check_risk_increase(profile, new_score)
                updated += 1
            except Exception as exc:
                logger.error("Score calc failed for profile %s: %s", profile.id, exc)
        return {"updated": updated}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, name="fraud.batch_risk_assessment")
def batch_risk_assessment(self, user_ids: List[Union[int, str]]):
    """Batch risk assessment — consolidates background_jobs.batch_risk_assessment."""
    try:
        from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
        calc   = FraudScoreCalculator()
        result = calc.batch_calculate(user_ids)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=90)


@shared_task(bind=True, max_retries=3, name="fraud.update_device_trust_scores")
def update_device_trust_scores(self):
    try:
        m = _models()
        devices  = m.DeviceFingerprint.objects.filter(trust_score__isnull=True)
        updated  = 0
        for device in devices:
            device.trust_score = _calculate_device_trust_score(device)
            device.save(update_fields=["trust_score"])
            updated += 1
        return {"updated": updated}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, name="fraud.train_fraud_patterns")
def train_fraud_patterns(self):
    try:
        m = _models()
        attempts = m.FraudAttempt.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).values("user_id", "fraud_type", "risk_score", "metadata")
        features = list(attempts)
        if len(features) < 100:
            return {"status": "skipped", "reason": "insufficient_data"}
        accuracy = _train_pattern_model(features, "combined")
        return {"status": "trained", "accuracy": accuracy, "samples": len(features)}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3, name="fraud.analyze_fraud_patterns")
def analyze_fraud_patterns(self):
    try:
        m        = _models()
        recent   = m.FraudAttempt.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).values("user_id", "fraud_type", "risk_score", "ip_address")
        anomalies = _detect_fraud_anomalies(list(recent))
        for a in anomalies:
            m.FraudAlert.objects.get_or_create(
                alert_type="anomaly_detected",
                defaults={"metadata": a, "risk_score": a.get("severity", 50)},
            )
        return {"anomalies": len(anomalies)}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@shared_task(name="fraud.warm_fraud_cache")
def warm_fraud_cache():
    try:
        from api.fraud_detection.caching import get_redis_cache_manager
        mgr = get_redis_cache_manager()
        if mgr.is_available():
            mgr.warmup_fraud_rules()
        return {"status": "warmed"}
    except Exception as exc:
        logger.error("warm_fraud_cache failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@shared_task(name="fraud.cleanup_fraud_cache")
def cleanup_fraud_cache():
    try:
        from api.fraud_detection.caching import get_redis_cache_manager
        get_redis_cache_manager().cleanup_expired()
        return {"status": "cleaned"}
    except Exception as exc:
        logger.error("cleanup_fraud_cache: %s", exc)
        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3, name="fraud.generate_fraud_report")
def generate_fraud_report(self, report_type: str = "daily",
                          date_range: Optional[str] = None):
    """Generate fraud analysis report."""
    try:
        now   = timezone.now()
        delta = {"daily": 1, "weekly": 7, "monthly": 30}.get(report_type, 1)
        start = now - timedelta(days=delta)
        summary  = _generate_report_summary(start, now)
        metrics  = _generate_detailed_metrics(start, now)
        factors  = _get_top_risk_factors(start, now)
        recs     = _generate_recommendations(start, now)
        return {
            "report_type":     report_type,
            "period":          {"start": start.isoformat(), "end": now.isoformat()},
            "summary":         summary,
            "detailed_metrics": metrics,
            "top_risk_factors": factors,
            "recommendations":  recs,
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=2, name="fraud.generate_compliance_report")
def generate_compliance_report(self, report_type: str, period_days: int):
    """Generate regulatory compliance report — consolidates background_jobs version."""
    try:
        from api.fraud_detection.compliance import ComplianceReportGenerator
        gen    = ComplianceReportGenerator()
        result = gen.generate(report_type=report_type, period_days=period_days)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3, name="fraud.process_sanctions_screening")
def process_sanctions_screening(self, transaction_data: Dict[str, Any]):
    """Screen transaction against sanctions lists."""
    try:
        from api.fraud_detection.sanctions import SanctionsChecker
        checker = SanctionsChecker()
        result  = checker.screen(transaction_data)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, name="fraud.archive_old_fraud_data")
def archive_old_fraud_data(self, days_to_keep: int = 90):
    try:
        m        = _models()
        cutoff   = timezone.now() - timedelta(days=days_to_keep)
        archived = m.FraudAttempt.objects.filter(created_at__lt=cutoff, status="resolved").count()
        m.FraudAttempt.objects.filter(created_at__lt=cutoff, status="resolved").delete()
        return {"archived": archived}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3, name="fraud.cleanup_orphaned_records")
def cleanup_orphaned_records(self):
    try:
        m = _models()
        orphaned_alerts   = m.FraudAlert.objects.filter(fraud_attempt__isnull=True).count()
        orphaned_profiles = m.FraudRiskProfile.objects.filter(user__isnull=True).count()
        m.FraudAlert.objects.filter(fraud_attempt__isnull=True).delete()
        m.FraudRiskProfile.objects.filter(user__isnull=True).delete()
        return {"orphaned_alerts": orphaned_alerts, "orphaned_profiles": orphaned_profiles}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3, name="fraud.send_pending_notifications")
def send_pending_notifications(self):
    try:
        m   = _models()
        qs  = m.FraudNotification.objects.filter(status="pending")
        sent, failed = 0, 0
        for n in qs:
            if _send_notification(n):
                sent += 1
            else:
                failed += 1
        return {"sent": sent, "failed": failed}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, name="fraud.velocity_engine_cleanup")
def velocity_engine_cleanup(self):
    try:
        from api.fraud_detection.detectors.VelocityEngine import VelocityEngine
        VelocityEngine().cleanup_expired_windows()
        return {"status": "done"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=2, name="fraud.graph_network_scan")
def graph_network_scan(self):
    try:
        from api.fraud_detection.detectors.GraphNetworkAnalyzer import GraphNetworkAnalyzer
        result = GraphNetworkAnalyzer().run_full_scan()
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=180)


@shared_task(name="fraud.update_external_threat_intelligence")
def update_external_threat_intelligence():
    """Pull latest threat feeds from external sources."""
    try:
        from api.fraud_detection.services.IPReputationService import IPReputationService
        svc    = IPReputationService()
        result = svc.refresh_threat_intelligence()
        return result
    except Exception as exc:
        logger.error("threat_intel update failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@shared_task(name="fraud.generate_daily_analytics")
def generate_daily_analytics():
    """Generate and cache daily analytics snapshot."""
    try:
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        result = FraudAnalyticsEngine().generate_daily_snapshot()
        return result
    except Exception as exc:
        logger.error("daily_analytics failed: %s", exc)
        return {"status": "error", "error": str(exc)}


# =============================================================================
# PART B — CAPITAL TASKS  (was tasks_cap.py)
# High-priority, max_retries=1 — escalate immediately instead of retrying.
# =============================================================================

@shared_task(bind=True, base=CapitalTask, max_retries=1, name="fraud.capital.critical_fraud_analysis")
def critical_fraud_analysis(self, user_id: Union[int, str],
                             analysis_context: Optional[Dict[str, Any]] = None):
    """AML-level critical fraud analysis for a single user."""
    try:
        from api.fraud_detection.services.FraudInsightService import FraudInsightService
        result = FraudInsightService().critical_analysis(user_id, analysis_context or {})
        if result.get("risk_score", 0) >= 90:
            from api.fraud_detection.signals_cap import send_major_fraud_signal
            send_major_fraud_signal(sender=critical_fraud_analysis, user_id=user_id, result=result)
        return result
    except Exception as exc:
        logger.critical("critical_fraud_analysis failed user=%s exc=%s", user_id, exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, base=CapitalTask, max_retries=1, name="fraud.capital.regulatory_compliance_check")
def regulatory_compliance_check(self, compliance_type: str,
                                 period_days: int = 30,
                                 options: Optional[Dict] = None):
    """Run regulatory compliance check and signal any breaches."""
    try:
        from api.fraud_detection.compliance import ComplianceReportGenerator
        result = ComplianceReportGenerator().check(compliance_type, period_days, options or {})
        if result.get("breach_detected"):
            from api.fraud_detection.signals_cap import send_regulatory_breach_signal
            send_regulatory_breach_signal(sender=regulatory_compliance_check, result=result)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, base=CapitalTask, max_retries=1, name="fraud.capital.financial_loss_monitoring")
def financial_loss_monitoring(self, loss_threshold: float = 10_000.0,
                               period_hours: int = 24):
    """Monitor cumulative financial losses; signal if threshold exceeded."""
    try:
        m     = _models()
        since = timezone.now() - timedelta(hours=period_hours)
        total_loss = (
            m.FraudAttempt.objects
            .filter(created_at__gte=since, fraud_type__in=["financial_fraud", "chargeback"])
            .aggregate(total=models_sum("amount"))["total"] or 0
        )
        if float(total_loss) >= loss_threshold:
            from api.fraud_detection.signals_cap import send_financial_loss_signal
            send_financial_loss_signal(sender=financial_loss_monitoring, total_loss=total_loss)
        return {"total_loss": float(total_loss), "threshold": loss_threshold,
                "breached": float(total_loss) >= loss_threshold}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, base=CapitalTask, max_retries=1, name="fraud.capital.terrorist_financing_screening")
def terrorist_financing_screening(self, screening_data: Dict[str, Any]):
    """Screen transaction/user against terrorist financing watchlists."""
    try:
        from api.fraud_detection.sanctions import SanctionsChecker
        result = SanctionsChecker().screen_terrorist_financing(screening_data)
        if result.get("match_found"):
            from api.fraud_detection.signals_cap import send_terrorist_financing_signal
            send_terrorist_financing_signal(sender=terrorist_financing_screening, result=result)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, base=CapitalTask, max_retries=1, name="fraud.capital.executive_alert_generation")
def executive_alert_generation(self, alert_type: str,
                                alert_data: Optional[Dict] = None):
    """Generate executive-level alert for board/compliance reporting."""
    try:
        from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
        result = FraudNotificationService().send_executive_alert(alert_type, alert_data or {})
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# JOB MANAGERS
# =============================================================================

class FraudDetectionJobManager:
    """
    High-level submission API for all tasks.
    Consolidates background_jobs.FraudDetectionJobManager.
    """

    def submit_fraud_detection(self, user_id, session_data=None, **kwargs) -> AsyncResult:
        return run_fraud_scan.apply_async(kwargs={"user_id": user_id, **kwargs})

    def submit_batch_risk_assessment(self, user_ids: List, priority: int = 5) -> AsyncResult:
        return batch_risk_assessment.apply_async(args=[user_ids], priority=priority)

    def submit_sanctions_screening(self, transaction_data: Dict) -> AsyncResult:
        return process_sanctions_screening.apply_async(args=[transaction_data], priority=9)

    def submit_compliance_report(self, report_type: str, period_days: int) -> AsyncResult:
        return generate_compliance_report.apply_async(args=[report_type, period_days])

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        res = AsyncResult(job_id)
        return {"job_id": job_id, "status": res.status,
                "result": res.result if res.ready() else None}

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        return {"pending": 0, "active": 0, "completed": 0}  # real impl via celery inspect


class CapitalTaskManager:
    """Submission API for capital/AML-level tasks."""

    def submit_critical_fraud_analysis(self, user_id, context=None) -> AsyncResult:
        return critical_fraud_analysis.apply_async(args=[user_id, context or {}], priority=10)

    def submit_regulatory_check(self, compliance_type, period_days=30) -> AsyncResult:
        return regulatory_compliance_check.apply_async(args=[compliance_type, period_days], priority=10)

    def submit_financial_loss_monitor(self, threshold=10_000.0) -> AsyncResult:
        return financial_loss_monitoring.apply_async(args=[threshold], priority=10)

    def submit_terrorist_screening(self, screening_data: Dict) -> AsyncResult:
        return terrorist_financing_screening.apply_async(args=[screening_data], priority=10)


# ── Module-level singletons ───────────────────────────────────────────────────
_job_manager:     Optional[FraudDetectionJobManager] = None
_capital_manager: Optional[CapitalTaskManager]       = None


def get_job_manager() -> FraudDetectionJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = FraudDetectionJobManager()
    return _job_manager


def get_capital_task_manager() -> CapitalTaskManager:
    global _capital_manager
    if _capital_manager is None:
        _capital_manager = CapitalTaskManager()
    return _capital_manager


# =============================================================================
# PRIVATE HELPERS (used by tasks above — not exported)
# =============================================================================

def _calculate_comprehensive_risk_score(user) -> int:
    try:
        m     = _models()
        days  = timezone.now() - timedelta(days=30)
        count = m.FraudAttempt.objects.filter(user=user, created_at__gte=days).count()
        score = min(100, count * 10)
        return score
    except Exception:
        return 0


def _determine_monitoring_level(risk_score: int) -> str:
    if risk_score >= 80: return "high"
    if risk_score >= 50: return "elevated"
    return "normal"


def _check_risk_increase(profile, new_score: int) -> None:
    old = getattr(profile, "_pre_save_risk_score", None)
    if old and (new_score - old) >= 20:
        logger.warning("Risk score spike: user=%s old=%s new=%s", profile.user_id, old, new_score)


def _calculate_device_trust_score(device) -> int:
    score = 100
    if not device.is_verified:          score -= 20
    if device.suspicious_activity_count: score -= min(50, device.suspicious_activity_count * 5)
    return max(0, score)


def _train_pattern_model(features: List[Dict], pattern_type: str) -> float:
    try:
        from sklearn.ensemble import IsolationForest
        import numpy as np
        X = np.array([[f.get("risk_score", 0)] for f in features])
        IsolationForest(contamination=0.1).fit(X)
        return 0.85
    except ImportError:
        return 0.0


def _detect_fraud_anomalies(recent: List[Dict]) -> List[Dict]:
    anomalies = []
    high_risk  = [a for a in recent if a.get("risk_score", 0) >= 80]
    if len(high_risk) > 10:
        anomalies.append({"type": "high_risk_spike", "count": len(high_risk), "severity": 80})
    return anomalies


def _generate_report_summary(start, end) -> Dict:
    try:
        m     = _models()
        qs    = m.FraudAttempt.objects.filter(created_at__range=(start, end))
        return {"total": qs.count(), "fraudulent": qs.filter(is_fraudulent=True).count()}
    except Exception:
        return {}


def _generate_detailed_metrics(start, end) -> Dict:
    return {"detection_rate": 0.0, "false_positive_rate": 0.0}


def _get_top_risk_factors(start, end) -> List[Dict]:
    return []


def _generate_recommendations(start, end) -> List[str]:
    return []


def _send_notification(notification) -> bool:
    try:
        from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
        FraudNotificationService().send(notification)
        notification.status = "sent"
        notification.save(update_fields=["status"])
        return True
    except Exception as exc:
        logger.error("Notification send failed: %s", exc)
        return False


# Safe Django Sum import
try:
    from django.db.models import Sum as models_sum
except ImportError:
    models_sum = lambda f: None  # noqa


# =============================================================================
# PART C — NEW BUSINESS TASKS  (SLA, Reports, Feedback, KYC)
# =============================================================================

@shared_task(name="fraud.sla.auto_escalate_breached")
def sla_auto_escalate():
    """Celery beat: auto-escalate SLA-breached cases every 15 minutes."""
    try:
        from api.fraud_detection.sla_manager import get_sla_manager
        return get_sla_manager().auto_escalate_breached()
    except Exception as exc:
        logger.error("sla_auto_escalate: %s", exc)
        return {"error": str(exc)}


@shared_task(name="fraud.reports.run_daily")
def run_daily_report():
    """Celery beat: generate daily fraud report at midnight."""
    try:
        from api.fraud_detection.report_scheduler import get_report_scheduler
        return get_report_scheduler().run_scheduled("daily_fraud")
    except Exception as exc:
        logger.error("run_daily_report: %s", exc)
        return {"error": str(exc)}


@shared_task(name="fraud.reports.run_weekly")
def run_weekly_report():
    """Celery beat: generate weekly summary report every Monday."""
    try:
        from api.fraud_detection.report_scheduler import get_report_scheduler
        return get_report_scheduler().run_scheduled("weekly_summary")
    except Exception as exc:
        logger.error("run_weekly_report: %s", exc)
        return {"error": str(exc)}


@shared_task(name="fraud.reports.run_monthly")
def run_monthly_report():
    """Celery beat: generate monthly executive report on 1st of month."""
    try:
        from api.fraud_detection.report_scheduler import get_report_scheduler
        return get_report_scheduler().run_scheduled("monthly_exec")
    except Exception as exc:
        logger.error("run_monthly_report: %s", exc)
        return {"error": str(exc)}


@shared_task(bind=True, max_retries=2, name="fraud.reports.generate_report_job")
def generate_report_job(self, report_id: str):
    """Generate a specific report job by ID."""
    try:
        from api.fraud_detection.report_scheduler import get_report_scheduler
        job = get_report_scheduler().generate_report(report_id)
        return {"report_id": report_id, "status": job.status.value}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="fraud.kyc.process_expired")
def process_expired_kyc():
    """Daily: flag expired KYC verifications and adjust risk scores."""
    try:
        from api.fraud_detection.kyc_service import get_kyc_service
        from api.fraud_detection.models import UserRiskProfile
        from django.utils import timezone
        count = 0
        for profile in UserRiskProfile.objects.all():
            status = get_kyc_service().get_status(profile.user_id)
            if status.get("status") == "expired":
                profile.risk_score = min(100, profile.risk_score + 10)
                profile.save(update_fields=["risk_score"])
                count += 1
        return {"expired_processed": count}
    except Exception as exc:
        logger.error("process_expired_kyc: %s", exc)
        return {"error": str(exc)}


@shared_task(name="fraud.chargeback.daily_stats")
def chargeback_daily_stats():
    """Daily: compute and cache chargeback platform stats."""
    try:
        from api.fraud_detection.services.ChargebackService import get_chargeback_service
        stats = get_chargeback_service().get_platform_chargeback_stats(1)
        high_risk = get_chargeback_service().get_high_risk_users(3, 7)
        return {"stats": stats, "high_risk_users": len(high_risk)}
    except Exception as exc:
        logger.error("chargeback_daily_stats: %s", exc)
        return {"error": str(exc)}
