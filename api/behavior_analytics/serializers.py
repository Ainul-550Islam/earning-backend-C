# =============================================================================
# behavior_analytics/serializers.py
# =============================================================================
"""
DRF serializers for the behavior_analytics application.

Design rules:
  - Serializers validate; they do NOT perform DB writes (leave that to services).
  - validate_* methods raise serializers.ValidationError, never raw exceptions.
  - Nested serializers are read-only on parent write endpoints.
  - Extra fields (read_only=True) are declared explicitly so we never leak
    internal fields accidentally.
  - to_representation overrides are used for computed / derived fields.
"""

from __future__ import annotations

from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import ClickCategory, DeviceType, EngagementTier, SessionStatus
from .constants import (
    ENGAGEMENT_SCORE_MAX,
    ENGAGEMENT_SCORE_MIN,
    MAX_CLICK_METRICS_PER_SESSION,
    MAX_PATH_NODES,
    MAX_URL_LENGTH,
    STAY_TIME_MAX_SECONDS,
    STAY_TIME_MIN_SECONDS,
)
from .models import ClickMetric, EngagementScore, StayTime, UserPath


# ---------------------------------------------------------------------------
# Lightweight nested serializers (read-only, used inside parent responses)
# ---------------------------------------------------------------------------

class StayTimeInlineSerializer(serializers.ModelSerializer):
    """Minimal StayTime representation embedded inside UserPath responses."""

    is_bounce = serializers.SerializerMethodField()

    class Meta:
        model  = StayTime
        fields = ["id", "page_url", "duration_seconds", "is_active_time",
                  "scroll_depth_percent", "is_bounce"]
        read_only_fields = fields

    def get_is_bounce(self, obj: StayTime) -> bool:
        return obj.is_bounce


