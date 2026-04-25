"""Webhook Endpoint Serializer

This serializer handles webhook endpoint CRUD operations
including secret rotation, testing, and status management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..choices import WebhookStatus, HttpMethod

User = get_user_model()


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Serializer for webhook endpoint CRUD operations."""
    
    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'url', 'secret', 'status', 'http_method',
            'timeout_seconds', 'max_retries', 'ip_whitelist',
            'rate_limit_per_min', 'payload_template', 'headers',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'status': {'read_only': True},
        }
    
    def validate_url(self, value):
        """Validate webhook URL format."""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError(_('URL must start with http:// or https://'))
        return value
    
    def validate_ip_whitelist(self, value):
        """Validate IP whitelist format."""
        if not isinstance(value, list):
            raise serializers.ValidationError(_('IP whitelist must be a list'))
        
        for ip in value:
            if not isinstance(ip, str):
                raise serializers.ValidationError(_('IP addresses must be strings'))
        
        return value


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for webhook subscription CRUD operations."""
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id', 'endpoint', 'event_type', 'filter_config',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_filter_config(self, value):
        """Validate filter configuration JSON."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_('Filter config must be a JSON object'))
        
        return value


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """Serializer for webhook delivery log operations."""
    
    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id', 'endpoint', 'event_type', 'payload', 'status',
            'response_code', 'response_body', 'duration_ms',
            'attempt_number', 'next_retry_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def to_representation(self, instance):
        """Customize delivery log representation."""
        data = super().to_representation(instance)
        
        # Truncate long response bodies
        if 'response_body' in data and data['response_body']:
            response_body = data['response_body']
            if len(response_body) > 500:
                data['response_body'] = response_body[:500] + '...'
                data['response_body_truncated'] = True
        
        return data


class WebhookEmitSerializer(serializers.Serializer):
    """Serializer for webhook emission operations."""
    
    event_type = serializers.CharField(
        max_length=100,
        help_text=_('Event type to emit')
    )
    payload = serializers.JSONField(
        help_text=_('Payload data to emit')
    )
    endpoint_id = serializers.IntegerField(
        help_text=_('Specific endpoint ID (optional)')
    )
    async_emit = serializers.BooleanField(
        default=False,
        help_text=_('Emit asynchronously (queue for background processing)')
    )


class EventTypeListAPIViewSerializer(serializers.Serializer):
    """Serializer for event type list API view."""
    
    def to_representation(self, instance):
        """Format event type for API response."""
        from ..constants import EventType
        
        return {
            'event_type': instance,
            'display_name': dict(EventType.all_choices()).get(instance, instance),
        }


class WebhookTestSerializer(serializers.Serializer):
    """Serializer for webhook test operations."""
    
    url = serializers.URLField(
        help_text=_('Webhook URL to test')
    )
    event_type = serializers.CharField(
        max_length=100,
        help_text=_('Event type for test payload')
    )
    payload = serializers.JSONField(
        help_text=_('Test payload data')
    )
    headers = serializers.JSONField(
        required=False,
        help_text=_('Custom headers for test request')
    )
    timeout = serializers.IntegerField(
        default=30,
        help_text=_('Request timeout in seconds')
    )
