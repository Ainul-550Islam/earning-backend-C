# =============================================================================
# version_control/models.py
# =============================================================================
"""
ORM models for the version_control (App Update) application.

Models:
  - AppUpdatePolicy    : defines what action clients should take for a given
                         platform + version range.
  - MaintenanceSchedule: tracks scheduled and active maintenance windows.
  - PlatformRedirect   : maps a platform to the URL where users can get the
                         latest version (app store, web URL, etc.).
"""

from __future__ import annotations

import re
import uuid
from datetime import timedelta

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .choices import (
    MaintenanceStatus,
    Platform,
    PolicyStatus,
    RedirectType,
    UpdateType,
)
from .constants import (
    MAINTENANCE_MAX_DURATION_HOURS,
    MAX_REDIRECT_URL_LENGTH,
    MAX_VERSION_LENGTH,
    VERSION_REGEX,
)
from .exceptions import (
    InvalidMaintenanceWindowError,
    InvalidVersionStringError,
)
from .managers import (
    AppUpdatePolicyManager,
    MaintenanceScheduleManager,
    PlatformRedirectManager,
)

_version_validator = RegexValidator(
    regex=VERSION_REGEX,
    message=_(
        "Version must follow semver format: MAJOR.MINOR.PATCH[-prerelease][+build]"
    ),
)


class TimeStampedUUIDModel(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} pk={self.pk}>"


# ---------------------------------------------------------------------------
# AppUpdatePolicy
# ---------------------------------------------------------------------------

