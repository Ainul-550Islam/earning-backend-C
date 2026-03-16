"""serializers.py – DRF serializers for the postback module."""
from rest_framework import serializers
from .models import DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog
from .choices import ValidatorStatus
from .validators import validate_ip_whitelist, validate_field_mapping, validate_reward_rules


class NetworkPostbackConfigListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    network_type_display = serializers.CharField(source="get_network_type_display", read_only=True)

    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "id", "name", "network_key", "network_type", "network_type_display",
            "status", "status_display", "dedup_window",
            "ip_whitelist", "reward_rules", "rate_limit_per_minute",
            "signature_algorithm", "trust_forwarded_for", "require_nonce",
            "default_reward_points", "contact_email", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NetworkPostbackConfigDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "id", "name", "network_key", "network_type", "status",
            "signature_algorithm", "ip_whitelist",
            "trust_forwarded_for", "require_nonce",
            "field_mapping", "required_fields", "dedup_window",
            "reward_rules", "default_reward_points",
            "rate_limit_per_minute", "contact_email", "notes",
            "metadata", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "secret_key": {"write_only": True},
        }


class NetworkPostbackConfigWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "name", "network_key", "network_type", "status",
            "secret_key", "signature_algorithm",
            "ip_whitelist", "trust_forwarded_for", "require_nonce",
            "field_mapping", "required_fields", "dedup_window",
            "reward_rules", "default_reward_points",
            "rate_limit_per_minute", "contact_email", "notes", "metadata",
        ]
        extra_kwargs = {
            "secret_key": {"write_only": True, "required": True, "allow_blank": True},
        }

    def validate_ip_whitelist(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_ip_whitelist(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate_field_mapping(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_field_mapping(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate_reward_rules(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_reward_rules(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value


class PostbackLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    resolved_user_email = serializers.SerializerMethodField()

    class Meta:
        model = PostbackLog
        fields = [
            "id", "network_key", "status", "status_display",
            "lead_id", "offer_id", "transaction_id", "payout", "currency",
            "source_ip", "signature_verified", "ip_whitelisted",
            "rejection_reason", "rejection_detail",
            "points_awarded", "inventory_id",
            "retry_count", "processing_error",
            "received_at", "processed_at",
            "resolved_user_email",
        ]
        read_only_fields = fields

    def get_resolved_user_email(self, obj) -> str:
        return obj.resolved_user.email if obj.resolved_user else ""


class PostbackLogDetailSerializer(PostbackLogSerializer):
    class Meta(PostbackLogSerializer.Meta):
        fields = PostbackLogSerializer.Meta.fields + ["raw_payload", "request_headers", "method"]


class LeadValidatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadValidator
        fields = [
            "id", "name", "validator_type", "params",
            "is_blocking", "sort_order", "is_active", "failure_reason",
        ]


class DuplicateLeadCheckSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)

    class Meta:
        model = DuplicateLeadCheck
        fields = ["id", "network_key", "lead_id", "first_seen_at"]
        read_only_fields = fields
