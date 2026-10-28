"""Admin Webhook Serializer

This module contains the serializer for admin webhook operations.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..choices import WebhookStatus, DeliveryStatus

User = get_user_model()


class AdminWebhookEndpointSerializer(serializers.ModelSerializer):
    """Admin serializer for WebhookEndpoint model."""
    
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    subscription_count = serializers.SerializerMethodField()
    delivery_count = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookEndpoint
        # FIX: this Meta.fields list referenced url, headers,
        # timeout_seconds, rate_limit_per_min, ip_whitelist - none of
        # which exist on WebhookEndpoint (real names are target_url and
        # custom_headers; the other three don't correspond to any field
        # on this model at all - rate limiting lives on the separate
        # WebhookRateLimit model, and there's no per-endpoint request
        # timeout or IP allowlist field anywhere in this app). Confirmed
        # via direct instantiation: AdminWebhookEndpointSerializer()
        # raised ImproperlyConfigured immediately, so every real
        # list/retrieve/create through AdminWebhookViewSet ("all admin
        # CRUD paths use this serializer") would have crashed - nothing
        # in the test suite happens to exercise a successful response
        # from this viewset, so it went uncaught. Corrected the two
        # renames and dropped the three fields with no real backing
        # rather than inventing new model fields to match them.
        fields = [
            'id',
            'label',
            'target_url',
            'description',
            'owner',
            'owner_username',
            'status',
            'http_method',
            'max_retries',
            'verify_ssl',
            'secret_key',
            'custom_headers',
            'payload_template',
            'version',
            'subscription_count',
            'delivery_count',
            'success_rate',
            'health_status',
            'last_triggered_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_triggered_at']

    # Note: no validate_target_url() here - confirmed via a real HTTP
    # test that target_url already carries validate_webhook_url (SSRF
    # protection) and URLValidator(schemes=["https","http"]) at the
    # model-field level (models/core.py), which DRF's ModelSerializer
    # auto-applies to this field with zero extra code. Adding a weaker
    # duplicate check here would just be redundant dead weight.

    def validate_max_retries(self, value):
        # max_retries has no such field-level validator (plain
        # PositiveSmallIntegerField) - only WebhookEndpoint.clean()'s
        # upper bound, which DRF does not auto-apply. Mirroring that
        # already-decided rule here since this admin path had nothing.
        if value is not None and value > 10:
            raise serializers.ValidationError("max_retries must be between 0 and 10.")
        return value

    
    def get_subscription_count(self, obj):
        """Get subscription count."""
        return obj.subscriptions.filter(is_active=True).count()
    
    def get_delivery_count(self, obj):
        """Get delivery count."""
        return obj.delivery_logs.count()
    
    def get_success_rate(self, obj):
        """Calculate success rate."""
        deliveries = obj.delivery_logs.all()
        if not deliveries.exists():
            return 0.0
        
        success_count = deliveries.filter(status='success').count()
        return round((success_count / deliveries.count()) * 100, 2)
    
    def get_health_status(self, obj):
        """Get health status."""
        from django.utils import timezone
        from datetime import timedelta
        
        recent_health = obj.health_logs.filter(
            checked_at__gte=timezone.now() - timedelta(hours=24)
        ).first()
        
        if recent_health:
            return {
                'is_healthy': recent_health.is_healthy,
                'last_checked': recent_health.checked_at,
                'response_time_ms': recent_health.response_time_ms
            }
        
        return {
            'is_healthy': None,
            'last_checked': None,
            'response_time_ms': None
        }


class AdminWebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Admin serializer for WebhookSubscription model."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.target_url', read_only=True)
    endpoint_status = serializers.CharField(source='endpoint.status', read_only=True)
    delivery_count = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id',
            'endpoint',
            'endpoint_label',
            'endpoint_url',
            'endpoint_status',
            'event_type',
            'is_active',
            'filter_config',
            'delivery_count',
            'success_rate',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_delivery_count(self, obj):
        """Get delivery count."""
        from ..models import WebhookDeliveryLog
        return WebhookDeliveryLog.objects.filter(
            endpoint=obj.endpoint,
            event_type=obj.event_type
        ).count()
    
    def get_success_rate(self, obj):
        """Calculate success rate."""
        from ..models import WebhookDeliveryLog
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=obj.endpoint,
            event_type=obj.event_type
        )
        
        if not deliveries.exists():
            return 0.0
        
        success_count = deliveries.filter(status='success').count()
        return round((success_count / deliveries.count()) * 100, 2)


class AdminWebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """Admin serializer for WebhookDeliveryLog model."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.target_url', read_only=True)
    endpoint_status = serializers.CharField(source='endpoint.status', read_only=True)
    payload_preview = serializers.SerializerMethodField()
    headers_preview = serializers.SerializerMethodField()
    response_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id',
            'endpoint',
            'endpoint_label',
            'endpoint_url',
            'endpoint_status',
            'event_type',
            'payload',
            'payload_preview',
            'request_headers',
            'headers_preview',
            'signature',
            'http_status_code',
            'response_body',
            'response_preview',
            'response_time_ms',
            'error_message',
            'status',
            'attempt_number',
            'max_attempts',
            'next_retry_at',
            'dispatched_at',
            'completed_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'dispatched_at',
            'completed_at', 'next_retry_at', 'signature'
        ]
    
    def get_payload_preview(self, obj):
        """Get payload preview."""
        if not obj.payload:
            return None
        
        import json
        payload_str = json.dumps(obj.payload, indent=2)
        if len(payload_str) > 200:
            return payload_str[:200] + "..."
        return payload_str
    
    def get_headers_preview(self, obj):
        """Get headers preview."""
        if not obj.request_headers:
            return None
        
        import json
        headers_str = json.dumps(obj.request_headers, indent=2)
        if len(headers_str) > 200:
            return headers_str[:200] + "..."
        return headers_str
    
    def get_response_preview(self, obj):
        """Get response preview."""
        if not obj.response_body:
            return None
        
        response_str = str(obj.response_body)
        if len(response_str) > 200:
            return response_str[:200] + "..."
        return response_str


