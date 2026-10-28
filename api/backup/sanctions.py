"""
Backup Module Sanctions
Access control, rate limiting, and operation sanctions for backup operations.
Prevents abuse and enforces operational boundaries.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SanctionViolation(Exception):
    """Raised when a sanctioned operation is attempted"""
    def __init__(self, message: str, sanction_type: str, detail: Optional[Dict] = None):
        super().__init__(message)
        self.sanction_type = sanction_type
        self.detail = detail or {}


class RateLimitExceeded(SanctionViolation):
    def __init__(self, limit: int, window_seconds: int, current: int):
        super().__init__(
            f"Rate limit exceeded: {current}/{limit} in {window_seconds}s",
            sanction_type="rate_limit",
            detail={"limit": limit, "window_seconds": window_seconds, "current": current},
        )
        self.retry_after = window_seconds


class QuotaExceeded(SanctionViolation):
    def __init__(self, used: int, quota: int, unit: str = "bytes"):
        super().__init__(
            f"Storage quota exceeded: {used}/{quota} {unit}",
            sanction_type="quota",
            detail={"used": used, "quota": quota, "unit": unit},
        )


class OperationNotPermitted(SanctionViolation):
    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Operation '{operation}' not permitted: {reason}",
            sanction_type="permission",
            detail={"operation": operation, "reason": reason},
        )


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class BackupRateLimiter:
    """
    Sliding-window rate limiter backed by Django cache.
    Limits backup/restore operations per user or IP.
    """

    DEFAULTS = {
        "backup_create": {"limit": 10, "window": 3600},       # 10/hour
        "backup_restore": {"limit": 3, "window": 3600},        # 3/hour
        "backup_delete": {"limit": 20, "window": 3600},        # 20/hour
        "storage_upload": {"limit": 50, "window": 3600},       # 50/hour
    }

    def __init__(self, overrides: Optional[Dict] = None):
        cfg = getattr(settings, "BACKUP_RATE_LIMITS", {})
        self._limits = {**self.DEFAULTS, **(overrides or {}), **cfg}

    def _cache_key(self, operation: str, identifier: str) -> str:
        return f"backup_ratelimit:{operation}:{identifier}"

    def check(self, operation: str, identifier: str) -> None:
        """
        Check if identifier (user_id or IP) is within rate limit for operation.
        Raises RateLimitExceeded if over limit.
        """
        rule = self._limits.get(operation)
        if not rule:
            return  # unknown operation — no limit

        limit = rule["limit"]
        window = rule["window"]
        key = self._cache_key(operation, identifier)

        current = cache.get(key, 0)
        if current >= limit:
            raise RateLimitExceeded(limit=limit, window_seconds=window, current=current)

        # Increment counter; set expiry only on first hit
        pipe_val = cache.get_or_set(key, 0, window)
        cache.incr(key)

    def reset(self, operation: str, identifier: str) -> None:
        """Reset counter for an operation/identifier pair"""
        cache.delete(self._cache_key(operation, identifier))

    def get_current(self, operation: str, identifier: str) -> int:
        return cache.get(self._cache_key(operation, identifier), 0)


# ---------------------------------------------------------------------------
# Storage Quota Enforcer
# ---------------------------------------------------------------------------

class StorageQuotaEnforcer:
    """
    Enforces per-tenant storage quotas.
    Reads quota from settings or per-tenant config.
    """

    DEFAULT_QUOTA_BYTES = getattr(settings, "BACKUP_DEFAULT_QUOTA_BYTES",
                                  100 * 1024 ** 3)  # 100 GB

    def __init__(self):
        self._tenant_quotas: Dict[str, int] = getattr(
            settings, "BACKUP_TENANT_QUOTAS", {}
        )

    def get_quota(self, tenant_id: str) -> int:
        return self._tenant_quotas.get(tenant_id, self.DEFAULT_QUOTA_BYTES)

    def check_quota(self, tenant_id: str, current_usage: int, new_size: int) -> None:
        """
        Check if adding new_size bytes would exceed quota.
        Raises QuotaExceeded if it would.
        """
        quota = self.get_quota(tenant_id)
        projected = current_usage + new_size
        if projected > quota:
            raise QuotaExceeded(used=projected, quota=quota)

    def usage_percentage(self, tenant_id: str, current_usage: int) -> float:
        quota = self.get_quota(tenant_id)
        if quota == 0:
            return 100.0
        return round((current_usage / quota) * 100, 2)

    def is_near_limit(self, tenant_id: str, current_usage: int,
                      threshold: float = 0.8) -> bool:
        quota = self.get_quota(tenant_id)
        return current_usage >= quota * threshold


# ---------------------------------------------------------------------------
# Operation Sanctions
# ---------------------------------------------------------------------------

class OperationSanctionChecker:
    """
    Checks whether a backup operation is sanctioned given system state.
    E.g.: block new backups during maintenance, block delete of running backup.
    """

    def check_create_backup(self, system_state: Dict[str, Any]) -> None:
        if system_state.get("maintenance_mode", False):
            raise OperationNotPermitted(
                "backup_create",
                "System is in maintenance mode. Backup creation is temporarily suspended.",
            )
        if system_state.get("storage_full", False):
            raise OperationNotPermitted(
                "backup_create",
                "Storage is full. Free up space before creating new backups.",
            )

    def check_delete_backup(self, backup: Dict[str, Any]) -> None:
        if backup.get("status") == "running":
            raise OperationNotPermitted(
                "backup_delete",
                f"Cannot delete backup '{backup.get('id')}' while it is running.",
            )
        if backup.get("is_locked", False):
            raise OperationNotPermitted(
                "backup_delete",
                f"Backup '{backup.get('id')}' is locked and cannot be deleted.",
            )

    def check_restore_backup(self, backup: Dict[str, Any],
                              system_state: Dict[str, Any]) -> None:
        if backup.get("status") != "completed":
            raise OperationNotPermitted(
                "backup_restore",
                f"Only completed backups can be restored. Current status: {backup.get('status')}",
            )
        if system_state.get("restore_in_progress", False):
            raise OperationNotPermitted(
                "backup_restore",
                "Another restore operation is already in progress.",
            )


# ---------------------------------------------------------------------------
# Composite Sanction Guard
# ---------------------------------------------------------------------------

class BackupSanctionGuard:
    """
    Facade that combines rate limiting, quota enforcement, and operation sanctions.
    Call check_* methods from views/tasks before executing operations.
    """

    def __init__(self):
        self.rate_limiter = BackupRateLimiter()
        self.quota_enforcer = StorageQuotaEnforcer()
        self.operation_checker = OperationSanctionChecker()

    def guard_create(self, user_id: str, tenant_id: str,
                     current_usage: int, new_size: int,
                     system_state: Optional[Dict] = None) -> None:
        self.rate_limiter.check("backup_create", user_id)
        self.quota_enforcer.check_quota(tenant_id, current_usage, new_size)
        self.operation_checker.check_create_backup(system_state or {})

    def guard_delete(self, user_id: str, backup: Dict[str, Any]) -> None:
        self.rate_limiter.check("backup_delete", user_id)
        self.operation_checker.check_delete_backup(backup)

    def guard_restore(self, user_id: str, backup: Dict[str, Any],
                      system_state: Optional[Dict] = None) -> None:
        self.rate_limiter.check("backup_restore", user_id)
        self.operation_checker.check_restore_backup(backup, system_state or {})
