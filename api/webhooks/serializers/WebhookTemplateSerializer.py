"""Webhook Template Serializer

This serializer handles webhook template CRUD operations
including validation and configuration management.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import (
    WebhookTemplate, WebhookBatch, WebhookBatchItem, WebhookFilter,
    WebhookSecret, WebhookAnalytics, WebhookHealthLog, WebhookEventStat,
    WebhookRateLimit, WebhookRetryAnalysis, WebhookReplay,
    WebhookReplayBatch, WebhookReplayItem,
)


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
    
    def to_representation(self, instance):
        """Customize template representation."""
        data = super().to_representation(instance)
        
        # Add template preview
        if instance.payload_template:
            try:
                from jinja2 import Environment
                env = Environment()
                template = env.from_string(instance.payload_template)
                
                # Sample data for preview
                sample_data = {
                    'user_id': 12345,
                    'email': 'test@example.com',
                    'amount': 100.00,
                    'created_at': '2024-01-01T00:00:00Z',
                }
                
                data['template_preview'] = template.render(sample_data)
            except Exception:
                data['template_preview'] = None
        
        return data


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
        
        # Add expiration status
        if instance.expires_at:
            from django.utils import timezone
            days_until_expiry = (instance.expires_at - timezone.now()).days
            data['days_until_expiry'] = days_until_expiry
            data['is_expired'] = days_until_expiry <= 0
        else:
            data['days_until_expiry'] = None
            data['is_expired'] = False
        
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
    
    def to_representation(self, instance):
        """Customize analytics representation."""
        data = super().to_representation(instance)
        
        # Add calculated fields
        if instance.total_sent > 0:
            data['failure_rate'] = round((instance.failed_count / instance.total_sent) * 100, 2)
        else:
            data['failure_rate'] = 0
        
        return data


class WebhookHealthLogSerializer(serializers.ModelSerializer):
    """Serializer for webhook health log CRUD operations."""
    
    class Meta:
        model = WebhookHealthLog
        fields = [
            'id', 'endpoint', 'checked_at', 'is_healthy',
            'response_time_ms', 'status_code', 'error',
        ]
        read_only_fields = ['id', 'created_at']
    
    def to_representation(self, instance):
        """Customize health log representation."""
        data = super().to_representation(instance)
        
        # Add status display
        data['status_display'] = 'Healthy' if instance.is_healthy else 'Unhealthy'
        
        # Add response time category
        if instance.response_time_ms:
            response_time = instance.response_time_ms
            if response_time < 100:
                data['response_time_category'] = 'Excellent'
            elif response_time < 500:
                data['response_time_category'] = 'Good'
            elif response_time < 1000:
                data['response_time_category'] = 'Fair'
            else:
                data['response_time_category'] = 'Poor'
        else:
            data['response_time_category'] = 'Unknown'
        
        return data


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
    
    def to_representation(self, instance):
        """Customize rate limit representation."""
        data = super().to_representation(instance)
        
        # Add percentage fields
        if instance.max_requests > 0:
            data['usage_percentage'] = round((instance.current_count / instance.max_requests) * 100, 2)
            data['remaining_requests'] = instance.max_requests - instance.current_count
        else:
            data['usage_percentage'] = 0
            data['remaining_requests'] = instance.max_requests
        
        # Add time until reset
        if instance.reset_at:
            from django.utils import timezone
            time_until_reset = instance.reset_at - timezone.now()
            data['seconds_until_reset'] = max(0, int(time_until_reset.total_seconds()))
        else:
            data['seconds_until_reset'] = None
        
        return data


class WebhookRetryAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for webhook retry analysis CRUD operations."""
    
    class Meta:
        model = WebhookRetryAnalysis
        fields = [
            'id', 'endpoint', 'period', 'avg_attempts_before_success',
            'exhausted_count', 'success_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookReplaySerializer(serializers.ModelSerializer):
    """Serializer for webhook replay CRUD operations."""
    
    class Meta:
        model = WebhookReplay
        fields = [
            'id', 'original_log', 'replayed_by', 'new_log',
            'reason', 'status', 'replayed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Customize replay representation."""
        data = super().to_representation(instance)
        
        # Add status display
        status_choices = dict(instance._meta.get_field('status').choices)
        data['status_display'] = status_choices.get(instance.status, instance.status)
        
        return data


class WebhookReplayBatchSerializer(serializers.ModelSerializer):
    """Serializer for webhook replay batch CRUD operations."""
    
    class Meta:
        model = WebhookReplayBatch
        fields = [
            'id', 'created_by', 'event_type', 'date_from',
            'date_to', 'count', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookReplayItemSerializer(serializers.ModelSerializer):
    """Serializer for webhook replay item CRUD operations."""
    
    class Meta:
        model = WebhookReplayItem
        fields = [
            'id', 'batch', 'original_log', 'new_log',
            'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
