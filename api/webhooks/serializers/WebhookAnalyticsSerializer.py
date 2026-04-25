"""Webhook Analytics Serializer

This serializer handles webhook analytics CRUD operations
including statistics and performance metrics.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit, WebhookRetryAnalysis


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
        
        # Add performance rating
        if instance.avg_latency_ms:
            if instance.avg_latency_ms < 100:
                data['performance_rating'] = 'Excellent'
            elif instance.avg_latency_ms < 500:
                data['performance_rating'] = 'Good'
            elif instance.avg_latency_ms < 1000:
                data['performance_rating'] = 'Fair'
            else:
                data['performance_rating'] = 'Poor'
        else:
            data['performance_rating'] = 'Unknown'
        
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
            if instance.response_time_ms < 100:
                data['response_time_category'] = 'Excellent'
            elif instance.response_time_ms < 500:
                data['response_time_category'] = 'Good'
            elif instance.response_time_ms < 1000:
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
    
    def to_representation(self, instance):
        """Customize event statistics representation."""
        data = super().to_representation(instance)
        
        # Add success rate
        if instance.fired_count > 0:
            data['success_rate'] = round((instance.delivered_count / instance.fired_count) * 100, 2)
        else:
            data['success_rate'] = 0
        
        return data


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
    
    def to_representation(self, instance):
        """Customize retry analysis representation."""
        data = super().to_representation(instance)
        
        # Add performance rating
        if instance.success_rate >= 95:
            data['performance_rating'] = 'Excellent'
        elif instance.success_rate >= 85:
            data['performance_rating'] = 'Good'
        elif instance.success_rate >= 70:
            data['performance_rating'] = 'Fair'
        elif instance.success_rate >= 50:
            data['performance_rating'] = 'Poor'
        else:
            data['performance_rating'] = 'Very Poor'
        
        return data
