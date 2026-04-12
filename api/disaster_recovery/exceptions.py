"""
Custom Exceptions for Disaster Recovery System
"""


class DRBaseException(Exception):
    """Base exception for all DR system errors."""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or "DR_ERROR"
        self.details = details or {}
        super().__init__(message)

    def to_dict(self):
        return {"error": self.code, "message": self.message, "details": self.details}


# ── Backup Exceptions ─────────────────────────────────────────────────────────
class BackupException(DRBaseException):
    pass

class BackupNotFoundException(BackupException):
    def __init__(self, backup_id: str):
        super().__init__(f"Backup {backup_id} not found", "BACKUP_NOT_FOUND")

class BackupFailedException(BackupException):
    def __init__(self, reason: str):
        super().__init__(f"Backup failed: {reason}", "BACKUP_FAILED")

class BackupVerificationException(BackupException):
    def __init__(self, backup_id: str, reason: str):
        super().__init__(
            f"Backup {backup_id} verification failed: {reason}",
            "BACKUP_VERIFICATION_FAILED"
        )

class BackupStorageException(BackupException):
    def __init__(self, provider: str, reason: str):
        super().__init__(
            f"Storage error on {provider}: {reason}",
            "BACKUP_STORAGE_ERROR"
        )

class BackupPolicyNotFoundException(BackupException):
    def __init__(self, policy_id: str):
        super().__init__(f"Backup policy {policy_id} not found", "POLICY_NOT_FOUND")


# ── Restore Exceptions ────────────────────────────────────────────────────────
class RestoreException(DRBaseException):
    pass

class RestoreNotFoundException(RestoreException):
    def __init__(self, restore_id: str):
        super().__init__(f"Restore request {restore_id} not found", "RESTORE_NOT_FOUND")

class RestoreFailedException(RestoreException):
    def __init__(self, reason: str):
        super().__init__(f"Restore failed: {reason}", "RESTORE_FAILED")

class RestoreValidationException(RestoreException):
    def __init__(self, reason: str):
        super().__init__(f"Restore validation failed: {reason}", "RESTORE_VALIDATION_FAILED")

class PointInTimeRestoreException(RestoreException):
    def __init__(self, timestamp: str, reason: str):
        super().__init__(
            f"Point-in-time restore to {timestamp} failed: {reason}",
            "PITR_FAILED"
        )


# ── Failover Exceptions ───────────────────────────────────────────────────────
class FailoverException(DRBaseException):
    pass

class FailoverNotFoundException(FailoverException):
    def __init__(self, event_id: str):
        super().__init__(f"Failover event {event_id} not found", "FAILOVER_NOT_FOUND")

class FailoverFailedException(FailoverException):
    def __init__(self, reason: str):
        super().__init__(f"Failover failed: {reason}", "FAILOVER_FAILED")

class NoHealthyNodeException(FailoverException):
    def __init__(self):
        super().__init__("No healthy nodes available for failover", "NO_HEALTHY_NODE")


# ── Replication Exceptions ────────────────────────────────────────────────────
class ReplicationException(DRBaseException):
    pass

class ReplicationLagException(ReplicationException):
    def __init__(self, lag_seconds: float):
        super().__init__(
            f"Replication lag too high: {lag_seconds}s",
            "REPLICATION_LAG_HIGH"
        )

class ReplicationSyncException(ReplicationException):
    def __init__(self, reason: str):
        super().__init__(f"Replication sync failed: {reason}", "REPLICATION_SYNC_FAILED")


# ── Storage Exceptions ────────────────────────────────────────────────────────
class StorageException(DRBaseException):
    pass

class StorageConnectionException(StorageException):
    def __init__(self, provider: str):
        super().__init__(f"Cannot connect to storage: {provider}", "STORAGE_CONNECTION_ERROR")

class StorageQuotaException(StorageException):
    def __init__(self, provider: str):
        super().__init__(f"Storage quota exceeded: {provider}", "STORAGE_QUOTA_EXCEEDED")


# ── Encryption Exceptions ─────────────────────────────────────────────────────
class EncryptionException(DRBaseException):
    pass

class KeyNotFoundException(EncryptionException):
    def __init__(self, key_id: str):
        super().__init__(f"Encryption key {key_id} not found", "KEY_NOT_FOUND")

class DecryptionFailedException(EncryptionException):
    def __init__(self, reason: str):
        super().__init__(f"Decryption failed: {reason}", "DECRYPTION_FAILED")


# ── Monitoring / Alert Exceptions ─────────────────────────────────────────────
class MonitoringException(DRBaseException):
    pass

class AlertException(DRBaseException):
    pass

class NotificationException(DRBaseException):
    def __init__(self, channel: str, reason: str):
        super().__init__(
            f"Notification via {channel} failed: {reason}",
            "NOTIFICATION_FAILED"
        )


# ── Drill Exceptions ──────────────────────────────────────────────────────────
class DrillException(DRBaseException):
    pass

class DrillNotFoundException(DrillException):
    def __init__(self, drill_id: str):
        super().__init__(f"DR drill {drill_id} not found", "DRILL_NOT_FOUND")

class DrillFailedException(DrillException):
    def __init__(self, reason: str):
        super().__init__(f"DR drill failed: {reason}", "DRILL_FAILED")


# ── Compliance Exceptions ─────────────────────────────────────────────────────
class ComplianceException(DRBaseException):
    pass

class SLAViolationException(ComplianceException):
    def __init__(self, metric: str, target: float, actual: float):
        super().__init__(
            f"SLA violation: {metric} target={target}% actual={actual}%",
            "SLA_VIOLATION",
            {"metric": metric, "target": target, "actual": actual}
        )


# ── HTTP Error Mapping ────────────────────────────────────────────────────────
EXCEPTION_STATUS_MAP = {
    BackupNotFoundException: 404,
    RestoreNotFoundException: 404,
    FailoverNotFoundException: 404,
    DrillNotFoundException: 404,
    BackupPolicyNotFoundException: 404,
    KeyNotFoundException: 404,
    BackupFailedException: 500,
    RestoreFailedException: 500,
    FailoverFailedException: 500,
    DrillFailedException: 500,
    BackupVerificationException: 422,
    RestoreValidationException: 422,
    SLAViolationException: 422,
    NoHealthyNodeException: 503,
    StorageConnectionException: 503,
    StorageQuotaException: 507,
}
