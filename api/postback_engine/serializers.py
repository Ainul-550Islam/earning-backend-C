"""
serializers.py (schemas.py) – DRF Serializers for Postback Engine.
"""
from rest_framework import serializers
from .models import (
    AdNetworkConfig, NetworkAdapterMapping, OfferPostback,
    ClickLog, PostbackRawLog, Conversion, Impression,
    FraudAttemptLog, IPBlacklist, ConversionDeduplication,
    PostbackQueue, RetryLog, NetworkPerformance, HourlyStat,
)


# ── AdNetworkConfig ───────────────────────────────────────────────────────────

class AdNetworkConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdNetworkConfig
        fields = [
            "id", "name", "network_key", "network_type", "status",
            "signature_algorithm", "require_nonce",
            "ip_whitelist", "trust_x_forwarded_for",
            "field_mapping", "required_fields",
            "reward_rules", "default_reward_points", "default_reward_usd",
            "dedup_window", "attribution_model", "conversion_window_hours",
            "rate_limit_per_minute", "contact_email", "is_test_mode",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "secret_key": {"write_only": True},
            "api_key":    {"write_only": True},
        }


class AdNetworkConfigListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    class Meta:
        model = AdNetworkConfig
        fields = ["id", "name", "network_key", "network_type", "status", "is_test_mode"]


# ── ClickLog ──────────────────────────────────────────────────────────────────

class ClickLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    network_name = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = ClickLog
        fields = [
            "id", "click_id", "username", "network_name",
            "offer_id", "offer_name", "status",
            "ip_address", "device_type", "country",
            "sub_id", "converted", "converted_at",
            "is_fraud", "fraud_score", "fraud_type",
            "clicked_at", "expires_at",
        ]
        read_only_fields = ["id", "click_id", "clicked_at"]


# ── PostbackRawLog ────────────────────────────────────────────────────────────

class PostbackRawLogSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source="network.name", read_only=True)
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    username = serializers.CharField(source="resolved_user.username", read_only=True)

    class Meta:
        model = PostbackRawLog
        fields = [
            "id", "network_name", "network_key", "status",
            "lead_id", "click_id", "offer_id", "transaction_id",
            "payout", "currency",
            "username", "source_ip",
            "signature_verified", "ip_whitelisted",
            "rejection_reason", "rejection_detail",
            "points_awarded", "usd_awarded",
            "received_at", "processed_at",
            "retry_count", "next_retry_at",
        ]
        read_only_fields = ["id", "received_at"]


class PostbackRawLogDetailSerializer(PostbackRawLogSerializer):
    """Full detail including raw payload."""
    class Meta(PostbackRawLogSerializer.Meta):
        fields = PostbackRawLogSerializer.Meta.fields + [
            "raw_payload", "http_method", "query_string",
            "request_headers", "processing_error",
        ]


# ── Conversion ────────────────────────────────────────────────────────────────

class ConversionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    network_name = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = Conversion
        fields = [
            "id", "username", "network_name",
            "lead_id", "click_id", "offer_id", "transaction_id",
            "status", "network_payout", "actual_payout", "currency",
            "points_awarded", "attribution_model",
            "time_to_convert_seconds", "source_ip", "country",
            "wallet_credited", "wallet_credited_at",
            "is_reversed", "reversed_at",
            "converted_at", "approved_at",
        ]
        read_only_fields = ["id", "converted_at", "approved_at"]


# ── Impression ────────────────────────────────────────────────────────────────

class ImpressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Impression
        fields = [
            "id", "offer_id", "placement", "status",
            "ip_address", "device_type", "country",
            "is_viewable", "view_time_seconds", "impressed_at",
        ]
        read_only_fields = ["id", "impressed_at"]


# ── FraudAttemptLog ───────────────────────────────────────────────────────────

class FraudAttemptLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudAttemptLog
        fields = [
            "id", "fraud_type", "fraud_score",
            "is_auto_blocked", "is_reviewed", "review_action",
            "source_ip", "device_fingerprint", "country",
            "details", "signals", "detected_at",
        ]
        read_only_fields = ["id", "detected_at"]


# ── IPBlacklist ───────────────────────────────────────────────────────────────

class IPBlacklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPBlacklist
        fields = [
            "id", "blacklist_type", "value", "reason",
            "is_active", "added_by_system", "notes",
            "expires_at", "hit_count", "last_hit_at",
            "created_at",
        ]
        read_only_fields = ["id", "hit_count", "last_hit_at", "created_at"]


# ── Analytics ─────────────────────────────────────────────────────────────────

class NetworkPerformanceSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = NetworkPerformance
        fields = [
            "id", "network_name", "date",
            "total_clicks", "unique_clicks", "total_impressions",
            "total_conversions", "approved_conversions",
            "rejected_conversions", "duplicate_conversions",
            "total_payout_usd", "total_points_awarded",
            "fraud_clicks", "fraud_conversions",
            "conversion_rate", "fraud_rate", "avg_payout_usd",
            "computed_at",
        ]


class HourlyStatSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = HourlyStat
        fields = [
            "id", "network_name", "date", "hour",
            "clicks", "conversions", "impressions",
            "rejected", "fraud",
            "payout_usd", "points_awarded",
            "conversion_rate", "fraud_rate",
            "updated_at",
        ]


class NetworkStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    revenue_usd = serializers.FloatField()
    fraud_rate = serializers.FloatField()


# ── Queue ─────────────────────────────────────────────────────────────────────

class PostbackQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostbackQueue
        fields = [
            "id", "priority", "status",
            "process_after", "enqueued_at",
            "processing_started_at", "processing_finished_at",
            "error_message",
        ]


class RetryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetryLog
        fields = [
            "id", "retry_type", "object_id", "attempt_number",
            "attempted_at", "succeeded", "error_message", "next_retry_at",
        ]
