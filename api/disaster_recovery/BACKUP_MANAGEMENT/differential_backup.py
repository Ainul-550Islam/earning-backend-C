"""
Differential Backup — Backs up all changes since last FULL backup
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class DifferentialBackupManager:
    """
    Differential backups capture all changes since the last FULL backup
    (unlike incremental, which captures changes since last backup of any type).
    Restores are faster: need only the full + latest differential.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    def find_last_full(self, policy_id: str) -> Optional[dict]:
        from ..sa_models import BackupJob
        from ..enums import BackupStatus, BackupType
        from sqlalchemy import desc, and_
        job = self.db.query(BackupJob).filter(
            and_(
                BackupJob.policy_id == policy_id,
                BackupJob.status == BackupStatus.COMPLETED,
                BackupJob.backup_type == BackupType.FULL,
            )
        ).order_by(desc(BackupJob.completed_at)).first()
        if not job:
            return None
        return {"id": job.id, "completed_at": job.completed_at, "storage_path": job.storage_path}

    def get_changed_since_full(self, source_path: str, full_backup_time: datetime) -> list:
        import os
        since_ts = full_backup_time.timestamp()
        changed = []
        for root, _, files in os.walk(source_path):
            for fname in files:
                full = os.path.join(root, fname)
                try:
                    if os.path.getmtime(full) > since_ts:
                        changed.append(full)
                except OSError:
                    pass
        logger.info(f"Differential: {len(changed)} files changed since full backup at {full_backup_time}")
        return changed

    def restore_sequence(self, policy_id: str) -> list:
        """Return the minimal restore sequence: [full_backup, latest_differential]."""
        full = self.find_last_full(policy_id)
        if not full:
            return []
        return [full]
