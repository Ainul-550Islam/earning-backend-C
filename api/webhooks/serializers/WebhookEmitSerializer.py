"""Webhook Emit Serializer

This module contains the serializer for webhook emit operations.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookEndpoint
from ..choices import WebhookStatus

User = get_user_model()


class WebhookEmitSerializer(serializers.Serializer):
    """Serializer for webhook emit operations."""
    
    endpoint_id = serializers.UUIDField()
    event_type = serializers.CharField(max_length=255)
    payload = serializers.JSONField()
    async_emit = serializers.BooleanField(default=False)
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=value)
            if endpoint.status != WebhookStatus.ACTIVE:
                raise serializers.ValidationError("Endpoint must be active to emit webhooks.")
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_payload(self, value):
        """Validate payload."""
        if not value:
            raise serializers.ValidationError("Payload is required.")
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Payload must be a dictionary.")
        
        return value
    
    def validate_async_emit(self, value):
        """Validate async emit option."""
        return value


class WebhookEmitBatchSerializer(serializers.Serializer):
    """Serializer for batch webhook emit operations."""
    
    endpoint_id = serializers.UUIDField()
    event_type = serializers.CharField(max_length=255)
    events = serializers.ListField(child=serializers.JSONField())
    async_emit = serializers.BooleanField(default=False)
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=value)
            if endpoint.status != WebhookStatus.ACTIVE:
                raise serializers.ValidationError("Endpoint must be active to emit webhooks.")
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_events(self, value):
        """Validate events list."""
        if not value:
            raise serializers.ValidationError("Events list is required.")
        
        if len(value) > 1000:
            raise serializers.ValidationError("Cannot emit more than 1000 events at once.")
        
        for i, event in enumerate(value):
            if not isinstance(event, dict):
                raise serializers.ValidationError(f"Event at index {i} must be a dictionary.")
        
        return value
    
    def validate_async_emit(self, value):
        """Validate async emit option."""
        return value


class WebhookEmitTestSerializer(serializers.Serializer):
    """Serializer for webhook emit test operations."""
    
    endpoint_id = serializers.UUIDField()
    test_payload = serializers.JSONField(required=False)
    
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
                'message': 'Test webhook payload'
            }
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test payload must be a dictionary.")
        
        return value


class WebhookEmitResultSerializer(serializers.Serializer):
    """Serializer for webhook emit results."""
    
    success = serializers.BooleanField(read_only=True)
    endpoint_id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    delivery_log_id = serializers.UUIDField(read_only=True, required=False)
    error = serializers.CharField(read_only=True, required=False)
    processing_time = serializers.FloatField(read_only=True)
    emitted_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'success',
            'endpoint_id',
            'event_type',
            'delivery_log_id',
            'error',
            'processing_time',
            'emitted_at'
        ]


class WebhookEmitBatchResultSerializer(serializers.Serializer):
    """Serializer for webhook batch emit results."""
    
    success = serializers.BooleanField(read_only=True)
    endpoint_id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    total_events = serializers.IntegerField(read_only=True)
    processed_events = serializers.IntegerField(read_only=True)
    successful_events = serializers.IntegerField(read_only=True)
    failed_events = serializers.IntegerField(read_only=True)
    processing_time = serializers.FloatField(read_only=True)
    emitted_at = serializers.DateTimeField(read_only=True)
    errors = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)
    
    class Meta:
        fields = [
            'success',
            'endpoint_id',
            'event_type',
            'total_events',
            'processed_events',
            'successful_events',
            'failed_events',
            'processing_time',
            'emitted_at',
            'errors'
        ]


class WebhookEmitStatsSerializer(serializers.Serializer):
    """Serializer for webhook emit statistics."""
    
    total_emits = serializers.IntegerField(read_only=True)
    successful_emits = serializers.IntegerField(read_only=True)
    failed_emits = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_processing_time = serializers.FloatField(read_only=True)
    last_emit_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'total_emits',
            'successful_emits',
            'failed_emits',
            'success_rate',
            'avg_processing_time',
            'last_emit_at'
        ]


class WebhookEmitFilterSerializer(serializers.Serializer):
    """Serializer for filtering webhook emits."""
    
    endpoint_id = serializers.UUIDField(required=False)
    event_type = serializers.CharField(required=False)
    success = serializers.BooleanField(required=False)
    emitted_at_from = serializers.DateTimeField(required=False)
    emitted_at_to = serializers.DateTimeField(required=False)
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID filter."""
        return value
    
    def validate_event_type(self, value):
        """Validate event type filter."""
        return value
    
    def validate_success(self, value):
        """Validate success filter."""
        return value
    
    def validate_emitted_at_from(self, value):
        """Validate emitted_at_from filter."""
        return value
    
    def validate_emitted_at_to(self, value):
        """Validate emitted_at_to filter."""
        return value


class WebhookEmitPreviewSerializer(serializers.Serializer):
    """Serializer for webhook emit preview."""
    
    endpoint_id = serializers.UUIDField()
    event_type = serializers.CharField(max_length=255)
    payload = serializers.JSONField()
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            WebhookEndpoint.objects.get(id=value)
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_payload(self, value):
        """Validate payload."""
        if not value:
            raise serializers.ValidationError("Payload is required.")
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Payload must be a dictionary.")
        
        return value


class WebhookEmitPreviewResultSerializer(serializers.Serializer):
    """Serializer for webhook emit preview results."""
    
    endpoint_id = serializers.UUIDField(read_only=True)
    endpoint_url = serializers.URLField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    payload = serializers.JSONField(read_only=True)
    headers = serializers.JSONField(read_only=True)
    signature = serializers.CharField(read_only=True)
    estimated_size = serializers.IntegerField(read_only=True)
    estimated_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'endpoint_id',
            'endpoint_url',
            'event_type',
            'payload',
            'headers',
            'signature',
            'estimated_size',
            'estimated_time'
        ]


class WebhookEmitValidateSerializer(serializers.Serializer):
    """Serializer for validating webhook emit data."""
    
    endpoint_id = serializers.UUIDField()
    event_type = serializers.CharField(max_length=255)
    payload = serializers.JSONField()
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=value)
            if endpoint.status != WebhookStatus.ACTIVE:
                raise serializers.ValidationError("Endpoint must be active to emit webhooks.")
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_payload(self, value):
        """Validate payload."""
        if not value:
            raise serializers.ValidationError("Payload is required.")
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Payload must be a dictionary.")
        
        return value


class WebhookEmitValidateResultSerializer(serializers.Serializer):
    """Serializer for webhook emit validation results."""
    
    valid = serializers.BooleanField(read_only=True)
    endpoint_id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    payload_size = serializers.IntegerField(read_only=True)
    warnings = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)
    errors = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)
    
    class Meta:
        fields = [
            'valid',
            'endpoint_id',
            'event_type',
            'payload_size',
            'warnings',
            'errors'
        ]
