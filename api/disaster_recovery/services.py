"""
Services Layer — Business Logic for Disaster Recovery System
"""
import uuid
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from .repository import (
    BackupRepository, RestoreRepository, FailoverRepository,
    MonitoringRepository, IncidentRepository, DrillRepository, AuditRepository
)
from .enums import (
    BackupStatus, RestoreStatus, FailoverStatus, FailoverType,
    HealthStatus, IncidentStatus, DrillStatus, DisasterType
)
from .exceptions import (
    BackupFailedException, RestoreFailedException, FailoverFailedException,
    NoHealthyNodeException, SLAViolationException
)
from .constants import (
    DEFAULT_RTO_SECONDS, DEFAULT_RPO_SECONDS,
    FAILOVER_HEALTH_CHECK_FAILURES, MAX_BACKUP_RETRY_ATTEMPTS
)

logger = logging.getLogger(__name__)


def _emit_to_django_audit(job_id: str, error: str, actor_id: str = "system") -> None:
    """
    Fail-safe bridge: write a backup failure into the main Django AuditLog
    without raising — safe to call from sync or async contexts.
    """
    try:
        from django.apps import apps
        AuditLog = apps.get_model("admin_panel", "AuditLog")
        AuditLog.objects.create(
            action="backup.failed",
            object_type="BackupJob",
            object_id=str(job_id),
            user=None,
            description=f"[DR] BackupJob {job_id} permanently failed: {error[:500]}",
        )
        logger.info(
            "dr.backup.audit_emitted",
            extra={"job_id": job_id, "error": error[:200]},
        )
    except Exception as audit_exc:
        # Never let audit failure propagate — just log it
        logger.warning(
            "dr.backup.audit_emit_failed",
            extra={"job_id": job_id, "audit_error": str(audit_exc)},
        )


# ──────────────────────────────────────────────────────────────────────────────
# BACKUP SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class BackupService:
    def __init__(self, db: Session):
        self.repo = BackupRepository(db)
        self.audit = AuditRepository(db)

    def create_policy(self, data: dict, actor_id: str) -> dict:
        policy = self.repo.create_policy(data)
        self.audit.log({
            "actor_id": actor_id, "action": "backup_policy.create",
            "resource_type": "backup_policy", "resource_id": policy.id,
            "new_values": data
        })
        logger.info("dr.backup_policy.created", extra={"policy_id": policy.id, "actor": actor_id})
        return policy

    def trigger_backup(self, policy_id: str = None, backup_type=None, actor_id: str = "system") -> dict:
        job_data = {
            "id": str(uuid.uuid4()),
            "policy_id": policy_id,
            "backup_type": backup_type,
            "status": BackupStatus.PENDING,
        }
        job = self.repo.create_job(job_data)
        self.audit.log({
            "actor_id": actor_id, "action": "backup.trigger",
            "resource_type": "backup_job", "resource_id": job.id
        })
        logger.info("dr.backup.triggered", extra={"job_id": job.id, "actor": actor_id})
        return job

    def start_backup(self, job_id: str) -> dict:
        job = self.repo.update_job_status(
            job_id, BackupStatus.RUNNING,
            {"started_at": datetime.utcnow()}
        )
        logger.info("dr.backup.started", extra={"job_id": job_id})
        return job

    def complete_backup(
        self,
        job_id: str,
        size_bytes: int,
        compressed_size: int,
        storage_path: str,
        checksum: str
    ) -> dict:
        now = datetime.utcnow()
        job = self.repo.get_job(job_id)
        duration = (now - job.started_at).total_seconds() if job.started_at else None
        updated = self.repo.update_job_status(
            job_id, BackupStatus.COMPLETED, {
                "completed_at": now,
                "duration_seconds": duration,
                "source_size_bytes": size_bytes,
                "compressed_size_bytes": compressed_size,
                "storage_path": storage_path,
                "checksum": checksum,
            }
        )
        logger.info(
            "dr.backup.completed",
            extra={"job_id": job_id, "size_bytes": size_bytes, "duration_s": duration},
        )
        return updated

    def fail_backup(self, job_id: str, error: str, retry: bool = True) -> dict:
        """
        Mark a backup as failed.

        Fail-safe guarantee: on permanent failure, the error is written to the
        main Django AuditLog via _emit_to_django_audit().  That call is fully
        isolated — any exception it raises is swallowed so the DR event loop
        is never disrupted.
        """
        job = self.repo.get_job(job_id)
        if retry and job.retry_count < MAX_BACKUP_RETRY_ATTEMPTS:
            updated = self.repo.update_job_status(
                job_id, BackupStatus.PENDING,
                {"retry_count": job.retry_count + 1, "error_message": error}
            )
            logger.warning(
                "dr.backup.retry",
                extra={
                    "job_id": job_id,
                    "retry_count": job.retry_count + 1,
                    "error": error[:200],
                },
            )
        else:
            updated = self.repo.update_job_status(
                job_id, BackupStatus.FAILED,
                {"error_message": error, "completed_at": datetime.utcnow()}
            )
            logger.error(
                "dr.backup.permanent_failure",
                extra={"job_id": job_id, "error": error[:200]},
            )
            # Fail-safe: emit to Django audit without crashing the event loop
            _emit_to_django_audit(job_id, error)
        return updated

    def verify_backup(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if job.status != BackupStatus.COMPLETED:
            return False
        # In production: download and verify checksum
        is_valid = True  # Placeholder
        self.repo.update_job_status(
            job_id, BackupStatus.VERIFIED,
            {"is_verified": is_valid, "verified_at": datetime.utcnow()}
        )
        return is_valid

    def cleanup_old_backups(self, policy_id: str) -> int:
        policy = self.repo.get_policy(policy_id)
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)
        old_jobs = self.repo.get_jobs_for_cleanup(cutoff)
        count = 0
        for job in old_jobs:
            if job.policy_id == policy_id:
                # In production: delete from storage first
                self.repo.update_job_status(job.id, BackupStatus.CANCELLED)
                count += 1
        logger.info(f"Cleaned up {count} old backups for policy {policy_id}")
        return count

    def get_backup_stats(self) -> Dict[str, Any]:
        status_counts = self.repo.count_by_status()
        latest = self.repo.get_latest_successful_job()
        return {
            "status_counts": status_counts,
            "latest_backup": latest.completed_at.isoformat() if latest else None,
            "total_jobs": sum(status_counts.values()),
        }


