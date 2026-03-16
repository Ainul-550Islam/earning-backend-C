# =============================================================================
# version_control/services.py
# =============================================================================
"""
Service layer for the version_control application.

Handles:
  - Checking whether a client needs to update (VersionCheckService)
  - Creating / updating / activating update policies (UpdatePolicyService)
  - Starting / ending maintenance windows (MaintenanceService)
  - Resolving platform redirects (RedirectService)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from functools import total_ordering
from typing import Any

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .choices import MaintenanceStatus, PolicyStatus, UpdateType
from .constants import (
    CACHE_KEY_MAINTENANCE,
    CACHE_KEY_REDIRECT,
    CACHE_KEY_UPDATE_POLICY,
    CACHE_TTL_MAINTENANCE,
    CACHE_TTL_REDIRECT,
    CACHE_TTL_UPDATE_POLICY,
    VERSION_REGEX,
)
from .exceptions import (
    InvalidPlatformError,
    InvalidVersionStringError,
    MaintenanceAlreadyActiveError,
    MaintenanceNotFoundError,
    PolicyAlreadyExistsError,
    UpdatePolicyNotFoundError,
)
from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version comparison helper
# ---------------------------------------------------------------------------

@total_ordering
class SemVer:
    """
    Minimal semver parser for comparison.
    Only handles MAJOR.MINOR.PATCH (pre-release / build metadata ignored for ordering).
    """

    _PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

    def __init__(self, version_str: str) -> None:
        m = self._PATTERN.match(version_str)
        if not m:
            raise InvalidVersionStringError(
                f"Cannot parse version string: {version_str!r}"
            )
        self.major, self.minor, self.patch = int(m[1]), int(m[2]), int(m[3])
        self._raw = version_str

    def _tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._tuple() == other._tuple()

    def __lt__(self, other: "SemVer") -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._tuple() < other._tuple()

    def __str__(self) -> str:
        return self._raw


def _parse_version(v: str) -> SemVer:
    if not re.match(VERSION_REGEX, v):
        raise InvalidVersionStringError(f"'{v}' is not a valid semver string.")
    return SemVer(v)


# =============================================================================
# VersionCheckService
# =============================================================================

class VersionCheckService:
    """
    Given a platform and current client version, determine what update action
    the client should take.

    Returns a structured dict:
    {
        "update_required":  bool,
        "update_type":      "optional" | "required" | "critical" | None,
        "target_version":   "1.2.3" | None,
        "release_notes":    "..." | None,
        "release_notes_url": "..." | None,
        "force_update_at":  ISO datetime | None,
    }
    """

    @staticmethod
    def check(*, platform: str, client_version: str) -> dict[str, Any]:
        """
        Check if the client needs to update.

        Raises:
            InvalidVersionStringError: if client_version is malformed.
            InvalidPlatformError: if platform is unrecognised.
        """
        from .constants import ALL_PLATFORMS
        if platform not in ALL_PLATFORMS:
            raise InvalidPlatformError(f"Unknown platform: {platform!r}")

        try:
            client_sv = _parse_version(client_version)
        except InvalidVersionStringError:
            raise

        cache_key = CACHE_KEY_UPDATE_POLICY.format(
            platform=platform, app_version=client_version
        )
        cached = _safe_cache_get(cache_key)
        if cached is not None:
            return cached

        policy = VersionCheckService._find_applicable_policy(
            platform=platform, client_sv=client_sv
        )

        if policy is None:
            result: dict[str, Any] = {
                "update_required":   False,
                "update_type":       None,
                "target_version":    None,
                "release_notes":     None,
                "release_notes_url": None,
                "force_update_at":   None,
            }
            _safe_cache_set(cache_key, result, CACHE_TTL_UPDATE_POLICY)
            return result

        effective_type = (
            UpdateType.REQUIRED
            if policy.is_effective_required and policy.update_type == UpdateType.OPTIONAL
            else policy.update_type
        )

        result = {
            "update_required":   effective_type in (UpdateType.REQUIRED, UpdateType.CRITICAL),
            "update_type":       effective_type,
            "target_version":    policy.target_version,
            "release_notes":     policy.release_notes or None,
            "release_notes_url": policy.release_notes_url or None,
            "force_update_at": (
                policy.force_update_after.isoformat()
                if policy.force_update_after
                else None
            ),
        }
        _safe_cache_set(cache_key, result, CACHE_TTL_UPDATE_POLICY)

        logger.info(
            "version_check platform=%s client=%s target=%s type=%s",
            platform, client_version, policy.target_version, effective_type,
        )
        return result

    @staticmethod
    def _find_applicable_policy(
        platform: str, client_sv: SemVer
    ) -> AppUpdatePolicy | None:
        """
        Find the highest-priority active policy for this client version.
        Priority: critical > required > optional; newest target_version wins.
        """
        policies = (
            AppUpdatePolicy.objects.active()
            .for_platform(platform)
            .order_by("-update_type", "-target_version")
        )

        for policy in policies:
            try:
                min_sv = _parse_version(policy.min_version)
            except InvalidVersionStringError:
                continue

            if client_sv < min_sv:
                continue   # client is already on or above min_version

            if policy.max_version:
                try:
                    max_sv = _parse_version(policy.max_version)
                    if client_sv >= max_sv:
                        continue  # client is at or above max (exclusive upper bound)
                except InvalidVersionStringError:
                    pass

            try:
                target_sv = _parse_version(policy.target_version)
            except InvalidVersionStringError:
                continue

            if client_sv >= target_sv:
                continue   # client is already on target or newer

            return policy

        return None


# =============================================================================
# UpdatePolicyService
# =============================================================================

class UpdatePolicyService:
    """CRUD and activation logic for AppUpdatePolicy."""

    @staticmethod
    @transaction.atomic
    def create_policy(
        *,
        platform: str,
        min_version: str,
        target_version: str,
        update_type: str = UpdateType.OPTIONAL,
        max_version: str = "",
        release_notes: str = "",
        release_notes_url: str = "",
        force_update_after: datetime | None = None,
        created_by=None,
        metadata: dict | None = None,
    ) -> AppUpdatePolicy:
        """
        Create a new DRAFT policy.  Does not activate it.

        Raises:
            PolicyAlreadyExistsError: if an active policy with same key exists.
        """
        try:
            policy = AppUpdatePolicy(
                platform=platform,
                min_version=min_version,
                max_version=max_version,
                target_version=target_version,
                update_type=update_type,
                release_notes=release_notes,
                release_notes_url=release_notes_url,
                force_update_after=force_update_after,
                status=PolicyStatus.DRAFT,
                created_by=created_by,
                metadata=metadata or {},
            )
            policy.full_clean()
            policy.save()
            logger.info(
                "update_policy.created pk=%s platform=%s target=%s",
                policy.pk, platform, target_version,
            )
            return policy
        except IntegrityError as exc:
            raise PolicyAlreadyExistsError() from exc

    @staticmethod
    @transaction.atomic
    def activate_policy(policy: AppUpdatePolicy) -> AppUpdatePolicy:
        """Move a DRAFT policy to ACTIVE and invalidate related caches."""
        policy.status = PolicyStatus.ACTIVE
        policy.full_clean()
        policy.save(update_fields=["status", "updated_at"])
        _invalidate_version_caches(policy.platform)
        logger.info("update_policy.activated pk=%s", policy.pk)
        return policy

    @staticmethod
    @transaction.atomic
    def deactivate_policy(policy: AppUpdatePolicy) -> AppUpdatePolicy:
        policy.status = PolicyStatus.INACTIVE
        policy.save(update_fields=["status", "updated_at"])
        _invalidate_version_caches(policy.platform)
        logger.info("update_policy.deactivated pk=%s", policy.pk)
        return policy


# =============================================================================
# MaintenanceService
# =============================================================================

class MaintenanceService:
    """Manages maintenance schedule lifecycle."""

    @staticmethod
    @transaction.atomic
    def create_schedule(
        *,
        title: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        description: str = "",
        platforms: list[str] | None = None,
        notify_users: bool = True,
        bypass_token: str = "",
    ) -> MaintenanceSchedule:
        """
        Create a new maintenance schedule (SCHEDULED status).
        Raises InvalidMaintenanceWindowError on bad time range.
        """
        schedule = MaintenanceSchedule(
            title=title,
            description=description,
            platforms=platforms or [],
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=MaintenanceStatus.SCHEDULED,
            notify_users=notify_users,
            bypass_token=bypass_token,
        )
        schedule.full_clean()
        schedule.save()
        logger.info(
            "maintenance.created pk=%s title=%r start=%s",
            schedule.pk, title, scheduled_start,
        )
        return schedule

    @staticmethod
    @transaction.atomic
    def start_maintenance(schedule: MaintenanceSchedule) -> MaintenanceSchedule:
        """
        Transition a SCHEDULED window to ACTIVE.
        Raises MaintenanceAlreadyActiveError if one is already running.
        """
        if MaintenanceSchedule.objects.currently_active().exists():
            raise MaintenanceAlreadyActiveError()

        schedule.status       = MaintenanceStatus.ACTIVE
        schedule.actual_start = timezone.now()
        schedule.full_clean()
        schedule.save(update_fields=["status", "actual_start", "updated_at"])
        _invalidate_maintenance_cache()
        logger.warning(
            "maintenance.started pk=%s title=%r", schedule.pk, schedule.title
        )
        return schedule

    @staticmethod
    @transaction.atomic
    def end_maintenance(schedule: MaintenanceSchedule) -> MaintenanceSchedule:
        """End an active maintenance window."""
        if schedule.status != MaintenanceStatus.ACTIVE:
            raise MaintenanceNotFoundError("Schedule is not currently active.")

        schedule.status     = MaintenanceStatus.COMPLETED
        schedule.actual_end = timezone.now()
        schedule.save(update_fields=["status", "actual_end", "updated_at"])
        _invalidate_maintenance_cache()
        logger.info(
            "maintenance.ended pk=%s title=%r", schedule.pk, schedule.title
        )
        return schedule

    @staticmethod
    @transaction.atomic
    def cancel_maintenance(schedule: MaintenanceSchedule) -> MaintenanceSchedule:
        schedule.status = MaintenanceStatus.CANCELLED
        schedule.save(update_fields=["status", "updated_at"])
        _invalidate_maintenance_cache()
        logger.info("maintenance.cancelled pk=%s", schedule.pk)
        return schedule

    @staticmethod
    def is_active_for_platform(platform: str) -> bool:
        """
        Fast check (cached) whether maintenance is currently active for platform.
        """
        cache_key = CACHE_KEY_MAINTENANCE
        cached    = _safe_cache_get(cache_key)
        if cached is not None:
            return cached

        result = MaintenanceSchedule.objects.is_active_for_platform(platform)
        _safe_cache_set(cache_key, result, CACHE_TTL_MAINTENANCE)
        return result


# =============================================================================
# RedirectService
# =============================================================================

class RedirectService:
    """Resolves the store / download URL for a platform."""

    @staticmethod
    def get_redirect_url(platform: str) -> str | None:
        """
        Return the active redirect URL for `platform`, or None if not configured.
        Result is cached.
        """
        cache_key = CACHE_KEY_REDIRECT.format(platform=platform)
        cached    = _safe_cache_get(cache_key)
        if cached is not None:
            return cached

        redirect = (
            PlatformRedirect.objects.active_for_platform(platform).first()
        )
        if redirect is None:
            return None

        _safe_cache_set(cache_key, redirect.url, CACHE_TTL_REDIRECT)
        return redirect.url


# ---------------------------------------------------------------------------
# Cache helpers (never raise)
# ---------------------------------------------------------------------------

def _safe_cache_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception:
        logger.warning("version_control.cache_get_failed key=%s", key)
        return None


def _safe_cache_set(key: str, value: Any, timeout: int) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.warning("version_control.cache_set_failed key=%s", key)


def _invalidate_version_caches(platform: str) -> None:
    """Best-effort cache invalidation for a platform's update policies."""
    try:
        from django.core.cache import cache
        # Pattern-based delete (works with Redis; noop on LocMemCache)
        pattern = f"version_control:policy:{platform}:*"
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern(pattern)
    except Exception:
        logger.warning("version_control.cache_invalidate_failed platform=%s", platform)


def _invalidate_maintenance_cache() -> None:
    try:
        cache.delete(CACHE_KEY_MAINTENANCE)
    except Exception:
        logger.warning("version_control.maintenance_cache_invalidate_failed")
