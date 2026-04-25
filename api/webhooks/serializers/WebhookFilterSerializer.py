"""Webhook Filter Serializer

This serializer handles webhook filter CRUD operations
including validation and configuration management.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import WebhookFilter
from ..constants import FilterOperator


class WebhookFilterSerializer(serializers.ModelSerializer):
    """Serializer for webhook filter CRUD operations."""
    
    class Meta:
        model = WebhookFilter
        fields = [
            'id', 'endpoint', 'field_path', 'operator', 'value',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_operator(self, value):
        """Validate filter operator."""
        if value not in [choice[0] for choice in FilterOperator.CHOICES]:
            raise serializers.ValidationError(_('Invalid operator'))
        return value
    
    def validate_value(self, value):
        """Validate filter value based on operator."""
        # Add validation logic based on operator type
        return value


class WebhookTemplateSerializer(serializers.ModelSerializer):
    """Serializer for webhook template CRUD operations."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'id', 'name', 'event_type', 'payload_template',
            'transform_rules', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_payload_template(self, value):
        """Validate Jinja2 template syntax."""
        try:
            from jinja2 import Environment, TemplateSyntaxError
            env = Environment()
            env.from_string(value)
            return value
        except TemplateSyntaxError as e:
            raise serializers.ValidationError(_('Invalid Jinja2 template: {}').format(str(e)))
    
    def validate_transform_rules(self, value):
        """Validate transformation rules JSON."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_('Transform rules must be a JSON object'))
        return value


class WebhookBatchSerializer(serializers.ModelSerializer):
    """Serializer for webhook batch CRUD operations."""
    
    class Meta:
        model = WebhookBatch
        fields = [
            'id', 'batch_id', 'endpoint', 'event_count',
            'status', 'created_at', 'completed_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookBatchItemSerializer(serializers.ModelSerializer):
    """Serializer for webhook batch item CRUD operations."""
    
    class Meta:
        model = WebhookBatchItem
        fields = [
            'id', 'batch', 'delivery_log', 'position',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class WebhookSecretSerializer(serializers.ModelSerializer):
    """Serializer for webhook secret CRUD operations."""
    
    class Meta:
        model = WebhookSecret
        fields = [
            'id', 'endpoint', 'secret_hash', 'created_at',
            'expires_at', 'is_active',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Customize secret representation."""
        data = super().to_representation(instance)
        # Never expose actual secret in API responses
        data.pop('secret_hash', None)
        data['secret_exists'] = bool(instance.secret_hash)
        return data


class WebhookAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for webhook analytics CRUD operations."""
    
    class Meta:
        model = WebhookAnalytics
        fields = [
            'id', 'date', 'endpoint', 'total_sent', 'success_count',
            'failed_count', 'avg_latency_ms', 'success_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookHealthLogSerializer(serializers.ModelSerializer):
    """Serializer for webhook health log CRUD operations."""
    
    class Meta:
        model = WebhookHealthLog
        fields = [
            'id', 'endpoint', 'checked_at', 'is_healthy',
            'response_time_ms', 'status_code', 'error',
        ]
        read_only_fields = ['id', 'created_at']


class WebhookEventStatSerializer(serializers.ModelSerializer):
    """Serializer for webhook event statistics CRUD operations."""
    
    class Meta:
        model = WebhookEventStat
        fields = [
            'id', 'date', 'event_type', 'fired_count',
            'delivered_count', 'failed_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookRateLimitSerializer(serializers.ModelSerializer):
    """Serializer for webhook rate limit CRUD operations."""
    
    class Meta:
        model = WebhookRateLimit
        fields = [
            'id', 'endpoint', 'window_seconds', 'max_requests',
            'current_count', 'reset_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