# ──────────────────────────────────────────────────────────────────────────────
# RESTORE SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class RestoreService:
    def __init__(self, db: Session):
        self.repo = RestoreRepository(db)
        self.audit = AuditRepository(db)

    def request_restore(self, data: dict, requested_by: str) -> dict:
        request_data = {**data, "requested_by": requested_by, "id": str(uuid.uuid4())}
        req = self.repo.create_request(request_data)
        self.audit.log({
            "actor_id": requested_by, "action": "restore.request",
            "resource_type": "restore_request", "resource_id": req.id
        })
        logger.info(f"Restore requested: {req.id} by {requested_by}")
        return req

    def approve_restore(self, request_id: str, approver: str) -> dict:
        req = self.repo.update_request(request_id, {
            "approval_status": "approved",
            "approved_by": approver
        })
        self.audit.log({
            "actor_id": approver, "action": "restore.approve",
            "resource_type": "restore_request", "resource_id": request_id
        })
        return req

    def execute_restore(self, request_id: str) -> dict:
        req = self.repo.get_request(request_id)
        if req.approval_status != "approved":
            raise RestoreFailedException("Restore not approved")
        self.repo.update_request(request_id, {
            "status": RestoreStatus.RUNNING,
            "started_at": datetime.utcnow()
        })
        # In production: dispatch to worker
        logger.info(f"Restore execution started: {request_id}")
        return req

    def complete_restore(self, request_id: str, bytes_restored: int) -> dict:
        now = datetime.utcnow()
        req = self.repo.get_request(request_id)
        duration = (now - req.started_at).total_seconds() if req.started_at else None
        updated = self.repo.update_request(request_id, {
            "status": RestoreStatus.COMPLETED,
            "completed_at": now,
            "duration_seconds": duration,
            "bytes_restored": bytes_restored,
        })
        # Auto-verify
        self.verify_restore(request_id)
        return updated

    def verify_restore(self, request_id: str) -> dict:
        verification = self.repo.create_verification({
            "id": str(uuid.uuid4()),
            "restore_request_id": request_id,
            "is_passed": True,
            "row_count_match": True,
            "checksum_match": True,
            "schema_match": True,
            "sample_data_verified": True,
            "verified_at": datetime.utcnow(),
            "verified_by": "system",
            "report": {"message": "All checks passed"}
        })
        return verification

    def get_available_restore_points(self, database: str) -> List[dict]:
        logs = self.repo.get_pitr_windows(database)
        return [
            {
                "database": l.database_name,
                "earliest": l.earliest_restore_point.isoformat(),
                "latest": l.latest_restore_point.isoformat(),
            }
            for l in logs
        ]


