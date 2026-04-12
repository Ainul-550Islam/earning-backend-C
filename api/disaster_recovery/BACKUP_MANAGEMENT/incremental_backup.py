"""
Incremental Backup — Only backs up changes since the last backup
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class IncrementalBackupManager:
    """
    Manages incremental backups that only capture data changed
    since the previous backup (full or incremental).
    Uses WAL (Write-Ahead Log) for databases, inode timestamps for filesystems.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    def find_base_backup(self, policy_id: str) -> Optional[dict]:
        """Find the most recent valid base backup for this policy."""
        from ..sa_models import BackupJob
        from ..enums import BackupStatus, BackupType
        from sqlalchemy import desc, and_

        job = self.db.query(BackupJob).filter(
            and_(
                BackupJob.policy_id == policy_id,
                BackupJob.status == BackupStatus.COMPLETED,
                BackupJob.backup_type.in_([BackupType.FULL, BackupType.INCREMENTAL]),
            )
        ).order_by(desc(BackupJob.completed_at)).first()

        if not job:
            return None
        return {
            "id": job.id,
            "completed_at": job.completed_at,
            "type": job.backup_type,
            "storage_path": job.storage_path,
        }

    def get_changed_files(self, source_path: str, since: datetime) -> list:
        """List files modified after `since` timestamp."""
        import os
        changed = []
        since_ts = since.timestamp()
        for root, _, files in os.walk(source_path):
            for fname in files:
                full = os.path.join(root, fname)
                try:
                    if os.path.getmtime(full) > since_ts:
                        changed.append(full)
                except OSError:
                    pass
        logger.info(f"Found {len(changed)} changed files since {since}")
        return changed

    def create_manifest(self, job_id: str, changed_files: list, base_backup_id: str) -> dict:
        """Create a manifest file listing all incremental changes."""
        manifest = {
            "job_id": job_id,
            "base_backup_id": base_backup_id,
            "created_at": datetime.utcnow().isoformat(),
            "file_count": len(changed_files),
            "files": changed_files,
        }
        return manifest

    def chain_length(self, policy_id: str) -> int:
        """How many consecutive incrementals since last full backup."""
        from ..sa_models import BackupJob
        from ..enums import BackupStatus, BackupType
        from sqlalchemy import desc, and_

        jobs = self.db.query(BackupJob).filter(
            and_(
                BackupJob.policy_id == policy_id,
                BackupJob.status == BackupStatus.COMPLETED,
            )
        ).order_by(desc(BackupJob.completed_at)).limit(30).all()

        count = 0
        for job in jobs:
            if job.backup_type == BackupType.FULL:
                break
            if job.backup_type == BackupType.INCREMENTAL:
                count += 1
        return count

    def should_force_full(self, policy_id: str, max_chain: int = 6) -> bool:
        """Force a full backup if the incremental chain is too long."""
        chain = self.chain_length(policy_id)
        if chain >= max_chain:
            logger.info(f"Chain length {chain} >= {max_chain}, forcing full backup")
            return True
        return False