class AdminWebhookBatchOperationSerializer(serializers.Serializer):
    """Admin serializer for batch webhook operations."""
    
    endpoint_ids = serializers.ListField(child=serializers.UUIDField())
    operation = serializers.ChoiceField(choices=[
        'activate',
        'deactivate',
        'suspend',
        'test',
        'rotate_secret',
        'check_health'
    ])
    
    def validate_endpoint_ids(self, value):
        """Validate endpoint IDs."""
        if not value:
            raise serializers.ValidationError("Endpoint IDs are required.")
        
        if len(value) > 100:
            raise serializers.ValidationError("Cannot process more than 100 endpoints at once.")
        
        return value
    
    def validate_operation(self, value):
        """Validate operation."""
        return value


class AdminWebhookStatsSerializer(serializers.Serializer):
    """Admin serializer for webhook statistics."""
    
    total_endpoints = serializers.IntegerField(read_only=True)
    active_endpoints = serializers.IntegerField(read_only=True)
    inactive_endpoints = serializers.IntegerField(read_only=True)
    suspended_endpoints = serializers.IntegerField(read_only=True)
    total_subscriptions = serializers.IntegerField(read_only=True)
    active_subscriptions = serializers.IntegerField(read_only=True)
    total_deliveries = serializers.IntegerField(read_only=True)
    successful_deliveries = serializers.IntegerField(read_only=True)
    failed_deliveries = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'total_endpoints',
            'active_endpoints',
            'inactive_endpoints',
            'suspended_endpoints',
            'total_subscriptions',
            'active_subscriptions',
            'total_deliveries',
            'successful_deliveries',
            'failed_deliveries',
            'success_rate',
            'avg_response_time'
        ]


class AdminWebhookHealthCheckSerializer(serializers.Serializer):
    """Admin serializer for webhook health check operations."""
    
    endpoint_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    all_endpoints = serializers.BooleanField(default=False)
    force_check = serializers.BooleanField(default=False)
    
    def validate_endpoint_ids(self, value):
        """Validate endpoint IDs."""
        if value is None:
            return value
        
        if len(value) > 50:
            raise serializers.ValidationError("Cannot check more than 50 endpoints at once.")
        
        return value


