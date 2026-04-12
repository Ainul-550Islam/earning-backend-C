# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
serializers.py: DRF serializer definitions.

Serializers:
    WebhookEndpointSerializer      — Create/update endpoint registrations.
    WebhookEndpointDetailSerializer— Full endpoint with subscription list.
    WebhookSubscriptionSerializer  — Subscribe/unsubscribe event types.
    WebhookDeliveryLogSerializer   — Read-only delivery attempt log.
    WebhookEmitSerializer          — Validate inbound emit requests.
    SecretRotateSerializer         — Confirm secret key rotation.
    WebhookTestSerializer          — Trigger a test ping.
"""

import logging

from rest_framework import serializers

from .constants import EndpointStatus, EventType, HttpMethod
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """
    Ainul Enterprise Engine — Webhook Subscription serializer.
    Supports create (subscribe) and partial update (toggle active).
    """

    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model  = WebhookSubscription
        fields = [
            "id",
            "event_type",
            "event_type_display",
            "is_active",
            "filters",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_event_type(self, value: str) -> str:
        valid = [choice[0] for choice in EventType.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f"'{value}' is not a valid event type. "
                f"Valid types: {', '.join(valid)}"
            )
        return value


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointSerializer(serializers.ModelSerializer):
    """
    Ainul Enterprise Engine — Webhook Endpoint registration serializer.
    secret_key is write-never; shown only in the detail view on creation.
    """

    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model  = WebhookEndpoint
        fields = [
            "id",
            "label",
            "target_url",
            "http_method",
            "status",
            "description",
            "custom_headers",
            "max_retries",
            "verify_ssl",
            "version",
            "owner_email",
            "total_deliveries",
            "success_deliveries",
            "failed_deliveries",
            "success_rate",
            "last_triggered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "secret_key",
            "owner_email",
            "total_deliveries",
            "success_deliveries",
            "failed_deliveries",
            "last_triggered_at",
            "created_at",
            "updated_at",
        ]

    def validate_target_url(self, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError(
                "Target URL must begin with http:// or https://"
            )
        return value

    def validate_max_retries(self, value: int) -> int:
        if value < 0 or value > 10:
            raise serializers.ValidationError(
                "max_retries must be between 0 and 10."
            )
        return value


class WebhookEndpointDetailSerializer(WebhookEndpointSerializer):
    """
    Ainul Enterprise Engine — Full endpoint detail including subscriptions.
    secret_key is included once (on creation or after rotation).
    """

    subscriptions = WebhookSubscriptionSerializer(many=True, read_only=True)
    secret_key    = serializers.CharField(read_only=True)

    class Meta(WebhookEndpointSerializer.Meta):
        fields = WebhookEndpointSerializer.Meta.fields + [
            "secret_key",
            "subscriptions",
        ]


class SecretRotateSerializer(serializers.Serializer):
    """
    Ainul Enterprise Engine — Secret rotation confirmation serializer.
    Requires explicit confirmation to prevent accidental rotations.
    """

    confirm = serializers.BooleanField(
        required=True,
        help_text="Must be true to confirm secret rotation.",
    )

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Set confirm=true to proceed with secret rotation."
            )
        return value


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY LOG
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """
    Ainul Enterprise Engine — Delivery log read-only serializer.
    Used for dashboard, audit, and retry views.
    """

    event_type_display  = serializers.CharField(
        source="get_event_type_display", read_only=True
    )
    status_display      = serializers.CharField(
        source="get_status_display", read_only=True
    )
    endpoint_label      = serializers.CharField(
        source="endpoint.label", read_only=True
    )
    endpoint_url        = serializers.URLField(
        source="endpoint.target_url", read_only=True
    )
    was_successful      = serializers.BooleanField(read_only=True)
    is_retryable        = serializers.BooleanField(read_only=True)

    class Meta:
        model  = WebhookDeliveryLog
        fields = [
            "id",
            "delivery_id",
            "endpoint_label",
            "endpoint_url",
            "event_type",
            "event_type_display",
            "status",
            "status_display",
            "http_status_code",
            "response_time_ms",
            "attempt_number",
            "max_attempts",
            "signature",
            "error_message",
            "response_body",
            "payload",
            "request_headers",
            "dispatched_at",
            "completed_at",
            "next_retry_at",
            "was_successful",
            "is_retryable",
            "created_at",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
#  EMIT / TEST
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEmitSerializer(serializers.Serializer):
    """
    Ainul Enterprise Engine — Inbound emit request validator.
    Used by the internal emit API endpoint.
    """

    event_type = serializers.ChoiceField(
        choices=EventType.choices,
        required=True,
    )
    payload = serializers.DictField(
        required=True,
        allow_empty=False,
        help_text="Arbitrary event payload. Will be JSON-serialised.",
    )
    tenant_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )
    async_dispatch = serializers.BooleanField(
        default=True,
        required=False,
        help_text="If true, dispatches via Celery task (non-blocking).",
    )


class WebhookTestSerializer(serializers.Serializer):
    """
    Ainul Enterprise Engine — Test ping payload validator.
    Sends a webhook.test event to a specific endpoint.
    """

    message = serializers.CharField(
        max_length=256,
        default="Ainul Enterprise Engine — Webhook Test Ping",
        required=False,
    )
