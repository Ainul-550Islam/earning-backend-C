"""
Backup Policy Model — SQLAlchemy model for automated backup policies.
Defines schedules (cron), retention rules, storage targets,
and encryption/compression settings for automated backups.
"""
from ..sa_models import BackupPolicy

__all__ = ["BackupPolicy"]

POLICY_EXAMPLES = [
    {
        "name": "Production DB — Hourly Incremental",
        "backup_type": "incremental",
        "frequency": "hourly",
        "cron_expression": "0 * * * *",
        "retention_days": 7,
        "storage_provider": "aws_s3",
        "target_database": "production_db",
        "enable_compression": True,
        "enable_encryption": True,
    },
    {
        "name": "Production DB — Daily Full",
        "backup_type": "full",
        "frequency": "daily",
        "cron_expression": "0 2 * * *",
        "retention_days": 30,
        "storage_provider": "aws_s3",
        "target_database": "production_db",
    },
    {
        "name": "Production DB — Weekly Archive",
        "backup_type": "full",
        "frequency": "weekly",
        "cron_expression": "0 3 * * 0",
        "retention_days": 365,
        "storage_provider": "aws_glacier",
        "target_database": "production_db",
    },
]
