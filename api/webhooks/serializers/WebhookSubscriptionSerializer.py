# Custom exception available: from ..exceptions import WebhookValidationError
"""Webhook Subscription Serializer

This module contains the serializer for the WebhookSubscription model.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookSubscription, WebhookEndpoint
from ..choices import WebhookStatus

User = get_user_model()


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for WebhookSubscription model."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.target_url', read_only=True)
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id',
            'endpoint',
            'endpoint_label',
            'endpoint_url',
            'event_type',
            'is_active',
            'filters',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_endpoint(self, value):
        """Validate that the endpoint exists and is active."""
        if not value:
            raise serializers.ValidationError("Endpoint is required.")
        
        if value.status != WebhookStatus.ACTIVE:
            raise serializers.ValidationError("Endpoint must be active to create subscriptions.")
        
        return value
    
    def validate_filters(self, value):
        """Filters must be a JSON object."""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a JSON object.")
        return value
    
    def validate(self, attrs):
        """Validate that subscription doesn't already exist."""
        endpoint = attrs.get('endpoint')
        event_type = attrs.get('event_type')
        
        # Check if subscription already exists
        if endpoint and event_type:
            existing_subscription = WebhookSubscription.objects.filter(
                endpoint=endpoint,
                event_type=event_type
            ).first()
            
            if existing_subscription and (not self.instance or existing_subscription.id != self.instance.id):
                raise serializers.ValidationError(
                    "A subscription for this endpoint and event type already exists."
                )
        
        return attrs


class WebhookSubscriptionCreateSerializer(WebhookSubscriptionSerializer):
    """Serializer for creating webhook subscriptions."""
    
    class Meta(WebhookSubscriptionSerializer.Meta):
        fields = WebhookSubscriptionSerializer.Meta.fields
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookSubscriptionUpdateSerializer(WebhookSubscriptionSerializer):
    """Serializer for updating webhook subscriptions."""
    
    class Meta(WebhookSubscriptionSerializer.Meta):
        fields = [
            'is_active',
            'filters',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class WebhookSubscriptionDetailSerializer(WebhookSubscriptionSerializer):
    """Detailed serializer for webhook subscriptions."""
    
    endpoint = serializers.PrimaryKeyRelatedField(queryset=WebhookEndpoint.objects.all())
    delivery_count = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta(WebhookSubscriptionSerializer.Meta):
        fields = WebhookSubscriptionSerializer.Meta.fields + [
            'delivery_count',
            'success_rate'
        ]
    
    def get_delivery_count(self, obj):
        """Get the number of deliveries for this subscription."""
        from ..models import WebhookDeliveryLog
        return WebhookDeliveryLog.objects.filter(
            endpoint=obj.endpoint,
            event_type=obj.event_type
        ).count()
    
    def get_success_rate(self, obj):
        """Calculate success rate for this subscription."""
        from ..models import WebhookDeliveryLog
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=obj.endpoint,
            event_type=obj.event_type
        )
        
        if not deliveries.exists():
            return 0.0
        
        success_count = deliveries.filter(status='success').count()
        return round((success_count / deliveries.count()) * 100, 2)


class WebhookSubscriptionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing webhook subscriptions."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.target_url', read_only=True)
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id',
            'endpoint_label',
            'endpoint_url',
            'event_type',
            'is_active',
            'created_at'
        ]