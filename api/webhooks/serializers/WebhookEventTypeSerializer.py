"""Webhook Event Type Serializer

This module contains the serializer for webhook event types.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookSubscription, WebhookEndpoint

User = get_user_model()


class WebhookEventTypeSerializer(serializers.Serializer):
    """Serializer for webhook event types."""
    
    event_types = serializers.ListField(child=serializers.CharField())
    
    def validate_event_types(self, value):
        """Validate event types list."""
        if not value:
            raise serializers.ValidationError("Event types list cannot be empty.")
        
        # Validate event type format (e.g., 'user.created')
        for event_type in value:
            if '.' not in event_type:
                raise serializers.ValidationError(f"Event type '{event_type}' must be in format 'domain.event'.")
        
        return value


class WebhookEventTypeDetailSerializer(serializers.Serializer):
    """Serializer for detailed webhook event type information."""
    
    event_type = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    subscription_count = serializers.IntegerField(read_only=True)
    endpoint_count = serializers.IntegerField(read_only=True)
    last_emitted = serializers.DateTimeField(read_only=True, required=False)
    
    class Meta:
        fields = [
            'event_type',
            'description',
            'subscription_count',
            'endpoint_count',
            'last_emitted'
        ]


class WebhookEventTypeStatsSerializer(serializers.Serializer):
    """Serializer for webhook event type statistics."""
    
    event_type = serializers.CharField()
    total_emits = serializers.IntegerField(read_only=True)
    successful_emits = serializers.IntegerField(read_only=True)
    failed_emits = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    last_emitted = serializers.DateTimeField(read_only=True, required=False)
    
    class Meta:
        fields = [
            'event_type',
            'total_emits',
            'successful_emits',
            'failed_emits',
            'success_rate',
            'avg_response_time',
            'last_emitted'
        ]


class WebhookEventTypeFilterSerializer(serializers.Serializer):
    """Serializer for filtering webhook event types."""
    
    domain = serializers.CharField(required=False)
    event = serializers.CharField(required=False)
    has_subscriptions = serializers.BooleanField(required=False)
    
    def validate_domain(self, value):
        """Validate domain filter."""
        if value is None:
            return value
        
        if not value.isalnum():
            raise serializers.ValidationError("Domain must be alphanumeric.")
        
        return value
    
    def validate_event(self, value):
        """Validate event filter."""
        if value is None:
            return value
        
        if not value.isalnum():
            raise serializers.ValidationError("Event must be alphanumeric.")
        
        return value
    
    def validate_has_subscriptions(self, value):
        """Validate has_subscriptions filter."""
        return value


class WebhookEventTypeCreateSerializer(serializers.Serializer):
    """Serializer for creating webhook event types."""
    
    event_type = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_description(self, value):
        """Validate description."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Description must be a string.")
        
        return value


class WebhookEventTypeUpdateSerializer(serializers.Serializer):
    """Serializer for updating webhook event types."""
    
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_description(self, value):
        """Validate description."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Description must be a string.")
        
        return value


class WebhookEventTypeListSerializer(serializers.Serializer):
    """Serializer for listing webhook event types."""
    
    event_type = serializers.CharField()
    subscription_count = serializers.IntegerField(read_only=True)
    endpoint_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        fields = [
            'event_type',
            'subscription_count',
            'endpoint_count'
        ]


class WebhookEventTypeSubscriptionSerializer(serializers.Serializer):
    """Serializer for webhook event type subscriptions."""
    
    event_type = serializers.CharField()
    endpoint_id = serializers.UUIDField()
    is_active = serializers.BooleanField(default=True)
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        if not value:
            raise serializers.ValidationError("Endpoint ID is required.")
        
        try:
            WebhookEndpoint.objects.get(id=value)
        except WebhookEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found.")
        
        return value
    
    def validate_is_active(self, value):
        """Validate is_active."""
        return value


class WebhookEventTypeSubscriptionResultSerializer(serializers.Serializer):
    """Serializer for webhook event type subscription results."""
    
    subscription_id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    endpoint_id = serializers.UUIDField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'subscription_id',
            'event_type',
            'endpoint_id',
            'is_active',
            'created_at'
        ]


class WebhookEventTypePopularSerializer(serializers.Serializer):
    """Serializer for popular webhook event types."""
    
    event_type = serializers.CharField(read_only=True)
    emit_count = serializers.IntegerField(read_only=True)
    subscription_count = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'event_type',
            'emit_count',
            'subscription_count',
            'success_rate'
        ]


class WebhookEventTypeRecentSerializer(serializers.Serializer):
    """Serializer for recent webhook event types."""
    
    event_type = serializers.CharField(read_only=True)
    last_emitted = serializers.DateTimeField(read_only=True)
    emit_count_24h = serializers.IntegerField(read_only=True)
    success_rate_24h = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'event_type',
            'last_emitted',
            'emit_count_24h',
            'success_rate_24h'
        ]


class WebhookEventTypeTrendSerializer(serializers.Serializer):
    """Serializer for webhook event type trends."""
    
    event_type = serializers.CharField(read_only=True)
    date = serializers.DateField(read_only=True)
    emit_count = serializers.IntegerField(read_only=True)
    success_count = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'event_type',
            'date',
            'emit_count',
            'success_count',
            'success_rate',
            'avg_response_time'
        ]


class WebhookEventTypeRecommendationSerializer(serializers.Serializer):
    """Serializer for webhook event type recommendations."""
    
    event_type = serializers.CharField(read_only=True)
    recommendation = serializers.CharField(read_only=True)
    confidence = serializers.FloatField(read_only=True)
    reason = serializers.CharField(read_only=True)
    
    class Meta:
        fields = [
            'event_type',
            'recommendation',
            'confidence',
            'reason'
        ]


class WebhookEventTypeValidateSerializer(serializers.Serializer):
    """Serializer for validating webhook event types."""
    
    event_type = serializers.CharField()
    
    def validate_event_type(self, value):
        """Validate event type."""
        if not value:
            raise serializers.ValidationError("Event type is required.")
        
        # Validate event type format (e.g., 'user.created')
        if '.' not in value:
            raise serializers.ValidationError("Event type must be in format 'domain.event'.")
        
        return value


class WebhookEventTypeValidateResultSerializer(serializers.Serializer):
    """Serializer for webhook event type validation results."""
    
    valid = serializers.BooleanField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    domain = serializers.CharField(read_only=True)
    event = serializers.CharField(read_only=True)
    warnings = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)
    errors = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)
    
    class Meta:
        fields = [
            'valid',
            'event_type',
            'domain',
            'event',
            'warnings',
            'errors'
        ]
