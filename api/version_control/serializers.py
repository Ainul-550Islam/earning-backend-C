# =============================================================================
# version_control/serializers.py
# =============================================================================

from __future__ import annotations

import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import MaintenanceStatus, Platform, PolicyStatus, RedirectType, UpdateType
from .constants import ALL_PLATFORMS, MAX_REDIRECT_URL_LENGTH, MAX_VERSION_LENGTH, VERSION_REGEX
from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_version(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise serializers.ValidationError(_(f"{field_name} may not be blank."))
    if len(value) > MAX_VERSION_LENGTH:
        raise serializers.ValidationError(
            _(f"{field_name} exceeds maximum length of {MAX_VERSION_LENGTH}.")
        )
    if not re.match(VERSION_REGEX, value):
        raise serializers.ValidationError(
            _(f"{field_name} must follow semver format (e.g. '1.2.3'). Got: '{value}'")
        )
    return value


# ---------------------------------------------------------------------------
# AppUpdatePolicy
# ---------------------------------------------------------------------------

class AppUpdatePolicySerializer(serializers.ModelSerializer):

    is_effective_required = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = AppUpdatePolicy
        fields = [
            "id", "platform", "min_version", "max_version",
            "target_version", "update_type", "status",
            "release_notes", "release_notes_url",
            "force_update_after",
            "is_effective_required",
            "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_effective_required", "created_at", "updated_at"]

    def validate_min_version(self, value: str) -> str:
        return _validate_version(value, "min_version")

    def validate_target_version(self, value: str) -> str:
        return _validate_version(value, "target_version")

    def validate_max_version(self, value: str) -> str:
        if not value:
            return value
        return _validate_version(value, "max_version")

    def validate_platform(self, value: str) -> str:
        if value not in ALL_PLATFORMS:
            raise serializers.ValidationError(
                _(f"Unknown platform '{value}'. Valid: {', '.join(ALL_PLATFORMS)}")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        min_v    = attrs.get("min_version", "")
        target_v = attrs.get("target_version", "")
        if min_v and target_v and min_v == target_v:
            raise serializers.ValidationError(
                {"target_version": _("target_version must differ from min_version.")}
            )
        force_after = attrs.get("force_update_after")
        update_type = attrs.get("update_type", "")
        if force_after and update_type != UpdateType.OPTIONAL:
            raise serializers.ValidationError(
                {"force_update_after": _(
                    "force_update_after is only valid for 'optional' update type."
                )}
            )
        return attrs

    def get_is_effective_required(self, obj: AppUpdatePolicy) -> bool:
        return obj.is_effective_required


class AppUpdatePolicyCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer for creating a new DRAFT policy."""

    class Meta:
        model  = AppUpdatePolicy
        fields = [
            "platform", "min_version", "max_version",
            "target_version", "update_type",
            "release_notes", "release_notes_url",
            "force_update_after", "metadata",
        ]

    def validate_min_version(self, value: str) -> str:
        return _validate_version(value, "min_version")

    def validate_target_version(self, value: str) -> str:
        return _validate_version(value, "target_version")

    def validate_max_version(self, value: str) -> str:
        if not value:
            return value
        return _validate_version(value, "max_version")

    def validate_platform(self, value: str) -> str:
        if value not in ALL_PLATFORMS:
            raise serializers.ValidationError(
                _(f"Unknown platform '{value}'.")
            )
        return value


# ---------------------------------------------------------------------------
# VersionCheckResult  (read-only response shape)
# ---------------------------------------------------------------------------

class VersionCheckResultSerializer(serializers.Serializer):
    """
    Serialises the dict returned by VersionCheckService.check().
    Used only for response rendering — never for writes.
    """
    update_required   = serializers.BooleanField(read_only=True)
    update_type       = serializers.CharField(allow_null=True, read_only=True)
    target_version    = serializers.CharField(allow_null=True, read_only=True)
    release_notes     = serializers.CharField(allow_null=True, read_only=True)
    release_notes_url = serializers.URLField(allow_null=True, read_only=True)
    force_update_at   = serializers.CharField(allow_null=True, read_only=True)


# ---------------------------------------------------------------------------
# MaintenanceSchedule
# ---------------------------------------------------------------------------

class MaintenanceScheduleSerializer(serializers.ModelSerializer):

    duration_minutes  = serializers.SerializerMethodField(read_only=True)
    affects_all       = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = MaintenanceSchedule
        fields = [
            "id", "title", "description",
            "platforms", "status",
            "scheduled_start", "scheduled_end",
            "actual_start", "actual_end",
            "bypass_token", "notify_users",
            "duration_minutes", "affects_all",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status",
            "actual_start", "actual_end",
            "duration_minutes", "affects_all",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "bypass_token": {"write_only": True},
        }

    def validate_platforms(self, value: list) -> list:
        if not isinstance(value, list):
            raise serializers.ValidationError(_("platforms must be a JSON list."))
        invalid = [p for p in value if p not in ALL_PLATFORMS]
        if invalid:
            raise serializers.ValidationError(
                _(f"Unknown platform(s): {', '.join(invalid)}. "
                  f"Valid: {', '.join(ALL_PLATFORMS)}")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("scheduled_start")
        end   = attrs.get("scheduled_end")
        if start and end:
            if end <= start:
                raise serializers.ValidationError(
                    {"scheduled_end": _("scheduled_end must be after scheduled_start.")}
                )
            from .constants import MAINTENANCE_MAX_DURATION_HOURS
            from datetime import timedelta
            max_end = start + timedelta(hours=MAINTENANCE_MAX_DURATION_HOURS)
            if end > max_end:
                raise serializers.ValidationError(
                    {"scheduled_end": _(
                        f"Maintenance window cannot exceed "
                        f"{MAINTENANCE_MAX_DURATION_HOURS} hours."
                    )}
                )
        return attrs

    def get_duration_minutes(self, obj: MaintenanceSchedule) -> int:
        return obj.duration_minutes

    def get_affects_all(self, obj: MaintenanceSchedule) -> bool:
        return obj.affects_all_platforms


class MaintenanceScheduleCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer used when scheduling a new maintenance window."""

    class Meta:
        model  = MaintenanceSchedule
        fields = [
            "title", "description", "platforms",
            "scheduled_start", "scheduled_end",
            "notify_users", "bypass_token",
        ]

    def validate_platforms(self, value: list) -> list:
        return MaintenanceScheduleSerializer().validate_platforms(value)

    def validate(self, attrs: dict) -> dict:
        return MaintenanceScheduleSerializer().validate(attrs)


class MaintenanceStatusSerializer(serializers.Serializer):
    """
    Lightweight response returned by the 'is_active' endpoint.
    """
    is_active        = serializers.BooleanField(read_only=True)
    platform         = serializers.CharField(read_only=True)
    title            = serializers.CharField(allow_null=True, read_only=True)
    description      = serializers.CharField(allow_null=True, read_only=True)
    scheduled_end    = serializers.DateTimeField(allow_null=True, read_only=True)


# ---------------------------------------------------------------------------
# PlatformRedirect
# ---------------------------------------------------------------------------

class PlatformRedirectSerializer(serializers.ModelSerializer):

    class Meta:
        model  = PlatformRedirect
        fields = [
            "id", "platform", "redirect_type",
            "url", "is_active", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_platform(self, value: str) -> str:
        if value not in ALL_PLATFORMS:
            raise serializers.ValidationError(
                _(f"Unknown platform '{value}'.")
            )
        return value

    def validate_url(self, value: str) -> str:
        if len(value) > MAX_REDIRECT_URL_LENGTH:
            raise serializers.ValidationError(
                _(f"URL exceeds maximum length of {MAX_REDIRECT_URL_LENGTH}.")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        # On create, prevent duplicate active redirects per platform
        if self.instance is None:
            platform  = attrs.get("platform", "")
            is_active = attrs.get("is_active", True)
            if is_active and platform:
                exists = PlatformRedirect.objects.active_for_platform(platform).exists()
                if exists:
                    raise serializers.ValidationError(
                        {"platform": _(
                            f"An active redirect for platform '{platform}' already exists. "
                            "Deactivate it first or set is_active=false."
                        )}
                    )
        return attrs
