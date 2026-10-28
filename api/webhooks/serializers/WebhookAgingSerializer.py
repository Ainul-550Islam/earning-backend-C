# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Aging Serializers

Serializers for the aging API:
    WebhookAgingPolicySerializer       — Create/update retention policies
    WebhookEndpointAgingSerializer     — Read endpoint aging records
    WebhookDeliveryAgingSerializer     — Read delivery log aging records
    WebhookAgingEventSerializer        — Read audit trail events
    WebhookAgingSummarySerializer      — Validate summary query params
"""

from rest_framework import serializers

from ..models.aging import (
    AgeTier,
    AgingEventType,
    WebhookAgingEvent,
    WebhookAgingPolicy,
    WebhookDeliveryAging,
    WebhookEndpointAging,
)


class WebhookAgingPolicySerializer(serializers.ModelSerializer):
    """Ainul Enterprise Engine — Read/write aging retention policy."""

    owner_email = serializers.EmailField(source="owner.email", read_only=True, allow_null=True)

    class Meta:
        model  = WebhookAgingPolicy
        fields = [
            "id",
            "owner_email",
            "log_warm_after_days",
            "log_cooling_after_days",
            "log_stale_after_days",
            "log_archive_after_days",
            "log_purge_after_days",
            "endpoint_warm_after_days",
            "endpoint_cooling_after_days",
            "endpoint_stale_after_days",
            "endpoint_dormant_after_days",
            "notify_on_stale",
            "notify_on_dormant",
            "notify_on_archive",
            "notify_before_purge",
            "purge_warning_days",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_email", "created_at", "updated_at"]

    def validate(self, data):
        thresholds = [
            ("log_warm_after_days",    data.get("log_warm_after_days",    self.instance.log_warm_after_days    if self.instance else 7)),
            ("log_cooling_after_days", data.get("log_cooling_after_days", self.instance.log_cooling_after_days if self.instance else 30)),
            ("log_stale_after_days",   data.get("log_stale_after_days",   self.instance.log_stale_after_days   if self.instance else 90)),
            ("log_archive_after_days", data.get("log_archive_after_days", self.instance.log_archive_after_days if self.instance else 180)),
            ("log_purge_after_days",   data.get("log_purge_after_days",   self.instance.log_purge_after_days   if self.instance else 365)),
        ]
        for i in range(1, len(thresholds)):
            prev_name, prev_val = thresholds[i - 1]
            curr_name, curr_val = thresholds[i]
            if curr_val <= prev_val:
                raise serializers.ValidationError(
                    {curr_name: f"Must be greater than {prev_name} ({prev_val} days)."}
                )
        return data


class WebhookEndpointAgingSerializer(serializers.ModelSerializer):
    """Ainul Enterprise Engine — Endpoint aging state (read-only)."""

    endpoint_label = serializers.CharField(source="endpoint.label",      read_only=True)
    endpoint_url   = serializers.URLField(source="endpoint.target_url",  read_only=True)
    endpoint_status = serializers.CharField(source="endpoint.status",    read_only=True)
    is_stale        = serializers.BooleanField(read_only=True)
    needs_purge_warning = serializers.BooleanField(read_only=True)

    class Meta:
        model  = WebhookEndpointAging
        fields = [
            "id",
            "endpoint",
            "endpoint_label",
            "endpoint_url",
            "endpoint_status",
            "tier",
            "previous_tier",
            "days_inactive",
            "total_deliveries",
            "failed_deliveries",
            "last_delivery_at",
            "is_stale",
            "needs_purge_warning",
            "stale_notified_at",
            "dormant_notified_at",
            "purge_warned_at",
            "archive_after",
            "purge_after",
            "archived_at",
            "purged_at",
            "is_archived",
            "is_purged",
            "last_evaluated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WebhookDeliveryAgingSerializer(serializers.ModelSerializer):
    """Ainul Enterprise Engine — Delivery log aging record (read-only)."""

    delivery_event_type = serializers.CharField(
        source="delivery_log.event_type", read_only=True
    )
    delivery_status = serializers.CharField(
        source="delivery_log.status", read_only=True
    )

    class Meta:
        model  = WebhookDeliveryAging
        fields = [
            "id",
            "delivery_log",
            "delivery_event_type",
            "delivery_status",
            "bucket",
            "age_days",
            "archive_after",
            "purge_after",
            "archived_at",
            "purged_at",
            "is_archived",
            "is_purged",
            "last_evaluated_at",
            "created_at",
        ]
        read_only_fields = fields


class WebhookAgingEventSerializer(serializers.ModelSerializer):
    """Ainul Enterprise Engine — Aging audit event (read-only)."""

    class Meta:
        model  = WebhookAgingEvent
        fields = [
            "id",
            "event_type",
            "endpoint_aging",
            "delivery_aging",
            "from_tier",
            "to_tier",
            "detail",
            "triggered_by",
            "occurred_at",
        ]
        read_only_fields = fields


class AgingPurgeConfirmSerializer(serializers.Serializer):
    """Ainul Enterprise Engine — Confirm a destructive purge action."""
    confirm  = serializers.BooleanField(required=True)
    dry_run  = serializers.BooleanField(default=True)

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Set confirm=true to proceed.")
        return value
