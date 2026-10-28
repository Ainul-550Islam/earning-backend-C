"""
Backup Module Schemas
Data schemas and type definitions used across the backup module.
Provides structured validation and serialization contracts separate from DRF serializers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VERIFYING = "verifying"
    RESTORING = "restoring"


class StorageBackend(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"


class CompressionAlgorithm(str, Enum):
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    ZSTD = "zstd"
    LZ4 = "lz4"


class EncryptionAlgorithm(str, Enum):
    NONE = "none"
    AES_256 = "aes256"
    FERNET = "fernet"
    CHACHA20 = "chacha20"


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

@dataclass
class CreateBackupSchema:
    """Input schema for creating a new backup"""
    name: str
    storage_backend: StorageBackend
    compression: CompressionAlgorithm = CompressionAlgorithm.GZIP
    encryption: EncryptionAlgorithm = EncryptionAlgorithm.AES_256
    retention_days: int = 30
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self):
        errors = {}
        if not self.name or not self.name.strip():
            errors["name"] = "Name is required."
        if self.retention_days < 1:
            errors["retention_days"] = "Retention must be at least 1 day."
        if errors:
            raise ValueError(errors)
        return True


@dataclass
class BackupResponseSchema:
    """Output schema for backup objects"""
    id: str
    name: str
    status: BackupStatus
    storage_backend: StorageBackend
    size_bytes: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    retention_days: int
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "storage_backend": self.storage_backend.value,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retention_days": self.retention_days,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class RestoreRequestSchema:
    """Input schema for restore operations"""
    backup_id: str
    target_database: Optional[str] = None
    point_in_time: Optional[datetime] = None
    dry_run: bool = False

    def validate(self):
        if not self.backup_id:
            raise ValueError({"backup_id": "backup_id is required."})
        return True


@dataclass
class ScheduleSchema:
    """Schema for backup schedule configuration"""
    name: str
    cron_expression: str
    storage_backend: StorageBackend
    enabled: bool = True
    retention_days: int = 30
    compression: CompressionAlgorithm = CompressionAlgorithm.GZIP
    encryption: EncryptionAlgorithm = EncryptionAlgorithm.AES_256
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class StorageLocationSchema:
    """Schema for storage location configuration"""
    name: str
    backend: StorageBackend
    config: Dict[str, Any]
    is_default: bool = False
    is_active: bool = True

    def validate(self):
        required_keys = {
            StorageBackend.S3: ["bucket_name", "region"],
            StorageBackend.AZURE: ["container_name"],
            StorageBackend.GCS: ["bucket_name", "project_id"],
            StorageBackend.LOCAL: ["backup_path"],
        }
        needed = required_keys.get(self.backend, [])
        missing = [k for k in needed if k not in self.config]
        if missing:
            raise ValueError({
                "config": f"Missing required keys for {self.backend.value}: {missing}"
            })
        return True


@dataclass
class BackupStatsSchema:
    """Schema for backup statistics"""
    total_backups: int
    successful_backups: int
    failed_backups: int
    total_size_bytes: int
    average_size_bytes: float
    success_rate: float
    last_backup_at: Optional[datetime]
    next_scheduled_at: Optional[datetime]

    @classmethod
    def empty(cls) -> "BackupStatsSchema":
        return cls(
            total_backups=0,
            successful_backups=0,
            failed_backups=0,
            total_size_bytes=0,
            average_size_bytes=0.0,
            success_rate=0.0,
            last_backup_at=None,
            next_scheduled_at=None,
        )
