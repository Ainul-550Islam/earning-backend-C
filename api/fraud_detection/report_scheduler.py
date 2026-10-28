# =============================================================================
# fraud_detection/report_scheduler.py  — SCHEDULED REPORT DELIVERY
#
# Business purpose:
#   - Generate PDF / CSV / JSON reports on a schedule (daily/weekly/monthly)
#   - Email reports to configured recipients per organisation
#   - Support on-demand report requests via API
#   - Track report delivery status (queued / generating / delivered / failed)
# DRY: calls existing analytics.py + compliance.py + data_export.py
# =============================================================================
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    PDF  = "pdf"
    CSV  = "csv"
    JSON = "json"
    XLSX = "xlsx"


class ReportStatus(str, Enum):
    QUEUED     = "queued"
    GENERATING = "generating"
    READY      = "ready"
    DELIVERED  = "delivered"
    FAILED     = "failed"


class ReportType(str, Enum):
    DAILY_FRAUD      = "daily_fraud"
    WEEKLY_SUMMARY   = "weekly_summary"
    MONTHLY_EXEC     = "monthly_exec"
    COMPLIANCE_AML   = "compliance_aml"
    COMPLIANCE_CTR   = "compliance_ctr"
    CASE_ANALYSIS    = "case_analysis"
    CHARGEBACK       = "chargeback"
    KYC_STATUS       = "kyc_status"
    RISK_HEATMAP     = "risk_heatmap"
    CUSTOM           = "custom"


@dataclass
class ReportJob:
    report_id:   str
    report_type: str
    format:      str
    status:      ReportStatus
    recipients:  List[str] = field(default_factory=list)
    period_days: int = 7
    filters:     Dict[str, Any] = field(default_factory=dict)
    created_at:  str = field(default_factory=lambda: timezone.now().isoformat())
    completed_at: Optional[str] = None
    download_url: Optional[str] = None
    error:        Optional[str] = None


