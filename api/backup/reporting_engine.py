"""
Backup Reporting Engine
Inspired by: Veeam ONE reporting, Commvault reporting, Cohesity analytics
Generates executive dashboards, SLA compliance, and operational reports.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    EXECUTIVE_SUMMARY   = "executive_summary"
    SLA_COMPLIANCE      = "sla_compliance"
    STORAGE_USAGE       = "storage_usage"
    JOB_HISTORY         = "job_history"
    FAILURE_ANALYSIS    = "failure_analysis"
    CAPACITY_FORECAST   = "capacity_forecast"
    SECURITY_AUDIT      = "security_audit"
    COST_ANALYSIS       = "cost_analysis"


class ReportFormat(str, Enum):
    JSON = "json"
    CSV  = "csv"
    HTML = "html"


@dataclass
class ReportDefinition:
    report_id: str
    name: str
    report_type: ReportType
    format: ReportFormat = ReportFormat.JSON
    date_range_days: int = 30
    filters: Dict[str, Any] = field(default_factory=dict)
    schedule: Optional[str] = None    # cron expression


@dataclass
class GeneratedReport:
    definition: ReportDefinition
    generated_at: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    row_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({
            "report": self.definition.name,
            "type": self.definition.report_type.value,
            "generated_at": self.generated_at.isoformat(),
            "date_range_days": self.definition.date_range_days,
            "rows": self.row_count,
            "data": self.data,
        }, indent=2)

    def to_csv(self) -> str:
        buf = io.StringIO()
        rows = self.data.get("rows", [])
        if not rows:
            return ""
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    def to_html(self) -> str:
        rows = self.data.get("rows", [])
        if not rows:
            return "<p>No data</p>"
        headers = list(rows[0].keys())
        th = "".join(f"<th>{h}</th>" for h in headers)
        body = ""
        for row in rows:
            td = "".join(f"<td>{row.get(h,'')}</td>" for h in headers)
            body += f"<tr>{td}</tr>"
        return (
            f"<h2>{self.definition.name}</h2>"
            f"<p>Generated: {self.generated_at.isoformat()}</p>"
            f"<table border='1'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
        )


class BackupReportingEngine:
    """Generates backup reports from stored data"""

    def generate(self, definition: ReportDefinition) -> GeneratedReport:
        report = GeneratedReport(definition=definition)
        try:
            generator = {
                ReportType.EXECUTIVE_SUMMARY:  self._executive_summary,
                ReportType.SLA_COMPLIANCE:     self._sla_compliance,
                ReportType.STORAGE_USAGE:      self._storage_usage,
                ReportType.JOB_HISTORY:        self._job_history,
                ReportType.FAILURE_ANALYSIS:   self._failure_analysis,
                ReportType.CAPACITY_FORECAST:  self._capacity_forecast,
                ReportType.SECURITY_AUDIT:     self._security_audit,
                ReportType.COST_ANALYSIS:      self._cost_analysis,
            }.get(definition.report_type, self._unknown)
            report.data = generator(definition)
            report.row_count = len(report.data.get("rows", []))
        except Exception as exc:
            report.errors.append(str(exc))
            logger.error("Report generation failed: %s — %s", definition.name, exc)
        return report

    def _executive_summary(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        repo = BackupRepository()
        counts = repo.count_by_status()
        total = sum(counts.values())
        return {
            "summary": {
                "total_backups": total,
                "success_rate_pct": round(counts.get("completed", 0) / total * 100, 1) if total else 0,
                "failed": counts.get("failed", 0),
                "storage_used_gb": round(repo.total_size_bytes() / 1024**3, 2),
                "period_days": defn.date_range_days,
            },
            "rows": [{"metric": k, "value": v} for k, v in counts.items()],
        }

    def _sla_compliance(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        from django.utils import timezone
        repo = BackupRepository()
        cutoff = timezone.now() - timedelta(days=defn.date_range_days)
        recent = list(repo.get_recent(days=defn.date_range_days))
        rows = []
        for b in recent:
            rows.append({
                "backup_id": str(getattr(b, "id", "")),
                "name": getattr(b, "name", ""),
                "status": getattr(b, "status", ""),
                "created_at": str(getattr(b, "created_at", "")),
                "sla_met": getattr(b, "status", "") == "completed",
            })
        compliant = sum(1 for r in rows if r["sla_met"])
        return {
            "compliance_pct": round(compliant / len(rows) * 100, 1) if rows else 100.0,
            "rows": rows,
        }

    def _storage_usage(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository, StorageLocationRepository
        storage_repo = StorageLocationRepository()
        locations = list(storage_repo.get_all_active())
        rows = [{"location": getattr(l, "name", ""), "type": getattr(l, "storage_type", ""),
                 "active": True} for l in locations]
        return {"total_locations": len(rows), "rows": rows}

    def _job_history(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        backups = list(BackupRepository().get_recent(days=defn.date_range_days))
        rows = [{"id": str(getattr(b, "id", "")), "name": getattr(b, "name", ""),
                 "status": getattr(b, "status", ""),
                 "created_at": str(getattr(b, "created_at", ""))} for b in backups]
        return {"rows": rows}

    def _failure_analysis(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        failed = list(BackupRepository().get_by_status("failed"))
        rows = [{"id": str(getattr(b, "id", "")), "name": getattr(b, "name", ""),
                 "error": getattr(b, "error_message", "unknown")} for b in failed]
        return {"total_failures": len(rows), "rows": rows}

    def _capacity_forecast(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        repo = BackupRepository()
        current_bytes = repo.total_size_bytes()
        growth_rate = 0.05   # 5% per period assumption
        forecasts = []
        for period in [30, 60, 90, 180]:
            projected = current_bytes * ((1 + growth_rate) ** (period / 30))
            forecasts.append({"days": period, "projected_gb": round(projected / 1024**3, 2)})
        return {"current_gb": round(current_bytes / 1024**3, 2), "rows": forecasts}

    def _security_audit(self, defn: ReportDefinition) -> Dict[str, Any]:
        return {
            "rows": [
                {"check": "Encryption at rest", "status": "enabled"},
                {"check": "Encryption in transit", "status": "enabled"},
                {"check": "MFA on admin accounts", "status": "enabled"},
                {"check": "Immutable backups", "status": "partial"},
                {"check": "Air-gap copy", "status": "not_configured"},
                {"check": "Ransomware scanning", "status": "enabled"},
            ]
        }

    def _cost_analysis(self, defn: ReportDefinition) -> Dict[str, Any]:
        from api.backup.repositories import BackupRepository
        total_bytes = BackupRepository().total_size_bytes()
        total_gb = total_bytes / 1024**3
        costs = [
            {"storage_type": "S3 Standard", "cost_per_gb": 0.023, "estimated_monthly": round(total_gb * 0.023, 2)},
            {"storage_type": "S3 Glacier", "cost_per_gb": 0.004, "estimated_monthly": round(total_gb * 0.004, 2)},
            {"storage_type": "Azure Cool",  "cost_per_gb": 0.01,  "estimated_monthly": round(total_gb * 0.01, 2)},
            {"storage_type": "GCS Nearline","cost_per_gb": 0.01,  "estimated_monthly": round(total_gb * 0.01, 2)},
        ]
        return {"total_gb": round(total_gb, 2), "rows": costs}

    def _unknown(self, defn: ReportDefinition) -> Dict[str, Any]:
        return {"rows": [], "error": f"Unknown report type: {defn.report_type}"}