class ClickMetricInlineSerializer(serializers.ModelSerializer):
    """Minimal ClickMetric representation embedded inside UserPath responses."""

    class Meta:
        model  = ClickMetric
        fields = ["id", "page_url", "element_selector", "element_text",
                  "category", "clicked_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# UserPath
# ---------------------------------------------------------------------------

class UserPathSerializer(serializers.ModelSerializer):
    """
    Full read/write serializer for UserPath.
    On write, only a subset of fields is accepted.
    """

    depth        = serializers.SerializerMethodField(read_only=True)
    is_bounce    = serializers.SerializerMethodField(read_only=True)
    user_display = serializers.SerializerMethodField(read_only=True)
    stay_times = StayTimeInlineSerializer(many=True, read_only=True)
    click_metrics = ClickMetricInlineSerializer(many=True, read_only=True)

    class Meta:
        model  = UserPath
        fields = [
            "id", "user_display", "session_id", "device_type", "status",
            "entry_url", "exit_url", "nodes",
            "depth", "is_bounce",
            "stay_times", "click_metrics",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "user_display", "depth", "is_bounce",
            "stay_times", "click_metrics",
            "created_at", "updated_at",
        ]

    # ------------------------------------------------------------------
    # Field-level validation
    # ------------------------------------------------------------------

    def validate_session_id(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError(_("session_id may not be blank."))
        if len(value) > 128:
            raise serializers.ValidationError(_("session_id may not exceed 128 characters."))
        return value

    def validate_nodes(self, value: list) -> list:
        if not isinstance(value, list):
            raise serializers.ValidationError(_("nodes must be a JSON list."))
        if len(value) > MAX_PATH_NODES:
            raise serializers.ValidationError(
                _("nodes exceeds the maximum allowed count of %(max)d.") % {"max": MAX_PATH_NODES}
            )
        for idx, node in enumerate(value):
            if not isinstance(node, dict):
                raise serializers.ValidationError(
                    _("Node at index %(i)d must be a JSON object.") % {"i": idx}
                )
            url = node.get("url", "")
            if len(url) > MAX_URL_LENGTH:
                raise serializers.ValidationError(
                    _("URL at node %(i)d exceeds %(max)d characters.") % {
                        "i": idx, "max": MAX_URL_LENGTH
                    }
                )
        return value

    def validate_entry_url(self, value: str) -> str:
        if len(value) > MAX_URL_LENGTH:
            raise serializers.ValidationError(
                _("entry_url exceeds the maximum length of %(max)d.") % {"max": MAX_URL_LENGTH}
            )
        return value

    def validate_exit_url(self, value: str) -> str:
        if len(value) > MAX_URL_LENGTH:
            raise serializers.ValidationError(
                _("exit_url exceeds the maximum length of %(max)d.") % {"max": MAX_URL_LENGTH}
            )
        return value

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    def get_user_display(self, obj: UserPath) -> str:
        u = getattr(obj, 'user', None)
        if not u:
            return 'Unknown'
        return getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', '') or str(u)

    def get_depth(self, obj: UserPath) -> int:
        return obj.depth

    def get_is_bounce(self, obj: UserPath) -> bool:
        return obj.is_bounce


class UserPathCreateSerializer(serializers.ModelSerializer):
    """
    Lightweight write-only serializer for creating a new UserPath.
    Does not expose nested relations to keep payloads small.
    """

    class Meta:
        model  = UserPath
        fields = ["session_id", "device_type", "entry_url", "nodes"]

    def validate_nodes(self, value: list) -> list:
        # reuse parent logic
        return UserPathSerializer().validate_nodes(value)


# ---------------------------------------------------------------------------
# ClickMetric
# ---------------------------------------------------------------------------

class ClickMetricSerializer(serializers.ModelSerializer):

    class Meta:
        model  = ClickMetric
        fields = [
            "id", "path", "page_url", "element_selector", "element_text",
            "category", "x_position", "y_position",
            "viewport_width", "viewport_height",
            "clicked_at", "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "path":     {"write_only": True},
            "metadata": {"required": False},
        }

    def validate_page_url(self, value: str) -> str:
        if len(value) > MAX_URL_LENGTH:
            raise serializers.ValidationError(
                _("page_url exceeds %(max)d characters.") % {"max": MAX_URL_LENGTH}
            )
        return value

    def validate_element_selector(self, value: str) -> str:
        if len(value) > 512:
            raise serializers.ValidationError(
                _("element_selector must not exceed 512 characters.")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        # Guard against absurd coordinate values
        for field in ("x_position", "y_position"):
            val = attrs.get(field)
            if val is not None and val > 100_000:
                raise serializers.ValidationError(
                    {field: _("Coordinate value %(v)s is unrealistically large.") % {"v": val}}
                )
        return attrs


class ClickMetricEventSerializer(serializers.Serializer):
    """
    ✅ FIXED: Lightweight serializer for individual events inside a bulk request.
    Does NOT include 'path' field — path is provided at the top level (path_id).
    """
    page_url         = serializers.URLField(max_length=MAX_URL_LENGTH)
    element_selector = serializers.CharField(max_length=512, required=False, default="")
    element_text     = serializers.CharField(max_length=256, required=False, default="")
    category         = serializers.ChoiceField(choices=ClickCategory.choices, required=False, default=ClickCategory.OTHER)
    x_position       = serializers.IntegerField(required=False, allow_null=True, default=None)
    y_position       = serializers.IntegerField(required=False, allow_null=True, default=None)
    viewport_width   = serializers.IntegerField(required=False, allow_null=True, default=None)
    viewport_height  = serializers.IntegerField(required=False, allow_null=True, default=None)
    clicked_at       = serializers.DateTimeField(required=False, allow_null=True, default=None)
    metadata         = serializers.DictField(required=False, default=dict)


class ClickMetricBulkSerializer(serializers.Serializer):
    """
    Accepts a list of click events in one request.
    The service layer is responsible for persisting them in bulk.
    ✅ FIXED: events now uses ClickMetricEventSerializer (no 'path' field required per event).
    """

    path_id = serializers.UUIDField(required=False)
    path    = serializers.UUIDField(required=False)
    # ✅ FIXED: was ClickMetricSerializer (requires path per event) → now ClickMetricEventSerializer
    events  = ClickMetricEventSerializer(many=True)

    def validate(self, attrs):
        # Accept both 'path' and 'path_id'
        if 'path' in attrs and 'path_id' not in attrs:
            attrs['path_id'] = attrs.pop('path')
        if 'path_id' not in attrs:
            raise serializers.ValidationError({'path_id': 'This field is required.'})
        return attrs

    def validate_events(self, value: list) -> list:
        if not value:
            raise serializers.ValidationError(_("events list must not be empty."))
        if len(value) > MAX_CLICK_METRICS_PER_SESSION:
            raise serializers.ValidationError(
                _("Batch exceeds maximum of %(max)d events.") % {
                    "max": MAX_CLICK_METRICS_PER_SESSION
                }
            )
        return value


# ---------------------------------------------------------------------------
# StayTime
# ---------------------------------------------------------------------------

class StayTimeSerializer(serializers.ModelSerializer):

    is_bounce = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = StayTime
        fields = [
            "id", "path", "page_url",
            "duration_seconds", "is_active_time", "scroll_depth_percent",
            "is_bounce", "created_at",
        ]
        read_only_fields = ["id", "is_bounce", "created_at"]
        extra_kwargs = {
            "path": {"write_only": True},
        }

    def validate_duration_seconds(self, value: int) -> int:
        if not (STAY_TIME_MIN_SECONDS <= value <= STAY_TIME_MAX_SECONDS):
            raise serializers.ValidationError(
                _(
                    "duration_seconds must be between %(min)d and %(max)d."
                ) % {
                    "min": STAY_TIME_MIN_SECONDS,
                    "max": STAY_TIME_MAX_SECONDS,
                }
            )
        return value

    def validate_scroll_depth_percent(self, value: int | None) -> int | None:
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(_("scroll_depth_percent must be 0–100."))
        return value

    def get_is_bounce(self, obj: StayTime) -> bool:
        return obj.is_bounce


# ---------------------------------------------------------------------------
# EngagementScore
# ---------------------------------------------------------------------------

class EngagementScoreSerializer(serializers.ModelSerializer):

    tier_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = EngagementScore
        fields = [
            "id", "user", "date", "score", "tier", "tier_label",
            "click_count", "total_stay_sec", "path_depth", "return_visits",
            "breakdown_json",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tier_label", "breakdown_json", "created_at", "updated_at"
        ]
        extra_kwargs = {
            "user": {"read_only": True},
        }

    def validate_score(self, value: Decimal) -> Decimal:
        val = Decimal(str(value))
        lo  = Decimal(str(ENGAGEMENT_SCORE_MIN))
        hi  = Decimal(str(ENGAGEMENT_SCORE_MAX))
        if not (lo <= val <= hi):
            raise serializers.ValidationError(
                _("score must be between %(min)s and %(max)s.") % {
                    "min": lo, "max": hi
                }
            )
        return val

    def get_tier_label(self, obj: EngagementScore) -> str:
        return obj.get_tier_display_verbose()


class EngagementScoreSummarySerializer(serializers.Serializer):
    """
    Read-only summary serializer returned by the analytics engine
    after a recalculation run.
    """
    user_id      = serializers.UUIDField(read_only=True)
    date         = serializers.DateField(read_only=True)
    score        = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    tier         = serializers.ChoiceField(choices=EngagementTier.choices, read_only=True)
    click_count  = serializers.IntegerField(read_only=True)
    total_stay_sec = serializers.IntegerField(read_only=True)
    path_depth   = serializers.IntegerField(read_only=True)
    return_visits = serializers.IntegerField(read_only=True)