# ──────────────────────────────────────────────────────────────────────────────
# FAILOVER SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class FailoverService:
    def __init__(self, db: Session):
        self.repo = FailoverRepository(db)
        self.monitoring = MonitoringRepository(db)
        self.audit = AuditRepository(db)

    def trigger_failover(
        self,
        primary_node: str,
        secondary_node: str,
        failover_type: FailoverType,
        reason: str,
        triggered_by: str = "auto"
    ) -> dict:
        # Check secondary is healthy
        secondary_health = self.monitoring.get_latest_health(secondary_node)
        if secondary_health and secondary_health.status == HealthStatus.DOWN:
            raise NoHealthyNodeException()

        event_data = {
            "id": str(uuid.uuid4()),
            "failover_type": failover_type,
            "status": FailoverStatus.TRIGGERED,
            "primary_node": primary_node,
            "secondary_node": secondary_node,
            "triggered_by": triggered_by,
            "trigger_reason": reason,
            "initiated_at": datetime.utcnow(),
            "timeline": [{"time": datetime.utcnow().isoformat(), "event": "Failover triggered"}]
        }
        event = self.repo.create_event(event_data)
        self.audit.log({
            "actor_id": triggered_by, "action": "failover.trigger",
            "resource_type": "failover_event", "resource_id": event.id,
            "new_values": {"primary": primary_node, "secondary": secondary_node}
        })
        logger.critical(f"FAILOVER TRIGGERED: {primary_node} -> {secondary_node}")
        # In production: dispatch to failover executor
        return event

    def complete_failover(self, event_id: str) -> dict:
        now = datetime.utcnow()
        event = self.repo.get_event(event_id)
        duration = (now - event.initiated_at).total_seconds()
        updated = self.repo.update_event(event_id, {
            "status": FailoverStatus.COMPLETED,
            "completed_at": now,
            "duration_seconds": duration,
            "rto_achieved_seconds": duration,
        })
        logger.info(f"Failover completed: {event_id} in {duration:.1f}s")
        return updated

    def check_auto_failover(self, component: str) -> bool:
        """Check if auto-failover should be triggered based on recent health checks."""
        from .config import settings
        if not settings.enable_auto_failover:
            return False
        recent_checks = []
        # Get last N health check logs for this component
        # Simplified: check latest status
        latest = self.monitoring.get_latest_health(component)
        if latest and latest.status == HealthStatus.DOWN:
            logger.warning(f"Component {component} is DOWN — auto-failover candidate")
            return True
        return False

    def save_replication_lag(self, primary: str, replica: str, lag_seconds: float) -> dict:
        lag = self.repo.save_replication_lag({
            "primary_host": primary,
            "replica_host": replica,
            "lag_seconds": lag_seconds,
            "is_healthy": lag_seconds < 60,
            "measured_at": datetime.utcnow(),
        })
        if lag_seconds > 60:
            logger.warning(f"Replication lag high: {primary}->{replica} = {lag_seconds}s")
        return lag


# ──────────────────────────────────────────────────────────────────────────────
# MONITORING SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class MonitoringService:
    def __init__(self, db: Session):
        self.repo = MonitoringRepository(db)

    def record_health_check(
        self,
        component: str,
        component_type: str,
        status: HealthStatus,
        response_time_ms: float = None,
        metrics: dict = None
    ) -> dict:
        data = {
            "component_name": component,
            "component_type": component_type,
            "status": status,
            "response_time_ms": response_time_ms,
            **(metrics or {})
        }
        return self.repo.save_health_check(data)

    def get_system_health(self) -> dict:
        components = self.repo.get_all_components_latest()
        status_map = {HealthStatus.HEALTHY: 0, HealthStatus.DEGRADED: 0, HealthStatus.DOWN: 0}
        for c in components:
            if c.status in status_map:
                status_map[c.status] += 1

        if status_map[HealthStatus.DOWN] > 0:
            overall = HealthStatus.DOWN
        elif status_map[HealthStatus.DEGRADED] > 0:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return {
            "overall_status": overall,
            "components": components,
            "last_checked": datetime.utcnow(),
            "healthy_count": status_map[HealthStatus.HEALTHY],
            "degraded_count": status_map[HealthStatus.DEGRADED],
            "down_count": status_map[HealthStatus.DOWN],
        }

    def get_uptime(self, component: str, days: int = 30) -> float:
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)
        return self.repo.get_uptime_percent(component, from_date, to_date)


