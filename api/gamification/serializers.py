"""
Gamification Serializers — DRF serializers with full validation.
Enhanced with integration system monitoring, audit logging, and SHA-256 verification.
"""

from __future__ import annotations
from typing import Optional

import logging
import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Any, Dict

User = get_user_model()

from api.gamification.choices import ContestCycleStatus, RewardType, AchievementType, LeaderboardScope, BadgeRarity, BadgeCriteriaType, ChallengeAction, ChallengeStatus, StreakStatus, LevelPerkType
from api.gamification.constants import (
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    MAX_META_JSON_SIZE_BYTES,
)
from api.gamification.models import (
    ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement,
    UserPoints, PointsTransaction, StreakFreeze, ContestParticipant, 
    GamificationConfig, GamificationInsight, Badge, UserBadge, DailyChallenge, 
    UserDailyChallenge, Streak, StreakReward, LevelConfig,
    WebhookEndpoint,
    WebhookEvent,
    WebhookDelivery,)

# Import integration system components
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ContestCycle
# ---------------------------------------------------------------------------

class ContestCycleSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField(read_only=True)
    is_expired = serializers.SerializerMethodField(read_only=True)
    duration_days = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)
    health_status = serializers.SerializerMethodField(read_only=True)

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
            "checksum",
            "integration_sync_id",
            "health_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "checksum", "integration_sync_id"]

    def get_is_active(self, obj: ContestCycle) -> bool:
        return obj.is_active

    def get_is_expired(self, obj: ContestCycle) -> bool:
        return obj.is_expired

    def get_duration_days(self, obj: ContestCycle) -> int | None:
        return obj.duration_days

    def get_health_status(self, obj: ContestCycle) -> str:
        """Get health status from integration system."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.health_check import health_manager
            
            # Get health status for this contest cycle
            health_result = health_manager.check_resource_health(
                resource_type="contest_cycle",
                resource_id=str(obj.id)
            )
            return health_result.status.value if health_result else "unknown"
        except Exception:
            return "unknown"

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
        
        # Log validation with integration system
        try:
            audit_logger.log_audit(
                action=audit_logger.AuditAction.VALIDATE,
                description=f"ContestCycle metadata validation performed",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                details={
                    "metadata_size": len(encoded),
                    "validation_result": "success"
                }
            )
            performance_monitor.record_metric("metadata_validation_size", len(encoded))
        except Exception:
            pass  # Don't fail validation if integration system is unavailable
        
        return value

    def create(self, validated_data: dict) -> ContestCycle:
        """Create ContestCycle with integration system monitoring."""
        try:
            # Record creation metrics
            start_time = timezone.now()
            
            # Log creation attempt
            audit_logger.log_audit(
                action=audit_logger.AuditAction.CREATE,
                description=f"ContestCycle creation attempted: {validated_data.get('name', 'unnamed')}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                details={
                    "name": validated_data.get("name"),
                    "status": validated_data.get("status"),
                    "points_multiplier": str(validated_data.get("points_multiplier", "1.00"))
                }
            )
            
            instance = super().create(validated_data)
            
            # Calculate creation duration
            creation_duration = (timezone.now() - start_time).total_seconds()
            
            # Record success metrics
            performance_monitor.record_metric("contest_cycle_creation_duration", creation_duration)
            performance_monitor.record_metric("contest_cycle_creation_count", 1.0)
            
            # Log successful creation
            audit_logger.log_audit(
                action=audit_logger.AuditAction.CREATE,
                description=f"ContestCycle created successfully: {instance.name}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                resource_id=str(instance.id),
                details={
                    "creation_duration": creation_duration,
                    "checksum": instance.checksum
                }
            )
            
            return instance
            
        except Exception as exc:
            # Log creation error
            audit_logger.log_audit(
                action=audit_logger.AuditAction.ERROR,
                description=f"ContestCycle creation failed: {exc}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                error=str(exc)
            )
            
            performance_monitor.record_metric("contest_cycle_creation_error", 1.0)
            raise exc

    def update(self, instance: ContestCycle, validated_data: dict) -> ContestCycle:
        """Update ContestCycle with integration system monitoring."""
        try:
            # Record update metrics
            start_time = timezone.now()
            
            # Log update attempt
            audit_logger.log_audit(
                action=audit_logger.AuditAction.UPDATE,
                description=f"ContestCycle update attempted: {instance.name}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                resource_id=str(instance.id),
                details={
                    "updated_fields": list(validated_data.keys()),
                    "old_checksum": instance.checksum
                }
            )
            
            updated_instance = super().update(instance, validated_data)
            
            # Calculate update duration
            update_duration = (timezone.now() - start_time).total_seconds()
            
            # Record success metrics
            performance_monitor.record_metric("contest_cycle_update_duration", update_duration)
            performance_monitor.record_metric("contest_cycle_update_count", 1.0)
            
            # Log successful update
            audit_logger.log_audit(
                action=audit_logger.AuditAction.UPDATE,
                description=f"ContestCycle updated successfully: {instance.name}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                resource_id=str(instance.id),
                details={
                    "update_duration": update_duration,
                    "new_checksum": updated_instance.checksum,
                    "checksum_changed": instance.checksum != updated_instance.checksum
                }
            )
            
            return updated_instance
            
        except Exception as exc:
            # Log update error
            audit_logger.log_audit(
                action=audit_logger.AuditAction.ERROR,
                description=f"ContestCycle update failed: {exc}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                resource_id=str(instance.id),
                error=str(exc)
            )
            
            performance_monitor.record_metric("contest_cycle_update_error", 1.0)
            raise exc

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


# ---------------------------------------------------------------------------
# UserPoints Serializer
# ---------------------------------------------------------------------------

class UserPointsSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    monthly_rank = serializers.SerializerMethodField(read_only=True)
    weekly_rank = serializers.SerializerMethodField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = UserPoints
        fields = [
            "id", "user", "total_points", "lifetime_points", "points_this_month",
            "points_this_week", "monthly_rank", "weekly_rank", "last_updated",
            "created_at", "updated_at", "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "checksum", "integration_sync_id"]

    def get_monthly_rank(self, obj) -> Optional[int]:
        return obj.monthly_rank

    def get_weekly_rank(self, obj) -> Optional[int]:
        return obj.weekly_rank

    def validate_total_points(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Total points cannot be negative."))
        return value

    def validate_lifetime_points(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Lifetime points cannot be negative."))
        return value

    def validate(self, attrs):
        # Validate lifetime points >= total points
        if attrs.get("lifetime_points", 0) < attrs.get("total_points", 0):
            raise serializers.ValidationError(
                _("Lifetime points cannot be less than total points.")
            )
        return attrs


# ---------------------------------------------------------------------------
# PointsTransaction Serializer
# ---------------------------------------------------------------------------

class PointsTransactionSerializer(serializers.ModelSerializer):
    is_deduction = serializers.SerializerMethodField()

    def get_is_deduction(self, obj):
        return obj.is_deduction()

    user = serializers.PrimaryKeyRelatedField(read_only=True)
    is_earning = serializers.SerializerMethodField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = PointsTransaction
        fields = [
            "id", "user", "amount", "source", "source_id", "description",
            "balance_after", "is_earning", "created_at", "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "created_at", "checksum", "integration_sync_id"]

    def get_is_earning(self, obj) -> bool:
        return obj.is_earning

    def validate_amount(self, value) -> int:
        if value == 0:
            raise serializers.ValidationError(_("Transaction amount cannot be zero."))
        return value

    def validate_source(self, value) -> str:
        valid_sources = ["offer", "referral", "streak", "challenge", "contest", "manual", "bonus", "penalty"]
        if value not in valid_sources:
            raise serializers.ValidationError(
                _(f"Invalid source. Must be one of: {', '.join(valid_sources)}")
            )
        return value

    def validate_balance_after(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Balance after transaction cannot be negative."))
        return value


# ---------------------------------------------------------------------------
# StreakFreeze Serializer
# ---------------------------------------------------------------------------

class StreakFreezeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    streak = serializers.PrimaryKeyRelatedField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = StreakFreeze
        fields = [
            "id", "user", "streak", "used_at", "reason", "created_at",
            "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "created_at", "checksum", "integration_sync_id"]

    def validate_used_at(self, value) -> str:
        if value > timezone.now().date():
            raise serializers.ValidationError(_("Streak freeze date cannot be in the future."))
        return value

    def validate_reason(self, value) -> str:
        if len(value) > 255:
            raise serializers.ValidationError(_("Reason cannot exceed 255 characters."))
        return value


# ---------------------------------------------------------------------------
# ContestParticipant Serializer
# ---------------------------------------------------------------------------

class ContestParticipantSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    contest_cycle = serializers.PrimaryKeyRelatedField(read_only=True)
    is_ranked = serializers.SerializerMethodField(read_only=True)
    days_in_contest = serializers.SerializerMethodField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = ContestParticipant
        fields = [
            "id", "user", "contest_cycle", "joined_at", "current_points",
            "current_rank", "is_disqualified", "is_ranked", "days_in_contest",
            "created_at", "updated_at", "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "joined_at", "created_at", "updated_at", "checksum", "integration_sync_id"]

    def get_is_ranked(self, obj) -> bool:
        return obj.is_ranked

    def get_days_in_contest(self, obj) -> int:
        return obj.days_in_contest

    def validate_current_points(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Current points cannot be negative."))
        return value

    def validate_current_rank(self, value) -> Optional[int]:
        if value is not None and value <= 0:
            raise serializers.ValidationError(_("Current rank must be positive."))
        return value

    def validate(self, attrs):
        # Disqualified users should not have ranks
        if attrs.get("is_disqualified", False) and attrs.get("current_rank") is not None:
            raise serializers.ValidationError(
                _("Disqualified participants cannot have ranks.")
            )
        return attrs


# ---------------------------------------------------------------------------
# GamificationConfig Serializer
# ---------------------------------------------------------------------------

class GamificationConfigSerializer(serializers.ModelSerializer):
    tenant = serializers.PrimaryKeyRelatedField(read_only=True)
    features_enabled = serializers.SerializerMethodField(read_only=True)
    is_points_expiry_enabled = serializers.SerializerMethodField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = GamificationConfig
        fields = [
            "id", "tenant", "enable_contests", "enable_badges", "enable_streaks",
            "enable_levels", "enable_daily_challenges", "points_expiry_days",
            "leaderboard_refresh_interval", "features_enabled", "is_points_expiry_enabled",
            "created_at", "updated_at", "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "checksum", "integration_sync_id"]

    def get_features_enabled(self, obj) -> list[str]:
        return obj.features_enabled

    def get_is_points_expiry_enabled(self, obj) -> bool:
        return obj.is_points_expiry_enabled

    def validate_leaderboard_refresh_interval(self, value) -> int:
        if not (60 <= value <= 3600):
            raise serializers.ValidationError(
                _("Leaderboard refresh interval must be between 60 and 3600 seconds.")
            )
        return value

    def validate_points_expiry_days(self, value) -> Optional[int]:
        if value is not None and value < 1:
            raise serializers.ValidationError(_("Points expiry days must be at least 1 if set."))
        return value


# ---------------------------------------------------------------------------
# GamificationInsight Serializer
# ---------------------------------------------------------------------------

class GamificationInsightSerializer(serializers.ModelSerializer):
    engagement_rate = serializers.SerializerMethodField()
    points_per_active_user = serializers.SerializerMethodField()

    def get_engagement_rate(self, obj):
        try: return obj.engagement_rate()
        except Exception: return None

    def get_points_per_active_user(self, obj):
        try: return obj.points_per_active_user()
        except Exception: return None

    points_per_active_user = serializers.SerializerMethodField(read_only=True)
    engagement_rate = serializers.SerializerMethodField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    integration_sync_id = serializers.CharField(read_only=True)

    class Meta:
        model = GamificationInsight
        fields = [
            "id", "date", "active_users", "badges_awarded", "challenges_completed",
            "total_points_issued", "contest_participants", "streak_milestones",
            "points_per_active_user", "engagement_rate", "created_at", "updated_at",
            "checksum", "integration_sync_id"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "checksum", "integration_sync_id"]

    def get_points_per_active_user(self, obj) -> float:
        return obj.points_per_active_user

    def get_engagement_rate(self, obj) -> float:
        return obj.engagement_rate

    def validate_active_users(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Active users cannot be negative."))
        return value

    def validate_badges_awarded(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Badges awarded cannot be negative."))
        return value

    def validate_challenges_completed(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Challenges completed cannot be negative."))
        return value

    def validate_total_points_issued(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Total points issued cannot be negative."))
        return value

    def validate_contest_participants(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Contest participants cannot be negative."))
        return value

    def validate_streak_milestones(self, value) -> int:
        if value < 0:
            raise serializers.ValidationError(_("Streak milestones cannot be negative."))
        return value

    def validate_date(self, value) -> str:
        if value > timezone.now().date():
            raise serializers.ValidationError(_("Insight date cannot be in the future."))
        return value


# ---------------------------------------------------------------------------
# Badge Serializers
# ---------------------------------------------------------------------------

class BadgeSerializer(serializers.ModelSerializer):
    """Serializer for Badge model."""
    
    class Meta:
        model = Badge
        fields = [
            'id', 'name', 'description', 'icon', 'rarity', 'criteria_type',
            'criteria_value', 'points_bonus', 'is_active', 'sort_order',
            'metadata', 'checksum', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'checksum', 'created_at', 'updated_at']


class UserBadgeSerializer(serializers.ModelSerializer):
    """Serializer for UserBadge model."""
    badge = BadgeSerializer(read_only=True)
    badge_id = serializers.UUIDField(write_only=True)
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserBadge
        fields = [
            'id', 'user', 'badge', 'badge_id', 'earned_at', 'is_pinned',
            'metadata', 'checksum', 'created_at', 'updated_at',
            'progress_percentage'
        ]
        read_only_fields = [
            'id', 'user', 'earned_at', 'checksum', 'created_at', 'updated_at',
            'progress_percentage'
        ]
    
    def get_progress_percentage(self, obj: UserBadge) -> float:
        """Get progress percentage for display purposes."""
        return 100.0  # Badges are either earned or not earned


class BadgeStatisticsSerializer(serializers.Serializer):
    """Serializer for badge statistics."""
    total_badges = serializers.IntegerField()
    pinned_badges = serializers.IntegerField()
    by_rarity = serializers.DictField()
    by_criteria_type = serializers.DictField()
    recent_badges = UserBadgeSerializer(many=True)
    points_from_badges = serializers.IntegerField()


# ---------------------------------------------------------------------------
# Daily Challenge Serializers
# ---------------------------------------------------------------------------

class DailyChallengeSerializer(serializers.ModelSerializer):
    """Serializer for DailyChallenge model."""
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyChallenge
        fields = [
            'id', 'title', 'description', 'target_count', 'target_action',
            'bonus_points', 'date', 'is_active', 'metadata', 'checksum',
            'created_at', 'updated_at', 'progress_percentage'
        ]
        read_only_fields = ['id', 'checksum', 'created_at', 'updated_at', 'progress_percentage']
    
    def get_progress_percentage(self, obj: DailyChallenge) -> float:
        """Get progress percentage for display purposes."""
        return 0.0  # This will be overridden in UserDailyChallenge


class UserDailyChallengeSerializer(serializers.ModelSerializer):
    """Serializer for UserDailyChallenge model."""
    challenge = DailyChallengeSerializer(read_only=True)
    challenge_id = serializers.UUIDField(write_only=True)
    progress_percentage = serializers.SerializerMethodField()
    is_completed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = UserDailyChallenge
        fields = [
            'id', 'user', 'challenge', 'challenge_id', 'progress',
            'completed_at', 'metadata', 'checksum', 'created_at', 'updated_at',
            'progress_percentage', 'is_completed'
        ]
        read_only_fields = [
            'id', 'user', 'completed_at', 'checksum', 'created_at', 'updated_at',
            'progress_percentage', 'is_completed'
        ]
    
    def get_progress_percentage(self, obj: UserDailyChallenge) -> float:
        """Calculate progress percentage."""
        if not obj.challenge:
            return 0.0
        return obj.progress_percentage


class ChallengeProgressSerializer(serializers.Serializer):
    """Serializer for challenge progress updates."""
    increment_amount = serializers.IntegerField(min_value=1, default=1)
    action_metadata = serializers.DictField(required=False)


class ChallengeStatisticsSerializer(serializers.Serializer):
    """Serializer for challenge statistics."""
    period_days = serializers.IntegerField()
    total_challenges = serializers.IntegerField()
    completed_challenges = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    total_bonus_points = serializers.IntegerField()
    by_action_type = serializers.DictField()
    daily_completion = serializers.DictField()
    recent_challenges = UserDailyChallengeSerializer(many=True)


# ---------------------------------------------------------------------------
# Streak Serializers
# ---------------------------------------------------------------------------

class StreakSerializer(serializers.ModelSerializer):
    """Serializer for Streak model."""
    days_until_reset = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Streak
        fields = [
            'id', 'user', 'current_days', 'longest_days', 'last_activity_date',
            'is_active', 'metadata', 'checksum', 'created_at', 'updated_at',
            'days_until_reset', 'is_expired'
        ]
        read_only_fields = [
            'id', 'user', 'checksum', 'created_at', 'updated_at',
            'days_until_reset', 'is_expired'
        ]


class StreakRewardSerializer(serializers.ModelSerializer):
    """Serializer for StreakReward model."""
    badge = BadgeSerializer(read_only=True)
    badge_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = StreakReward
        fields = [
            'id', 'streak_days', 'points_bonus', 'badge', 'badge_id',
            'title', 'description', 'is_active', 'metadata', 'checksum',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'checksum', 'created_at', 'updated_at']


class StreakStatisticsSerializer(serializers.Serializer):
    """Serializer for streak statistics."""
    current_days = serializers.IntegerField()
    longest_days = serializers.IntegerField()
    is_active = serializers.BooleanField()
    last_activity_date = serializers.DateField()
    days_until_reset = serializers.IntegerField()
    is_expired = serializers.BooleanField()
    total_tracked_days = serializers.IntegerField()
    current_streak_percentage = serializers.FloatField()
    available_rewards = StreakRewardSerializer(many=True)
    metadata = serializers.DictField()


class StreakMilestoneSerializer(serializers.Serializer):
    """Serializer for streak milestones."""
    streak_days = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    points_bonus = serializers.IntegerField()
    badge_id = serializers.UUIDField(allow_null=True)
    badge_name = serializers.CharField(allow_null=True)
    received = serializers.BooleanField()
    achieved = serializers.BooleanField()
    progress_percentage = serializers.FloatField()


# ---------------------------------------------------------------------------
# Level Serializers
# ---------------------------------------------------------------------------

class LevelConfigSerializer(serializers.ModelSerializer):
    """Serializer for LevelConfig model."""
    badge = BadgeSerializer(read_only=True)
    badge_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = LevelConfig
        fields = [
            'id', 'level_number', 'points_required', 'title', 'description',
            'perks', 'badge', 'badge_id', 'points_multiplier', 'is_active',
            'metadata', 'checksum', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'checksum', 'created_at', 'updated_at']


class LevelProgressSerializer(serializers.Serializer):
    """Serializer for level progress information."""
    current_level = serializers.IntegerField()
    current_level_title = serializers.CharField()
    points_to_next_level = serializers.IntegerField()
    progress_percentage = serializers.FloatField()
    is_max_level = serializers.BooleanField()
    next_level_points = serializers.IntegerField(allow_null=True)
    next_level_title = serializers.CharField(allow_null=True)


class LevelStatisticsSerializer(serializers.Serializer):
    """Serializer for level statistics."""
    total_points = serializers.IntegerField()
    current_level = serializers.IntegerField()
    current_level_title = serializers.CharField()
    points_to_next_level = serializers.IntegerField()
    progress_percentage = serializers.FloatField()
    is_max_level = serializers.BooleanField()
    level_history = serializers.DictField()
    total_levels_achieved = serializers.IntegerField()
    points_multiplier = serializers.FloatField()
    level_perks = serializers.DictField()


class LevelRequirementsSerializer(serializers.Serializer):
    """Serializer for level requirements summary."""
    total_levels = serializers.IntegerField()
    min_points = serializers.IntegerField()
    max_points = serializers.IntegerField()
    levels = serializers.ListField(child=serializers.DictField())


# ---------------------------------------------------------------------------
# Summary Serializers
# ---------------------------------------------------------------------------

class GamificationSummarySerializer(serializers.Serializer):
    """Serializer for comprehensive gamification summary."""
    user_id = serializers.UUIDField()
    badges = BadgeStatisticsSerializer()
    streak = StreakStatisticsSerializer()
    level = LevelStatisticsSerializer()
    recent_challenges = serializers.ListField(child=serializers.DictField())


# ---------------------------------------------------------------------------
# Input Serializers
# ---------------------------------------------------------------------------

class BadgeAwardSerializer(serializers.Serializer):
    """Serializer for awarding a badge to a user."""
    badge_id = serializers.UUIDField()
    metadata = serializers.DictField(required=False)


class ChallengeStartSerializer(serializers.Serializer):
    """Serializer for starting a daily challenge."""
    challenge_id = serializers.UUIDField()


class StreakUpdateSerializer(serializers.Serializer):
    """Serializer for updating user streak."""
    activity_date = serializers.DateField(required=False)
    metadata = serializers.DictField(required=False)


class LevelConfigCreateSerializer(serializers.Serializer):
    """Serializer for creating level configurations."""
    level_number = serializers.IntegerField(min_value=1, max_value=1000)
    points_required = serializers.IntegerField(min_value=0)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    perks = serializers.DictField(required=False)
    points_multiplier = serializers.FloatField(min_value=0.01, max_value=5.0, default=1.0)
    badge_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False)


class DailyChallengeCreateSerializer(serializers.Serializer):
    """Serializer for creating daily challenges."""
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    target_action = serializers.ChoiceField(choices=ChallengeAction.choices)
    target_count = serializers.IntegerField(min_value=1, max_value=1000)
    bonus_points = serializers.IntegerField(min_value=0, max_value=10000)
    challenge_date = serializers.DateField(required=False)
    metadata = serializers.DictField(required=False)


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_url(self, value):
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError('URL must start with http:// or https://')
        return value


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
