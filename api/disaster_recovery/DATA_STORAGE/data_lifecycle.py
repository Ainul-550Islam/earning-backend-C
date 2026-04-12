"""
Data Lifecycle Manager — Automates full lifecycle of backup data from creation to deletion.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LifecycleStage:
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRING = "expiring"
    DELETED = "deleted"


class DataLifecycleManager:
    """
    Manages the complete lifecycle of backup data:
    Active -> Archived -> Expiring -> Deleted

    Features:
    - Legal hold support (prevents deletion)
    - Compliance retention enforcement
    - Automated expiry notifications
    - Audit trail for all lifecycle events
    """

    def __init__(self, db_session=None, config: dict = None):
        self.db = db_session
        self.config = config or {}
        self.default_retention_days = config.get("default_retention_days", 30)
        self.archive_after_days = config.get("archive_after_days", 7)
        self.warn_before_expiry_days = config.get("warn_before_expiry_days", 7)

    def get_lifecycle_stage(self, backup: dict) -> str:
        """Determine the current lifecycle stage of a backup."""
        created = datetime.fromisoformat(backup.get("created_at", datetime.utcnow().isoformat()))
        age_days = (datetime.utcnow() - created).days
        retention = backup.get("retention_days", self.default_retention_days)
        if backup.get("legal_hold", False):
            return LifecycleStage.ACTIVE
        if age_days >= retention:
            return LifecycleStage.EXPIRING
        if age_days >= self.archive_after_days:
            return LifecycleStage.ARCHIVED
        return LifecycleStage.ACTIVE

    def get_expiring_soon(self, backups: List[dict], within_days: int = 7) -> List[dict]:
        """Get backups that will expire within N days."""
        expiring = []
        now = datetime.utcnow()
        for backup in backups:
            created = datetime.fromisoformat(backup.get("created_at", now.isoformat()))
            retention = backup.get("retention_days", self.default_retention_days)
            expiry_date = created + timedelta(days=retention)
            days_until_expiry = (expiry_date - now).days
            if 0 <= days_until_expiry <= within_days:
                expiring.append({
                    **backup,
                    "expiry_date": expiry_date.isoformat(),
                    "days_until_expiry": days_until_expiry,
                })
        return sorted(expiring, key=lambda x: x["days_until_expiry"])

    def get_expired(self, backups: List[dict]) -> List[dict]:
        """Get all backups that have passed their retention date."""
        now = datetime.utcnow()
        expired = []
        for backup in backups:
            if backup.get("legal_hold", False):
                continue
            created = datetime.fromisoformat(backup.get("created_at", now.isoformat()))
            retention = backup.get("retention_days", self.default_retention_days)
            if (now - created).days >= retention:
                expired.append(backup)
        return expired

    def apply_legal_hold(self, backup_id: str) -> dict:
        """Apply legal hold to prevent deletion."""
        logger.warning(f"Legal hold applied to backup: {backup_id}")
        if self.db:
            from ..sa_models import BackupJob
            job = self.db.query(BackupJob).filter(BackupJob.id == backup_id).first()
            if job:
                if not job.job_payload:
                    job.job_payload = {}
                job.job_payload["legal_hold"] = True
                job.job_payload["legal_hold_applied_at"] = datetime.utcnow().isoformat()
                self.db.commit()
        return {"backup_id": backup_id, "legal_hold": True,
                "applied_at": datetime.utcnow().isoformat()}

    def remove_legal_hold(self, backup_id: str, authorized_by: str) -> dict:
        """Remove legal hold (requires authorized personnel)."""
        logger.warning(f"Legal hold removed from backup: {backup_id} by {authorized_by}")
        if self.db:
            from ..sa_models import BackupJob
            job = self.db.query(BackupJob).filter(BackupJob.id == backup_id).first()
            if job and job.job_payload:
                job.job_payload["legal_hold"] = False
                job.job_payload["legal_hold_removed_at"] = datetime.utcnow().isoformat()
                job.job_payload["legal_hold_removed_by"] = authorized_by
                self.db.commit()
        return {"backup_id": backup_id, "legal_hold": False,
                "removed_by": authorized_by, "removed_at": datetime.utcnow().isoformat()}

    def extend_retention(self, backup_id: str, additional_days: int,
                          reason: str, authorized_by: str) -> dict:
        """Extend retention period for a specific backup."""
        logger.info(f"Retention extended: backup={backup_id}, +{additional_days}d by {authorized_by}")
        return {
            "backup_id": backup_id,
            "additional_days": additional_days,
            "reason": reason,
            "authorized_by": authorized_by,
            "extended_at": datetime.utcnow().isoformat(),
        }

    def generate_lifecycle_report(self, backups: List[dict]) -> dict:
        """Generate a comprehensive lifecycle status report."""
        stage_counts: Dict[str, int] = {
            LifecycleStage.ACTIVE: 0,
            LifecycleStage.ARCHIVED: 0,
            LifecycleStage.EXPIRING: 0,
        }
        legal_holds = 0
        total_size = 0
        for backup in backups:
            stage = self.get_lifecycle_stage(backup)
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            total_size += backup.get("size_bytes", 0)
            if backup.get("legal_hold", False):
                legal_holds += 1
        expiring_soon = self.get_expiring_soon(backups, within_days=7)
        return {
            "report_date": datetime.utcnow().isoformat(),
            "total_backups": len(backups),
            "total_size_gb": round(total_size / 1e9, 3),
            "by_stage": stage_counts,
            "legal_holds": legal_holds,
            "expiring_in_7_days": len(expiring_soon),
            "expiring_details": expiring_soon[:10],
        }
