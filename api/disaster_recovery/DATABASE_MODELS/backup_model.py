"""
Backup Model — SQLAlchemy model for backup job records.
Every scheduled or manual backup execution is stored here with
full lifecycle tracking: pending → running → completed/failed → verified.
"""
from ..sa_models import BackupJob, BackupPolicy, BackupSnapshot, StorageLocation

# ── Re-export for module-level access ─────────────────────────────────────────
__all__ = ["BackupJob", "BackupPolicy", "BackupSnapshot", "StorageLocation"]

# ── Example usage (for documentation/testing) ─────────────────────────────────
BACKUP_JOB_EXAMPLE = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "policy_id": "policy-123",
    "backup_type": "full",
    "status": "completed",
    "started_at": "2024-01-15T02:00:00Z",
    "completed_at": "2024-01-15T02:45:22Z",
    "duration_seconds": 2722.0,
    "source_size_bytes": 10737418240,   # 10 GB
    "compressed_size_bytes": 3221225472, # 3 GB
    "encrypted": True,
    "checksum": "sha256:abc123...",
    "storage_path": "backups/full/mydb/2024/01/15/backup.dump.gz.enc",
    "is_verified": True,
}

BACKUP_POLICY_EXAMPLE = {
    "id": "policy-123",
    "name": "Production DB Daily Full",
    "backup_type": "full",
    "frequency": "daily",
    "cron_expression": "0 2 * * *",
    "retention_days": 30,
    "storage_provider": "aws_s3",
    "target_database": "production_db",
    "enable_compression": True,
    "enable_encryption": True,
    "is_active": True,
}
