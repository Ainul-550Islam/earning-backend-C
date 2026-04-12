"""
Restore Model — SQLAlchemy model for restore request records.
Tracks every restore operation from initial request through
approval, execution, and post-restore verification.
"""
from ..sa_models import RestoreRequest, RestoreVerification, PointInTimeLog

__all__ = ["RestoreRequest", "RestoreVerification", "PointInTimeLog"]

RESTORE_REQUEST_EXAMPLE = {
    "id": "restore-001",
    "backup_job_id": "backup-550e8400",
    "requested_by": "user@company.com",
    "status": "completed",
    "restore_type": "full",
    "target_database": "production_db_restore_test",
    "started_at": "2024-01-15T10:00:00Z",
    "completed_at": "2024-01-15T10:38:12Z",
    "duration_seconds": 2292.0,
    "bytes_restored": 10737418240,
    "approval_status": "approved",
    "approved_by": "admin@company.com",
}

PITR_LOG_EXAMPLE = {
    "database_name": "production_db",
    "earliest_restore_point": "2024-01-14T02:00:00Z",
    "latest_restore_point": "2024-01-15T09:59:45Z",
    "is_available": True,
}
