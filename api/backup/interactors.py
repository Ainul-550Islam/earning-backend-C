"""
Backup Module Interactors
Use-case interactors that orchestrate business logic.
Each interactor handles exactly one use case and depends on repositories/services,
keeping views and tasks thin.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CreateBackupInteractor:
    """
    Use case: Create a new backup.
    Validates input, triggers the backup service, persists the record.
    """

    def __init__(self, backup_repo=None, storage_repo=None, notification_service=None):
        from api.backup.repositories import BackupRepository, StorageLocationRepository
        from api.backup.services.BackupNotificationService import BackupNotificationService
        self.backup_repo = backup_repo or BackupRepository()
        self.storage_repo = storage_repo or StorageLocationRepository()
        self.notification_service = notification_service or BackupNotificationService()

    def execute(self, data: Dict[str, Any], user=None) -> Dict[str, Any]:
        from api.backup.schemas import CreateBackupSchema, StorageBackend
        schema = CreateBackupSchema(
            name=data["name"],
            storage_backend=StorageBackend(data.get("storage_backend", "local")),
            retention_days=data.get("retention_days", 30),
        )
        schema.validate()

        storage_location = self.storage_repo.get_default()
        if not storage_location:
            raise ValueError("No active storage location configured.")

        backup = self.backup_repo.create({
            "name": schema.name,
            "status": "pending",
            "retention_days": schema.retention_days,
            "created_by": user,
        })

        logger.info("Backup created: %s", backup.id)
        return {"backup_id": str(backup.id), "status": "pending"}


class DeleteBackupInteractor:
    """
    Use case: Delete a backup record and its storage artifact.
    """

    def __init__(self, backup_repo=None):
        from api.backup.repositories import BackupRepository
        self.backup_repo = backup_repo or BackupRepository()

    def execute(self, backup_id: str, user=None) -> bool:
        backup = self.backup_repo.get_by_id(backup_id)
        if not backup:
            raise LookupError(f"Backup {backup_id} not found.")
        if backup.status == "running":
            raise RuntimeError("Cannot delete a running backup.")
        deleted = self.backup_repo.delete(backup_id)
        logger.info("Backup deleted: %s by user=%s", backup_id, getattr(user, "id", None))
        return deleted


class RestoreBackupInteractor:
    """
    Use case: Restore a backup to the target database.
    """

    def __init__(self, backup_repo=None):
        from api.backup.repositories import BackupRepository
        self.backup_repo = backup_repo or BackupRepository()

    def execute(self, backup_id: str, target_database: Optional[str] = None,
                dry_run: bool = False) -> Dict[str, Any]:
        backup = self.backup_repo.get_by_id(backup_id)
        if not backup:
            raise LookupError(f"Backup {backup_id} not found.")
        if backup.status != "completed":
            raise RuntimeError(f"Cannot restore backup with status '{backup.status}'.")

        logger.info(
            "Restore initiated: backup=%s target=%s dry_run=%s",
            backup_id, target_database, dry_run,
        )
        return {
            "backup_id": backup_id,
            "target_database": target_database,
            "dry_run": dry_run,
            "status": "initiated",
        }


class ListBackupsInteractor:
    """
    Use case: List backups with optional filtering.
    """

    def __init__(self, backup_repo=None):
        from api.backup.repositories import BackupRepository
        self.backup_repo = backup_repo or BackupRepository()

    def execute(self, status: Optional[str] = None, days: Optional[int] = None) -> Any:
        if status:
            return self.backup_repo.get_by_status(status)
        if days:
            return self.backup_repo.get_recent(days=days)
        return self.backup_repo.get_all()


class GetBackupStatsInteractor:
    """
    Use case: Compute summary statistics for the backup system.
    """

    def __init__(self, backup_repo=None):
        from api.backup.repositories import BackupRepository
        self.backup_repo = backup_repo or BackupRepository()

    def execute(self) -> Dict[str, Any]:
        counts = self.backup_repo.count_by_status()
        total = sum(counts.values())
        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0)

        return {
            "total_backups": total,
            "completed": completed,
            "failed": failed,
            "running": counts.get("running", 0),
            "pending": counts.get("pending", 0),
            "success_rate": round(completed / total, 4) if total > 0 else 0.0,
            "total_size_bytes": self.backup_repo.total_size_bytes(),
        }


class CleanupExpiredBackupsInteractor:
    """
    Use case: Identify and delete expired backup records.
    """

    def __init__(self, backup_repo=None):
        from api.backup.repositories import BackupRepository
        self.backup_repo = backup_repo or BackupRepository()

    def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        expired = list(self.backup_repo.get_expired())
        if dry_run:
            return {"would_delete": len(expired), "dry_run": True}

        deleted = 0
        for backup in expired:
            if self.backup_repo.delete(str(backup.id)):
                deleted += 1

        logger.info("Cleanup: deleted %d expired backups", deleted)
        return {"deleted": deleted, "dry_run": False}