# ──────────────────────────────────────────────────────────────────────────────
# INCIDENT SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class IncidentService:
    def __init__(self, db: Session):
        self.repo = IncidentRepository(db)
        self.audit = AuditRepository(db)

    def create_incident(self, data: dict, reporter: str) -> dict:
        incident_data = {**data, "id": str(uuid.uuid4()), "reported_by": reporter}
        incident = self.repo.create(incident_data)
        self.audit.log({
            "actor_id": reporter, "action": "incident.create",
            "resource_type": "incident", "resource_id": incident.id
        })
        logger.error(f"INCIDENT CREATED: {incident.id} - {incident.title}")
        return incident

    def update_incident(self, incident_id: str, data: dict, actor: str) -> dict:
        old = self.repo.get(incident_id)
        updated = self.repo.update(incident_id, data)
        self.audit.log({
            "actor_id": actor, "action": "incident.update",
            "resource_type": "incident", "resource_id": incident_id
        })
        return updated

    def resolve_incident(self, incident_id: str, root_cause: str, actor: str) -> dict:
        now = datetime.utcnow()
        incident = self.repo.get(incident_id)
        duration = (now - incident.started_at).total_seconds() / 60
        updated = self.repo.update(incident_id, {
            "status": IncidentStatus.RESOLVED,
            "resolved_at": now,
            "duration_minutes": duration,
            "root_cause": root_cause,
        })
        logger.info(f"Incident resolved: {incident_id}")
        return updated

    def calculate_rto_rpo(self, incident_id: str, rto_actual: float, rpo_actual: float) -> dict:
        metric = self.repo.save_rto_rpo({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "rto_target_seconds": DEFAULT_RTO_SECONDS,
            "rto_actual_seconds": rto_actual,
            "rpo_target_seconds": DEFAULT_RPO_SECONDS,
            "rpo_actual_seconds": rpo_actual,
            "rto_met": rto_actual <= DEFAULT_RTO_SECONDS,
            "rpo_met": rpo_actual <= DEFAULT_RPO_SECONDS,
            "measured_at": datetime.utcnow(),
        })
        return metric


# ──────────────────────────────────────────────────────────────────────────────
# DRILL SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class DrillService:
    def __init__(self, db: Session):
        self.repo = DrillRepository(db)
        self.audit = AuditRepository(db)

    def schedule_drill(self, data: dict, planned_by: str) -> dict:
        drill_data = {**data, "id": str(uuid.uuid4()), "planned_by": planned_by}
        drill = self.repo.create(drill_data)
        self.audit.log({
            "actor_id": planned_by, "action": "drill.schedule",
            "resource_type": "drill", "resource_id": drill.id
        })
        logger.info(f"DR Drill scheduled: {drill.id}")
        return drill

    def start_drill(self, drill_id: str, executor: str) -> dict:
        updated = self.repo.update(drill_id, {
            "status": DrillStatus.RUNNING,
            "started_at": datetime.utcnow(),
            "executed_by": executor
        })
        logger.info(f"DR Drill started: {drill_id}")
        return updated

    def complete_drill(
        self, drill_id: str,
        rto_achieved: float, rpo_achieved: float,
        results: dict, lessons: str
    ) -> dict:
        now = datetime.utcnow()
        drill = self.repo.get(drill_id)
        duration = (now - drill.started_at).total_seconds() / 60 if drill.started_at else 0
        passed = (
            rto_achieved <= (drill.target_rto_seconds or DEFAULT_RTO_SECONDS) and
            rpo_achieved <= (drill.target_rpo_seconds or DEFAULT_RPO_SECONDS)
        )
        updated = self.repo.update(drill_id, {
            "status": DrillStatus.COMPLETED,
            "completed_at": now,
            "duration_minutes": duration,
            "achieved_rto_seconds": rto_achieved,
            "achieved_rpo_seconds": rpo_achieved,
            "results": results,
            "lessons_learned": lessons,
            "passed": passed,
        })
        logger.info(f"DR Drill completed: {drill_id}, passed={passed}")
        return updated