class ReportScheduler:
    """
    DRY: all report scheduling & delivery logic here.
    Celery tasks and API views delegate; no duplicate code.
    """

    _SCHEDULE = {
        ReportType.DAILY_FRAUD:    {"period_days": 1,  "format": ReportFormat.PDF},
        ReportType.WEEKLY_SUMMARY: {"period_days": 7,  "format": ReportFormat.PDF},
        ReportType.MONTHLY_EXEC:   {"period_days": 30, "format": ReportFormat.PDF},
        ReportType.COMPLIANCE_AML: {"period_days": 30, "format": ReportFormat.PDF},
        ReportType.CHARGEBACK:     {"period_days": 30, "format": ReportFormat.CSV},
        ReportType.KYC_STATUS:     {"period_days": 7,  "format": ReportFormat.CSV},
    }

    # ── Request report ─────────────────────────────────────────────────────────
    def request_report(self, report_type: str, format: str = "pdf",
                       period_days: int = 7, recipients: Optional[List[str]] = None,
                       filters: Optional[Dict] = None) -> ReportJob:
        """Enqueue a report for async generation."""
        job = ReportJob(
            report_id   = str(uuid.uuid4()),
            report_type = report_type,
            format      = format,
            status      = ReportStatus.QUEUED,
            recipients  = recipients or [],
            period_days = period_days,
            filters     = filters or {},
        )
        self._save_job(job)
        self._enqueue(job)
        logger.info("Report queued: %s type=%s format=%s", job.report_id, report_type, format)
        return job

    # ── Generate (called by Celery task) ──────────────────────────────────────
    def generate_report(self, report_id: str) -> ReportJob:
        """Generate the report data and mark as ready."""
        job = self._load_job(report_id)
        if not job:
            raise ValueError(f"Report {report_id} not found")

        job.status = ReportStatus.GENERATING
        self._save_job(job)

        try:
            data          = self._build_report_data(job)
            url           = self._render_and_store(job, data)
            job.status      = ReportStatus.READY
            job.download_url = url
            job.completed_at = timezone.now().isoformat()
            self._save_job(job)
            if job.recipients:
                self._deliver_by_email(job)
            return job
        except Exception as exc:
            job.status = ReportStatus.FAILED
            job.error  = str(exc)
            self._save_job(job)
            logger.error("Report generation failed: %s exc=%s", report_id, exc, exc_info=True)
            raise

    # ── Status ─────────────────────────────────────────────────────────────────
    def get_status(self, report_id: str) -> Optional[Dict[str, Any]]:
        job = self._load_job(report_id)
        if not job:
            return None
        return {
            "report_id":   job.report_id,
            "status":      job.status.value,
            "report_type": job.report_type,
            "format":      job.format,
            "created_at":  job.created_at,
            "completed_at":job.completed_at,
            "download_url":job.download_url,
            "error":       job.error,
        }

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent report jobs."""
        keys = cache.keys("report_job:*") if hasattr(cache, "keys") else []
        jobs = []
        for key in list(keys)[:limit]:
            raw = cache.get(key)
            if raw:
                jobs.append(raw)
        return sorted(jobs, key=lambda j: j.get("created_at", ""), reverse=True)

    # ── Scheduled run ─────────────────────────────────────────────────────────
    def run_scheduled(self, schedule_type: str) -> Dict[str, Any]:
        """Called by Celery beat — generate all reports for this schedule type."""
        cfg        = self._SCHEDULE.get(ReportType(schedule_type))
        if not cfg:
            return {"error": f"Unknown schedule type: {schedule_type!r}"}
        recipients = getattr(settings, "FRAUD_REPORT_RECIPIENTS", [])
        job        = self.request_report(
            report_type = schedule_type,
            format      = cfg["format"].value,
            period_days = cfg["period_days"],
            recipients  = recipients,
        )
        return {"report_id": job.report_id, "status": job.status.value}

    # ── Private ────────────────────────────────────────────────────────────────
    def _build_report_data(self, job: ReportJob) -> Dict[str, Any]:
        """DRY: delegates to existing services — no duplicate logic."""
        rt = job.report_type
        if rt in (ReportType.DAILY_FRAUD, ReportType.WEEKLY_SUMMARY, ReportType.MONTHLY_EXEC):
            from api.fraud_detection.analytics import FraudAnalyticsEngine
            return FraudAnalyticsEngine().generate_daily_snapshot()
        elif rt in (ReportType.COMPLIANCE_AML, ReportType.COMPLIANCE_CTR):
            from api.fraud_detection.compliance import ComplianceReportGenerator
            return ComplianceReportGenerator().generate(
                report_type=rt, period_days=job.period_days)
        elif rt == ReportType.CHARGEBACK:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            return get_chargeback_service().get_platform_chargeback_stats(job.period_days)
        elif rt == ReportType.KYC_STATUS:
            from api.fraud_detection.kyc_service import get_kyc_service
            users = get_kyc_service().get_unverified_high_risk_users(60)
            return {"unverified_high_risk": users, "period_days": job.period_days}
        else:
            return {"report_type": rt, "period_days": job.period_days, "data": {}}

    def _render_and_store(self, job: ReportJob, data: Dict) -> str:
        """Render to format and store — stub returns a placeholder URL."""
        import json
        cache.set(f"report_data:{job.report_id}", json.dumps(data, default=str),
                  timeout=86400 * 7)
        return f"/api/fraud/reports/{job.report_id}/download/"

    def _deliver_by_email(self, job: ReportJob) -> None:
        try:
            from django.core.mail import send_mail
            send_mail(
                subject = f"Fraud Report: {job.report_type} ({job.format.upper()})",
                message = f"Report {job.report_id} is ready.\n"
                          f"Download: {job.download_url}",
                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list = job.recipients,
                fail_silently  = True,
            )
            job.status = ReportStatus.DELIVERED
            self._save_job(job)
        except Exception as exc:
            logger.error("Email delivery failed for report %s: %s", job.report_id, exc)

    def _enqueue(self, job: ReportJob) -> None:
        try:
            from api.fraud_detection.tasks import generate_fraud_report
            generate_fraud_report.apply_async(
                kwargs={"report_type": job.report_type},
                task_id=job.report_id,
            )
        except Exception as exc:
            logger.warning("Could not enqueue report task: %s", exc)

    def _save_job(self, job: ReportJob) -> None:
        import dataclasses
        cache.set(f"report_job:{job.report_id}",
                  {**dataclasses.asdict(job), "status": job.status.value,
                   "format": job.format if isinstance(job.format, str) else job.format.value},
                  timeout=86400 * 30)

    def _load_job(self, report_id: str) -> Optional[ReportJob]:
        raw = cache.get(f"report_job:{report_id}")
        if not raw:
            return None
        return ReportJob(
            report_id   = raw["report_id"],
            report_type = raw["report_type"],
            format      = raw["format"],
            status      = ReportStatus(raw["status"]),
            recipients  = raw.get("recipients", []),
            period_days = raw.get("period_days", 7),
            filters     = raw.get("filters", {}),
            created_at  = raw.get("created_at", ""),
            completed_at= raw.get("completed_at"),
            download_url= raw.get("download_url"),
            error       = raw.get("error"),
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
_scheduler: Optional[ReportScheduler] = None

def get_report_scheduler() -> ReportScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ReportScheduler()
    return _scheduler