class AdminWebhookHealthCheckResultSerializer(serializers.Serializer):
    """Admin serializer for webhook health check results."""
    
    endpoint_id = serializers.UUIDField(read_only=True)
    endpoint_label = serializers.CharField(read_only=True)
    endpoint_url = serializers.URLField(read_only=True)
    is_healthy = serializers.BooleanField(read_only=True)
    status_code = serializers.IntegerField(read_only=True)
    response_time_ms = serializers.IntegerField(read_only=True)
    error = serializers.CharField(read_only=True)
    checked_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'endpoint_id',
            'endpoint_label',
            'endpoint_url',
            'is_healthy',
            'status_code',
            'response_time_ms',
            'error',
            'checked_at'
        ]


class AdminWebhookCleanupSerializer(serializers.Serializer):
    """Admin serializer for webhook cleanup operations."""
    
    operation = serializers.ChoiceField(choices=[
        'exhausted_logs',
        'failed_logs',
        'old_logs',
        'health_logs',
        'analytics',
        'all_data'
    ])
    days = serializers.IntegerField(min_value=1, default=30)
    
    def validate_operation(self, value):
        """Validate operation."""
        return value
    
    def validate_days(self, value):
        """Validate days."""
        if value < 1:
            raise serializers.ValidationError("Days must be at least 1.")
        return value


class AdminWebhookExportSerializer(serializers.Serializer):
    """Admin serializer for webhook export operations."""
    
    export_type = serializers.ChoiceField(choices=[
        'endpoints',
        'subscriptions',
        'delivery_logs',
        'health_logs',
        'analytics'
    ])
    format = serializers.ChoiceField(choices=['csv', 'json'], default='csv')
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    
    def validate_export_type(self, value):
        """Validate export type."""
        return value
    
    def validate_format(self, value):
        """Validate format."""
        return value
    
    def validate_date_from(self, value):
        """Validate date from."""
        return value
    
    def validate_date_to(self, value):
        """Validate date to."""
        return value


class AdminWebhookImportSerializer(serializers.Serializer):
    """Admin serializer for webhook import operations."""
    
    import_type = serializers.ChoiceField(choices=[
        'endpoints',
        'subscriptions'
    ])
    file = serializers.FileField()
    overwrite = serializers.BooleanField(default=False)
    
    def validate_import_type(self, value):
        """Validate import type."""
        return value
    
    def validate_file(self, value):
        """Validate file."""
        if not value:
            raise serializers.ValidationError("File is required.")
        
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        
        return value
    
    def validate_overwrite(self, value):
        """Validate overwrite."""
        return value


class AdminWebhookTestSerializer(serializers.Serializer):
    """Admin serializer for webhook test operations."""
    
    endpoint_id = serializers.UUIDField()
    test_payload = serializers.JSONField(required=False)
    custom_headers = serializers.JSONField(required=False)
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            WebhookEndpoint.objects.get(id=value)
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_test_payload(self, value):
        """Validate test payload."""
        if value is None:
            # Use default test payload
            return {
                'test': True,
                'timestamp': '2023-01-01T00:00:00Z',
                'message': 'Admin test webhook'
            }
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test payload must be a dictionary.")
        
        return value
    
    def validate_custom_headers(self, value):
        """Validate custom headers."""
        if value is None:
            return value
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom headers must be a dictionary.")
        
        return value


class AdminWebhookTestResultSerializer(serializers.Serializer):
    """Admin serializer for webhook test results."""
    
    endpoint_id = serializers.UUIDField(read_only=True)
    endpoint_label = serializers.CharField(read_only=True)
    endpoint_url = serializers.URLField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    status_code = serializers.IntegerField(read_only=True)
    response_time_ms = serializers.IntegerField(read_only=True)
    response_body = serializers.CharField(read_only=True)
    error = serializers.CharField(read_only=True)
    tested_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'endpoint_id',
            'endpoint_label',
            'endpoint_url',
            'success',
            'status_code',
            'response_time_ms',
            'response_body',
            'error',
            'tested_at'
        ]