# =============================================================================
# version_control/managers.py
# =============================================================================

from __future__ import annotations

from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# AppUpdatePolicy
# ---------------------------------------------------------------------------

class AppUpdatePolicyQuerySet(models.QuerySet):

    def active(self) -> "AppUpdatePolicyQuerySet":
        from .choices import PolicyStatus
        return self.filter(status=PolicyStatus.ACTIVE)

    def for_platform(self, platform: str) -> "AppUpdatePolicyQuerySet":
        return self.filter(platform=platform)

    def critical(self) -> "AppUpdatePolicyQuerySet":
        from .choices import UpdateType
        return self.filter(update_type=UpdateType.CRITICAL)

    def required_or_critical(self) -> "AppUpdatePolicyQuerySet":
        from .choices import UpdateType
        return self.filter(
            update_type__in=[UpdateType.REQUIRED, UpdateType.CRITICAL]
        )

    def effective_for_version(self, version: str) -> "AppUpdatePolicyQuerySet":
        """
        Return active policies whose min_version <= version.
        Clients use this to find if they need to update.
        Full semver range logic is handled in the service layer.
        """
        return self.active().for_platform_version(version)

    def for_platform_version(self, version: str) -> "AppUpdatePolicyQuerySet":
        """Filter where min_version <= version (string comparison; service does semver)."""
        return self.filter(min_version__lte=version)


class AppUpdatePolicyManager(models.Manager):
    def get_queryset(self) -> AppUpdatePolicyQuerySet:
        return AppUpdatePolicyQuerySet(self.model, using=self._db)

    def active(self) -> AppUpdatePolicyQuerySet:
        return self.get_queryset().active()

    def for_platform(self, platform: str) -> AppUpdatePolicyQuerySet:
        return self.get_queryset().for_platform(platform)


# ---------------------------------------------------------------------------
# MaintenanceSchedule
# ---------------------------------------------------------------------------

class MaintenanceScheduleQuerySet(models.QuerySet):

    def active(self) -> "MaintenanceScheduleQuerySet":
        from .choices import MaintenanceStatus
        return self.filter(status=MaintenanceStatus.ACTIVE)

    def scheduled(self) -> "MaintenanceScheduleQuerySet":
        from .choices import MaintenanceStatus
        return self.filter(status=MaintenanceStatus.SCHEDULED)

    def upcoming(self) -> "MaintenanceScheduleQuerySet":
        """Scheduled windows that start in the future."""
        return self.scheduled().filter(scheduled_start__gt=timezone.now())

    def starting_soon(self, within_minutes: int = 30) -> "MaintenanceScheduleQuerySet":
        """Scheduled windows starting within `within_minutes` minutes."""
        now  = timezone.now()
        cutoff = now + timezone.timedelta(minutes=within_minutes)
        return self.scheduled().filter(
            scheduled_start__range=(now, cutoff)
        )

    def currently_active(self) -> "MaintenanceScheduleQuerySet":
        now = timezone.now()
        return self.active().filter(
            scheduled_start__lte=now,
            scheduled_end__gte=now,
        )

    def for_platform(self, platform: str) -> "MaintenanceScheduleQuerySet":
        """
        Return schedules that affect `platform`.
        Empty platforms list means all platforms → use a raw Q filter.
        """
        from django.db.models import Q
        return self.filter(
            Q(platforms__len=0) | Q(platforms__contains=[platform])
        )


class MaintenanceScheduleManager(models.Manager):
    def get_queryset(self) -> MaintenanceScheduleQuerySet:
        return MaintenanceScheduleQuerySet(self.model, using=self._db)

    def currently_active(self) -> MaintenanceScheduleQuerySet:
        return self.get_queryset().currently_active()

    def is_active_for_platform(self, platform: str) -> bool:
        return self.get_queryset().currently_active().for_platform(platform).exists()


# ---------------------------------------------------------------------------
# PlatformRedirect
# ---------------------------------------------------------------------------

class PlatformRedirectQuerySet(models.QuerySet):

    def active(self) -> "PlatformRedirectQuerySet":
        return self.filter(is_active=True)

    def for_platform(self, platform: str) -> "PlatformRedirectQuerySet":
        return self.filter(platform=platform)


class PlatformRedirectManager(models.Manager):
    def get_queryset(self) -> PlatformRedirectQuerySet:
        return PlatformRedirectQuerySet(self.model, using=self._db)

    def active_for_platform(self, platform: str) -> "PlatformRedirectQuerySet":
        return self.get_queryset().active().for_platform(platform)
