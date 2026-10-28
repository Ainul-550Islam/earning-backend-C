# api/djoyalty/serializers/WebhookSerializer.py
from rest_framework import serializers


class WebhookEndpointSerializer(serializers.Serializer):
    """Webhook endpoint registration।"""
    url = serializers.URLField()
    events = serializers.ListField(child=serializers.CharField(), min_length=1)
    secret = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)

    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value

    def validate_events(self, value):
        from ..webhooks.webhook_payloads import WEBHOOK_EVENTS
        invalid = [e for e in value if e not in WEBHOOK_EVENTS]
        if invalid:
            raise serializers.ValidationError(f'Unknown event types: {invalid}')
        return value


class WebhookPayloadSerializer(serializers.Serializer):
    """Standard outbound webhook payload।"""
    event = serializers.CharField(read_only=True)
    timestamp = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    customer_code = serializers.CharField(read_only=True, allow_null=True)
    tenant_id = serializers.IntegerField(read_only=True, allow_null=True)
    data = serializers.DictField(read_only=True)


class WebhookDeliveryLogSerializer(serializers.Serializer):
    """Webhook delivery attempt log।"""
    url = serializers.URLField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    attempt = serializers.IntegerField(read_only=True)
    response_code = serializers.IntegerField(read_only=True, allow_null=True)
    error = serializers.CharField(read_only=True, allow_null=True)
    timestamp = serializers.CharField(read_only=True)
