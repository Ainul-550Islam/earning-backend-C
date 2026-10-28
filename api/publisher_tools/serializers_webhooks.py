# publisher_tools/serializers_webhooks.py
# ============================================================
# NEW FILE — Serializers for PublisherWebhook + WebhookDeliveryLog
# ============================================================
from rest_framework import serializers
from .models import PublisherWebhook, WebhookDeliveryLog


class PublisherWebhookSerializer(serializers.ModelSerializer):
    """Read serializer — full webhook detail."""
    success_rate   = serializers.ReadOnlyField()
    publisher_id   = serializers.CharField(source='publisher.publisher_id', read_only=True)

    class Meta:
        model  = PublisherWebhook
        fields = [
            'id', 'publisher_id', 'name', 'endpoint_url',
            'subscribed_events', 'subscribe_all',
            'status', 'is_active',
            'timeout_seconds', 'max_retries', 'retry_backoff', 'custom_headers',
            'total_deliveries', 'successful_deliveries', 'failed_deliveries',
            'consecutive_failures', 'success_rate',
            'last_delivery_at', 'last_success_at', 'last_failure_at', 'last_failure_reason',
            'description', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'publisher_id', 'success_rate',
            'total_deliveries', 'successful_deliveries', 'failed_deliveries',
            'consecutive_failures', 'last_delivery_at', 'last_success_at',
            'last_failure_at', 'last_failure_reason',
            'created_at', 'updated_at',
        ]


class PublisherWebhookCreateSerializer(serializers.ModelSerializer):
    """Write serializer — create/update webhook."""

    VALID_EVENTS = [choice[0] for choice in PublisherWebhook.EVENT_CHOICES]

    class Meta:
        model  = PublisherWebhook
        fields = [
            'name', 'endpoint_url', 'subscribed_events', 'subscribe_all',
            'timeout_seconds', 'max_retries', 'retry_backoff', 'custom_headers',
            'description',
        ]

    def validate_endpoint_url(self, value):
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError('Endpoint URL must start with http:// or https://')
        return value

    def validate_subscribed_events(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('subscribed_events must be a list.')
        invalid = [e for e in value if e not in self.VALID_EVENTS]
        if invalid:
            raise serializers.ValidationError(
                f'Invalid event types: {invalid}. '
                f'Valid events: {self.VALID_EVENTS}'
            )
        return value

    def validate(self, attrs):
        subscribe_all      = attrs.get('subscribe_all', False)
        subscribed_events  = attrs.get('subscribed_events', [])
        if not subscribe_all and not subscribed_events:
            raise serializers.ValidationError(
                'Either set subscribe_all=true or provide at least one subscribed_events entry.'
            )
        return attrs


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for delivery log entries."""

    class Meta:
        model  = WebhookDeliveryLog
        fields = [
            'id', 'event_type', 'event_id', 'status', 'attempt',
            'response_code', 'response_body', 'error_message',
            'delivery_time_ms', 'delivered_at', 'created_at',
        ]
        read_only_fields = fields


class WebhookTestSerializer(serializers.Serializer):
    """Payload for POST /webhooks/{id}/test/"""
    VALID_EVENTS = [choice[0] for choice in PublisherWebhook.EVENT_CHOICES] + ['test.ping']

    event_type = serializers.ChoiceField(
        choices=[(e, e) for e in VALID_EVENTS],
        default='test.ping',
        required=False,
    )
