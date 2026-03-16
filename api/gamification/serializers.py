"""
Gamification Serializers — DRF serializers with full validation.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import ContestCycleStatus, RewardType, AchievementType, LeaderboardScope
from .constants import (
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    MAX_META_JSON_SIZE_BYTES,
)
from .models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ContestCycle
# ---------------------------------------------------------------------------

class ContestCycleSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField(read_only=True)
    is_expired = serializers.SerializerMethodField(read_only=True)
    duration_days = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ContestCycle
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "points_multiplier",
            "is_featured",
            "max_participants",
            "metadata",
            "is_active",
            "is_expired",
            "duration_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_active(self, obj: ContestCycle) -> bool:
        return obj.is_active

    def get_is_expired(self, obj: ContestCycle) -> bool:
        return obj.is_expired

    def get_duration_days(self, obj: ContestCycle) -> int | None:
        return obj.duration_days

    def validate_points_multiplier(self, value: Decimal) -> Decimal:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError(
                _("points_multiplier must be a valid decimal number.")
            )
        if d <= 0:
            raise serializers.ValidationError(
                _("points_multiplier must be positive.")
            )
        if d > Decimal("100.00"):
            raise serializers.ValidationError(
                _("points_multiplier cannot exceed 100.00.")
            )
        return d

    def validate_max_participants(self, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise serializers.ValidationError(
                _("max_participants must be at least 1.")
            )
        return value

    def validate_metadata(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("metadata must be a JSON object."))
        import json
        try:
            encoded = json.dumps(value).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                _(f"metadata is not serialisable: {exc}")
            )
        if len(encoded) > MAX_META_JSON_SIZE_BYTES:
            raise serializers.ValidationError(
                _(f"metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start_date") or (self.instance.start_date if self.instance else None)
        end = attrs.get("end_date") or (self.instance.end_date if self.instance else None)
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"end_date": _("end_date must be strictly after start_date.")}
            )
        return attrs


class ContestCycleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints."""
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ContestCycle
        fields = ["id", "name", "slug", "status", "status_display", "start_date", "end_date", "is_featured"]


# ---------------------------------------------------------------------------
# LeaderboardSnapshot
# ---------------------------------------------------------------------------

class LeaderboardEntrySerializer(serializers.Serializer):
    """Validates a single leaderboard entry dict within snapshot_data."""
    rank = serializers.IntegerField(min_value=1, max_value=MAX_RANK_VALUE)
    user_id = serializers.CharField(max_length=255)
    display_name = serializers.CharField(max_length=255, required=False, default="")
    points = serializers.IntegerField(min_value=0)
    delta_rank = serializers.IntegerField(required=False, allow_null=True, default=None)


class LeaderboardSnapshotSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_finalized = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeaderboardSnapshot
        fields = [
            "id",
            "contest_cycle",
            "scope",
            "scope_ref",
            "snapshot_data",
            "top_n",
            "status",
            "status_display",
            "is_finalized",
            "generated_at",
            "checksum",
            "entry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "generated_at",
            "checksum",
            "created_at",
            "updated_at",
        ]

    def get_entry_count(self, obj: LeaderboardSnapshot) -> int:
        return obj.entry_count

    def validate_scope(self, value: str) -> str:
        if value not in LeaderboardScope.values:
            raise serializers.ValidationError(
                _(f"Invalid scope. Valid choices: {LeaderboardScope.values}")
            )
        return value

    def validate_top_n(self, value: int) -> int:
        if not isinstance(value, int) or value < 1 or value > 1000:
            raise serializers.ValidationError(
                _("top_n must be between 1 and 1000.")
            )
        return value


# ---------------------------------------------------------------------------
# ContestReward
# ---------------------------------------------------------------------------

class ContestRewardSerializer(serializers.ModelSerializer):
    is_exhausted = serializers.BooleanField(read_only=True)
    remaining_budget = serializers.SerializerMethodField(read_only=True)
    reward_type_display = serializers.CharField(source="get_reward_type_display", read_only=True)

    class Meta:
        model = ContestReward
        fields = [
            "id",
            "contest_cycle",
            "title",
            "description",
            "reward_type",
            "reward_type_display",
            "reward_value",
            "rank_from",
            "rank_to",
            "total_budget",
            "issued_count",
            "is_active",
            "is_exhausted",
            "remaining_budget",
            "image_url",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "issued_count", "created_at", "updated_at"]

    def get_remaining_budget(self, obj: ContestReward) -> int | None:
        return obj.remaining_budget

    def validate_reward_type(self, value: str) -> str:
        if value not in RewardType.values:
            raise serializers.ValidationError(
                _(f"Invalid reward_type. Valid choices: {RewardType.values}")
            )
        return value

    def validate_rank_from(self, value: int) -> int:
        if value < 1 or value > MAX_RANK_VALUE:
            raise serializers.ValidationError(
                _(f"rank_from must be between 1 and {MAX_RANK_VALUE}.")
            )
        return value

    def validate_rank_to(self, value: int) -> int:
        if value < 1 or value > MAX_RANK_VALUE:
            raise serializers.ValidationError(
                _(f"rank_to must be between 1 and {MAX_RANK_VALUE}.")
            )
        return value

    def validate(self, attrs: dict) -> dict:
        rank_from = attrs.get("rank_from") or (self.instance.rank_from if self.instance else None)
        rank_to = attrs.get("rank_to") or (self.instance.rank_to if self.instance else None)
        if rank_from and rank_to and rank_from > rank_to:
            raise serializers.ValidationError(
                {"rank_to": _("rank_to must be >= rank_from.")}
            )

        total_budget = attrs.get("total_budget")
        if total_budget is not None and total_budget < 1:
            raise serializers.ValidationError(
                {"total_budget": _("total_budget must be at least 1 if set.")}
            )
        return attrs

    def validate_reward_value(self, value: Decimal) -> Decimal:
        try:
            d = Decimal(str(value))
            if d < 0:
                raise serializers.ValidationError(_("reward_value must be non-negative."))
            return d
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError(_("reward_value must be a valid decimal."))


# ---------------------------------------------------------------------------
# UserAchievement
# ---------------------------------------------------------------------------

class UserAchievementSerializer(serializers.ModelSerializer):
    achievement_type_display = serializers.CharField(
        source="get_achievement_type_display", read_only=True
    )
    is_cycle_scoped = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserAchievement
        fields = [
            "id",
            "user",
            "contest_cycle",
            "contest_reward",
            "achievement_type",
            "achievement_type_display",
            "title",
            "description",
            "points_awarded",
            "rank_at_award",
            "is_awarded",
            "awarded_at",
            "is_notified",
            "notified_at",
            "is_cycle_scoped",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_awarded",
            "awarded_at",
            "is_notified",
            "notified_at",
            "created_at",
            "updated_at",
        ]

    def validate_achievement_type(self, value: str) -> str:
        if value not in AchievementType.values:
            raise serializers.ValidationError(
                _(f"Invalid achievement_type. Valid choices: {AchievementType.values}")
            )
        return value

    def validate_points_awarded(self, value: int) -> int:
        if not isinstance(value, int) or value < MIN_POINTS_VALUE or value > MAX_POINTS_VALUE:
            raise serializers.ValidationError(
                _(f"points_awarded must be between {MIN_POINTS_VALUE} and {MAX_POINTS_VALUE}.")
            )
        return value
