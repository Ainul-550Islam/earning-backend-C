# engagement/serializers/analytics_serializer.py
from rest_framework import serializers
from ..models.analytics import EngagementEvent, RetentionCohort, DailyPlatformMetric
from ..models.webhook import WebhookEndpoint, WebhookDelivery


class EngagementEventSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model  = EngagementEvent
        fields = [
            "id", "username", "event_type", "coins_delta", "xp_delta",
            "value", "properties", "session_id",
            "device_type", "platform", "app_version", "event_time",
        ]
        read_only_fields = fields


class RetentionCohortSerializer(serializers.ModelSerializer):
    retention_rate = serializers.FloatField(read_only=True)

    class Meta:
        model  = RetentionCohort
        fields = [
            "id", "cohort_date", "period_type", "period_number",
            "total_users", "retained", "retention_rate",
        ]
        read_only_fields = fields


class DailyPlatformMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DailyPlatformMetric
        fields = [
            "date", "dau", "checkins", "spins", "quests_completed",
            "achievements_unlocked", "shop_purchases",
            "coins_distributed", "xp_distributed",
            "new_users", "chest_openings", "guild_actions", "bp_premium_purchases",
        ]
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WebhookEndpoint
        fields = [
            "id", "name", "url", "events", "is_active",
            "timeout_seconds", "retry_count",
            "success_count", "failure_count", "last_triggered",
        ]
        read_only_fields = ["id", "success_count", "failure_count", "last_triggered"]
        extra_kwargs = {"secret": {"write_only": True}}


class WebhookDeliverySerializer(serializers.ModelSerializer):
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)

    class Meta:
        model  = WebhookDelivery
        fields = [
            "id", "endpoint_name", "event_type", "status",
            "attempt_count", "response_code", "duration_ms",
            "delivered_at", "next_retry_at", "created_at",
        ]
        read_only_fields = fields
