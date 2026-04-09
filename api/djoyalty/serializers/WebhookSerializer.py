# api/djoyalty/serializers/WebhookSerializer.py
"""
Webhook payload serializer — inbound ও outbound উভয়ের জন্য।
"""
from rest_framework import serializers


class WebhookPayloadSerializer(serializers.Serializer):
    """Standard outbound webhook payload format।"""
    event = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    tenant_id = serializers.IntegerField(allow_null=True, read_only=True)
    customer_code = serializers.CharField(allow_null=True, read_only=True)
    data = serializers.DictField(read_only=True)


class InboundWebhookSerializer(serializers.Serializer):
    """Inbound webhook from partner merchant।"""
    event = serializers.CharField()
    customer_code = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reference = serializers.CharField(max_length=128, required=False, allow_blank=True)
    metadata = serializers.DictField(required=False, default=dict)

    def validate_event(self, value):
        from djoyalty.webhooks.webhook_payloads import WEBHOOK_EVENTS
        if value not in WEBHOOK_EVENTS:
            raise serializers.ValidationError(f'Unknown event type: {value}')
        return value


class WebhookEndpointSerializer(serializers.Serializer):
    """Webhook endpoint registration।"""
    url = serializers.URLField()
    events = serializers.ListField(child=serializers.CharField(), min_length=1)
    secret = serializers.CharField(max_length=128, required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)

    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value

    def validate_events(self, value):
        from djoyalty.webhooks.webhook_payloads import WEBHOOK_EVENTS
        invalid = [e for e in value if e not in WEBHOOK_EVENTS]
        if invalid:
            raise serializers.ValidationError(f'Invalid event types: {", ".join(invalid)}')
        return value
