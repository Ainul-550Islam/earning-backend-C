"""
DR Dashboard — Real-time disaster recovery status dashboard data.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DRDashboard:
    """
    Provides aggregated data for the DR monitoring dashboard.
    Combines backup, restore, failover, health, and SLA metrics
    into a single unified view.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        to_date = to_date or datetime.utcnow()
        from_date = from_date or (to_date - timedelta(hours=24))
        return {
            "report_type": "dr_dashboard",
            "dashboard_time": datetime.utcnow().isoformat(),
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "system_health": self._get_system_health(),
            "backup_summary": self._get_backup_summary(from_date, to_date),
            "replication_status": self._get_replication_status(),
            "recent_incidents": self._get_recent_incidents(),
            "sla_status": self._get_sla_status(),
            "rto_rpo_compliance": self._get_rto_rpo_compliance(),
            "alerts": self._get_active_alerts(),
        }

    def _get_system_health(self) -> dict:
        if not self.db:
            return {"overall": "healthy", "components": {}, "note": "No DB session"}
        from ..repository import MonitoringRepository
        from ..enums import HealthStatus
        repo = MonitoringRepository(self.db)
        components = repo.get_all_components_latest()
        status_map = {}
        down_count = 0
        degraded_count = 0
        for comp in components:
            status_val = comp.status.value if hasattr(comp.status, "value") else str(comp.status)
            status_map[comp.component_name] = {
                "status": status_val,
                "response_time_ms": comp.response_time_ms,
                "checked_at": comp.checked_at.isoformat(),
            }
            if comp.status == HealthStatus.DOWN:
                down_count += 1
            elif comp.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                degraded_count += 1
        overall = "healthy"
        if down_count > 0:
            overall = "down"
        elif degraded_count > 0:
            overall = "degraded"
        return {
            "overall": overall,
            "components": status_map,
            "down_count": down_count,
            "degraded_count": degraded_count,
        }

    def _get_backup_summary(self, from_date: datetime, to_date: datetime) -> dict:
        if not self.db:
            return {"total": 0, "success_rate": 100.0}
        from ..sa_models import BackupJob
        from ..enums import BackupStatus
        from sqlalchemy import and_
        jobs = self.db.query(BackupJob).filter(
            and_(BackupJob.created_at >= from_date, BackupJob.created_at <= to_date)
        ).all()
        total = len(jobs)
        completed = sum(1 for j in jobs if j.status == BackupStatus.COMPLETED)
        return {
            "total": total,
            "completed": completed,
            "failed": total - completed,
            "success_rate": round(completed / max(total, 1) * 100, 1),
        }

    def _get_replication_status(self) -> dict:
        if not self.db:
            return {"replicas": [], "avg_lag_seconds": 0}
        from ..sa_models import ReplicationLag
        from sqlalchemy import desc
        recent_lags = self.db.query(ReplicationLag).order_by(
            desc(ReplicationLag.measured_at)
        ).limit(10).all()
        replicas = []
        for lag in recent_lags:
            replicas.append({
                "replica": lag.replica_host,
                "lag_seconds": lag.lag_seconds,
                "healthy": lag.is_healthy,
            })
        avg_lag = sum(r["lag_seconds"] for r in replicas) / max(len(replicas), 1)
        return {"replicas": replicas, "avg_lag_seconds": round(avg_lag, 2)}

    def _get_recent_incidents(self) -> list:
        if not self.db:
            return []
        from ..sa_models import IncidentReport
        from ..enums import IncidentStatus
        from sqlalchemy import desc
        open_incidents = self.db.query(IncidentReport).filter(
            IncidentReport.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.CLOSED])
        ).order_by(desc(IncidentReport.started_at)).limit(5).all()
        return [
            {"id": i.id[:8], "title": i.title[:80],
             "severity": i.severity.value, "status": i.status.value}
            for i in open_incidents
        ]

    def _get_sla_status(self) -> dict:
        if not self.db:
            return {"overall_uptime_percent": 99.9, "sla_met": True}
        from ..repository import MonitoringRepository
        repo = MonitoringRepository(self.db)
        from_date = datetime.utcnow() - timedelta(days=30)
        to_date = datetime.utcnow()
        uptime = repo.get_uptime_percent("api-server", from_date, to_date)
        return {
            "service": "api-server",
            "uptime_percent": uptime,
            "target_percent": 99.9,
            "sla_met": uptime >= 99.9,
        }

    def _get_rto_rpo_compliance(self) -> dict:
        if not self.db:
            return {"rto_met_percent": 100.0, "rpo_met_percent": 100.0}
        from ..sa_models import RTO_RPO_Metric
        metrics = self.db.query(RTO_RPO_Metric).all()
        if not metrics:
            return {"rto_met_percent": 100.0, "rpo_met_percent": 100.0, "samples": 0}
        rto_met = sum(1 for m in metrics if m.rto_met)
        rpo_met = sum(1 for m in metrics if m.rpo_met)
        return {
            "samples": len(metrics),
            "rto_met_percent": round(rto_met / len(metrics) * 100, 1),
            "rpo_met_percent": round(rpo_met / len(metrics) * 100, 1),
        }

    def _get_active_alerts(self) -> list:
        return []