class AppUpdatePolicy(TimeStampedUUIDModel):
    """
    Defines the update action for clients on a given platform whose current
    version falls in the range [min_version, max_version).

    Fields:
      platform           : target OS / environment
      min_version        : lowest affected version (inclusive)
      max_version        : upper bound (exclusive); NULL means "all newer versions"
      target_version     : the version clients should upgrade to
      update_type        : optional / required / critical
      release_notes      : human-readable changelog (markdown)
      release_notes_url  : link to full changelog
      force_update_after : datetime after which OPTIONAL becomes REQUIRED
      status             : draft / active / inactive / archived
    """

    platform = models.CharField(
        max_length=16,
        choices=Platform.choices,
        db_index=True,
        verbose_name=_("Platform"),
    )
    min_version = models.CharField(
        max_length=MAX_VERSION_LENGTH,
        validators=[_version_validator],
        verbose_name=_("Minimum Affected Version"),
        help_text=_("Inclusive lower bound. e.g. '1.0.0'"),
    )
    max_version = models.CharField(
        max_length=MAX_VERSION_LENGTH,
        blank=True,
        default="",
        validators=[RegexValidator(
            regex=VERSION_REGEX,
            message=_("max_version must follow semver format."),
        )],
        verbose_name=_("Maximum Affected Version"),
        help_text=_("Exclusive upper bound. Leave blank to match all versions above min."),
    )
    target_version = models.CharField(
        max_length=MAX_VERSION_LENGTH,
        validators=[_version_validator],
        verbose_name=_("Target Version"),
        help_text=_("The version users should upgrade to."),
    )
    update_type = models.CharField(
        max_length=16,
        choices=UpdateType.choices,
        default=UpdateType.OPTIONAL,
        db_index=True,
        verbose_name=_("Update Type"),
    )
    release_notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Release Notes"),
        help_text=_("Markdown-formatted release notes shown in-app."),
    )
    release_notes_url = models.URLField(
        max_length=MAX_REDIRECT_URL_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Release Notes URL"),
    )
    force_update_after = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Force Update After"),
        help_text=_(
            "If set, optional updates become required after this datetime."
        ),
    )
    status = models.CharField(
        max_length=16,
        choices=PolicyStatus.choices,
        default=PolicyStatus.DRAFT,
        db_index=True,
        verbose_name=_("Policy Status"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_update_policies",
        verbose_name=_("Created By"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Extra key-value data for downstream consumers."),
    )

    objects = AppUpdatePolicyManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("App Update Policy")
        verbose_name_plural = _("App Update Policies")
        indexes = [
            models.Index(fields=["platform", "status"]),
            models.Index(fields=["update_type", "status"]),
            models.Index(fields=["target_version"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "min_version", "target_version"],
                condition=models.Q(status="active"),
                name="unique_active_policy_per_platform_version",
            )
        ]

    def __str__(self) -> str:
        return (
            f"[{self.platform}] {self.min_version}→{self.target_version} "
            f"({self.update_type}) [{self.status}]"
        )

    def clean(self) -> None:
        super().clean()
        # Validate version format explicitly (validators run on full_clean)
        for field_name in ("min_version", "target_version"):
            val = getattr(self, field_name, "")
            if val and not re.match(VERSION_REGEX, val):
                raise InvalidVersionStringError(
                    _(f"{field_name} '{val}' is not a valid semver string.")
                )

    @property
    def is_effective_required(self) -> bool:
        """
        Returns True if this policy should be treated as REQUIRED right now,
        accounting for force_update_after escalation.
        """
        if self.update_type == UpdateType.CRITICAL:
            return True
        if self.update_type == UpdateType.REQUIRED:
            return True
        if (
            self.update_type == UpdateType.OPTIONAL
            and self.force_update_after
            and timezone.now() >= self.force_update_after
        ):
            return True
        return False


# ---------------------------------------------------------------------------
# MaintenanceSchedule
# ---------------------------------------------------------------------------

class MaintenanceSchedule(TimeStampedUUIDModel):
    """
    Tracks a maintenance window for one or more platforms.

    When status=ACTIVE the middleware will return 503 responses to all
    non-staff clients for the affected platforms.
    """

    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(
        blank=True, default="", verbose_name=_("Description / User Message")
    )
    platforms = models.JSONField(
        default=list,
        verbose_name=_("Affected Platforms"),
        help_text=_("List of platform strings, e.g. ['ios', 'android']. Empty = all."),
    )
    status = models.CharField(
        max_length=16,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.SCHEDULED,
        db_index=True,
        verbose_name=_("Status"),
    )
    scheduled_start = models.DateTimeField(
        db_index=True,
        verbose_name=_("Scheduled Start"),
    )
    scheduled_end = models.DateTimeField(
        db_index=True,
        verbose_name=_("Scheduled End"),
    )
    actual_start = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Actual Start")
    )
    actual_end = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Actual End")
    )
    bypass_token = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name=_("Bypass Token"),
        help_text=_(
            "If set, requests carrying this token in X-Maintenance-Bypass "
            "header will not receive 503 responses."
        ),
    )
    notify_users = models.BooleanField(
        default=True,
        verbose_name=_("Notify Users?"),
        help_text=_("Send push notifications to affected platforms before start."),
    )

    objects = MaintenanceScheduleManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Maintenance Schedule")
        verbose_name_plural = _("Maintenance Schedules")
        indexes = [
            models.Index(fields=["status", "scheduled_start"]),
            models.Index(fields=["scheduled_start", "scheduled_end"]),
        ]

    def __str__(self) -> str:
        return (
            f"Maintenance: {self.title} "
            f"[{self.scheduled_start:%Y-%m-%d %H:%M}–{self.scheduled_end:%H:%M}] "
            f"({self.status})"
        )

    def clean(self) -> None:
        super().clean()
        if self.scheduled_end <= self.scheduled_start:
            raise InvalidMaintenanceWindowError(
                _("scheduled_end must be after scheduled_start.")
            )
        max_end = self.scheduled_start + timezone.timedelta(
            hours=MAINTENANCE_MAX_DURATION_HOURS
        )
        if self.scheduled_end > max_end:
            raise InvalidMaintenanceWindowError(
                _(
                    "Maintenance window may not exceed %(max)d hours."
                ) % {"max": MAINTENANCE_MAX_DURATION_HOURS}
            )

    @property
    def duration_minutes(self) -> int:
        delta = self.scheduled_end - self.scheduled_start
        return int(delta.total_seconds() // 60)

    @property
    def affects_all_platforms(self) -> bool:
        return not self.platforms

    def affects_platform(self, platform: str) -> bool:
        if self.affects_all_platforms:
            return True
        return platform in self.platforms


# ---------------------------------------------------------------------------
# PlatformRedirect
# ---------------------------------------------------------------------------

class PlatformRedirect(TimeStampedUUIDModel):
    """
    Maps a platform to the URL where the client can obtain the latest version.

    E.g.:
      ios     → https://apps.apple.com/…
      android → https://play.google.com/…
      web     → https://myapp.com/download
    """

    platform = models.CharField(
        max_length=16,
        choices=Platform.choices,
        unique=True,
        db_index=True,
        verbose_name=_("Platform"),
    )
    redirect_type = models.CharField(
        max_length=16,
        choices=RedirectType.choices,
        default=RedirectType.STORE,
        verbose_name=_("Redirect Type"),
    )
    url = models.URLField(
        max_length=MAX_REDIRECT_URL_LENGTH,
        verbose_name=_("Redirect URL"),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    notes     = models.TextField(blank=True, default="", verbose_name=_("Internal Notes"))

    objects = PlatformRedirectManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Platform Redirect")
        verbose_name_plural = _("Platform Redirects")
        indexes = [
            models.Index(fields=["platform", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Redirect[{self.platform}] → {self.url[:60]}"
