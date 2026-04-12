"""
Restore Validator — Validates restore requests before execution.
"""
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


class RestoreValidator:
    """
    Pre-restore validation engine. Validates requests for completeness,
    backup integrity, target availability, approvals, and conflict detection.
    """

    def __init__(self, db_session=None, config: dict = None):
        self.db = db_session
        self.config = config or {}
        self.require_approval = config.get("require_approval", True) if config else True

    def validate(self, request: dict) -> dict:
        """Validate a restore request. Returns dict with valid, errors, warnings."""
        errors = []
        warnings = []
        errors.extend(self._check_required_fields(request))
        errors.extend(self._check_source(request))
        if self.require_approval:
            errors.extend(self._check_approval(request))
        warnings.extend(self._check_resources(request))
        errors.extend(self._check_conflicts(request))
        if request.get("restore_type") == "point_in_time":
            errors.extend(self._check_pitr(request))
        return {"valid": len(errors) == 0, "errors": [e["message"] for e in errors],
                "warnings": [w["message"] for w in warnings],
                "error_count": len(errors), "warning_count": len(warnings),
                "blocking_errors": [e["message"] for e in errors],
                "validated_at": datetime.utcnow().isoformat()}

    def validate_backup_integrity(self, backup_id: str) -> dict:
        """Validate a backup's integrity."""
        if not self.db: return {"valid": True, "backup_id": backup_id}
        from ..sa_models import BackupJob
        from ..enums import BackupStatus
        job = self.db.query(BackupJob).filter(BackupJob.id == backup_id).first()
        if not job: return {"valid": False, "error": f"Backup not found: {backup_id}"}
        checks = [
            {"check": "status", "passed": job.status == BackupStatus.COMPLETED},
            {"check": "verified", "passed": job.is_verified or False},
            {"check": "checksum", "passed": bool(job.checksum)},
        ]
        return {"valid": all(c["passed"] for c in checks), "backup_id": backup_id,
                "checks": checks, "backup_size_bytes": job.source_size_bytes}

    def validate_pitr_feasibility(self, database: str, target_time: datetime,
                                   wal_archive_path: str = None) -> dict:
        """Validate that PITR is feasible."""
        if not self.db: return {"feasible": True, "note": "Dev mode"}
        from ..sa_models import PointInTimeLog
        from sqlalchemy import and_
        window = self.db.query(PointInTimeLog).filter(
            and_(PointInTimeLog.database_name == database,
                 PointInTimeLog.is_available == True,
                 PointInTimeLog.earliest_restore_point <= target_time,
                 PointInTimeLog.latest_restore_point >= target_time)).first()
        if not window:
            return {"feasible": False, "database": database,
                    "reason": "No PITR window covers the requested time"}
        return {"feasible": True, "database": database,
                "available_from": window.earliest_restore_point.isoformat(),
                "available_to": window.latest_restore_point.isoformat()}

    def _check_required_fields(self, request: dict) -> list:
        errors = []
        rt = request.get("restore_type")
        if not rt:
            errors.append({"code": "MISSING_RESTORE_TYPE", "message": "restore_type is required (full|partial|table|point_in_time)"})
        elif rt not in ("full", "partial", "table", "point_in_time"):
            errors.append({"code": "INVALID_RESTORE_TYPE", "message": f"Invalid restore_type: {rt}"})
        if not request.get("backup_job_id") and rt != "point_in_time":
            errors.append({"code": "MISSING_SOURCE", "message": "backup_job_id is required"})
        if rt == "point_in_time" and not request.get("point_in_time"):
            errors.append({"code": "MISSING_PITR_TIMESTAMP", "message": "point_in_time is required for PITR"})
        return errors

    def _check_source(self, request: dict) -> list:
        bid = request.get("backup_job_id")
        if not bid or not self.db: return []
        result = self.validate_backup_integrity(bid)
        if not result.get("valid"):
            return [{"code": "INVALID_BACKUP", "message": f"Backup {bid} is not valid"}]
        return []

    def _check_approval(self, request: dict) -> list:
        if request.get("approval_status","pending") != "approved":
            return [{"code": "NOT_APPROVED", "message": f"Restore requires approval (status: {request.get('approval_status','pending')})"}]
        return []

    def _check_resources(self, request: dict) -> list:
        warnings = []
        try:
            _, _, free = shutil.disk_usage(request.get("target_path","/"))
            if free / 1e9 < 5:
                warnings.append({"code": "LOW_DISK", "message": f"Low disk space: {free/1e9:.1f}GB free"})
        except Exception: pass
        return warnings

    def _check_conflicts(self, request: dict) -> list:
        if not self.db: return []
        from ..sa_models import RestoreRequest
        from ..enums import RestoreStatus
        db = request.get("target_database")
        if db:
            active = self.db.query(RestoreRequest).filter(
                RestoreRequest.status == RestoreStatus.RUNNING,
                RestoreRequest.target_database == db).first()
            if active:
                return [{"code": "CONCURRENT_RESTORE",
                         "message": f"Restore to {db} already in progress: {active.id}"}]
        return []

    def _check_pitr(self, request: dict) -> list:
        errors = []
        pitr = request.get("point_in_time")
        if pitr:
            try:
                dt = datetime.fromisoformat(str(pitr)) if isinstance(pitr, str) else pitr
                if dt > datetime.utcnow():
                    errors.append({"code": "FUTURE_TIMESTAMP", "message": "PITR timestamp cannot be in the future"})
                max_age = self.config.get("max_pitr_age_days", 30)
                if dt < datetime.utcnow() - timedelta(days=max_age):
                    errors.append({"code": "PITR_TOO_OLD", "message": f"PITR older than {max_age} days"})
            except (ValueError, TypeError):
                errors.append({"code": "INVALID_TIMESTAMP", "message": "Invalid point_in_time format"})
        return errors
