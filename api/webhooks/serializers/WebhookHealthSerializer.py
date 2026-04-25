"""Webhook Health Serializer

This module contains the serializer for the WebhookHealthLog model.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookHealthLog, WebhookEndpoint

User = get_user_model()


class WebhookHealthLogSerializer(serializers.ModelSerializer):
    """Serializer for WebhookHealthLog model."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.url', read_only=True)
    
    class Meta:
        model = WebhookHealthLog
        fields = [
            'id',
            'endpoint',
            'endpoint_label',
            'endpoint_url',
            'is_healthy',
            'status_code',
            'response_time_ms',
            'error',
            'checked_at',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'checked_at', 'created_by']
    
    def validate_is_healthy(self, value):
        """Validate health status."""
        return value
    
    def validate_status_code(self, value):
        """Validate HTTP status code."""
        if value is not None and (value < 100 or value > 599):
            raise serializers.ValidationError("Status code must be between 100 and 599.")
        return value
    
    def validate_response_time_ms(self, value):
        """Validate response time."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Response time must be non-negative.")
        return value
    
    def validate_error(self, value):
        """Validate error message."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Error message must be a string.")
        return value


class WebhookHealthLogCreateSerializer(WebhookHealthLogSerializer):
    """Serializer for creating webhook health logs."""
    
    class Meta(WebhookHealthLogSerializer.Meta):
        fields = [
            'endpoint',
            'is_healthy',
            'status_code',
            'response_time_ms',
            'error'
        ]


class WebhookHealthLogUpdateSerializer(WebhookHealthLogSerializer):
    """Serializer for updating webhook health logs."""
    
    class Meta(WebhookHealthLogSerializer.Meta):
        fields = [
            'is_healthy',
            'status_code',
            'response_time_ms',
            'error',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class WebhookHealthLogDetailSerializer(WebhookHealthLogSerializer):
    """Detailed serializer for webhook health logs."""
    
    endpoint = serializers.PrimaryKeyRelatedField(queryset=WebhookEndpoint.objects.all())
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta(WebhookHealthLogSerializer.Meta):
        fields = WebhookHealthLogSerializer.Meta.fields + [
            'created_by_username'
        ]


class WebhookHealthLogListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing webhook health logs."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.url', read_only=True)
    
    class Meta:
        model = WebhookHealthLog
        fields = [
            'id',
            'endpoint_label',
            'endpoint_url',
            'is_healthy',
            'status_code',
            'response_time_ms',
            'checked_at'
        ]


class WebhookHealthCheckSerializer(serializers.Serializer):
    """Serializer for webhook health check operations."""
    
    endpoint_id = serializers.UUIDField(required=False)
    all_endpoints = serializers.BooleanField(default=False)
    
    def validate_endpoint_id(self, value):
        """Validate endpoint ID."""
        return value
    
    def validate_all_endpoints(self, value):
        """Validate all endpoints flag."""
        return value


class WebhookHealthCheckResultSerializer(serializers.Serializer):
    """Serializer for webhook health check results."""
    
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


class WebhookHealthStatsSerializer(serializers.Serializer):
    """Serializer for webhook health statistics."""
    
    total_checks = serializers.IntegerField(read_only=True)
    healthy_checks = serializers.IntegerField(read_only=True)
    unhealthy_checks = serializers.IntegerField(read_only=True)
    uptime_percentage = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    min_response_time = serializers.FloatField(read_only=True)
    max_response_time = serializers.FloatField(read_only=True)
    last_check = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'total_checks',
            'healthy_checks',
            'unhealthy_checks',
            'uptime_percentage',
            'avg_response_time',
            'min_response_time',
            'max_response_time',
            'last_check'
        ]


class WebhookHealthTrendSerializer(serializers.Serializer):
    """Serializer for webhook health trends."""
    
    date = serializers.DateField(read_only=True)
    total_checks = serializers.IntegerField(read_only=True)
    healthy_checks = serializers.IntegerField(read_only=True)
    unhealthy_checks = serializers.IntegerField(read_only=True)
    uptime_percentage = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'date',
            'total_checks',
            'healthy_checks',
            'unhealthy_checks',
            'uptime_percentage',
            'avg_response_time'
        ]


class WebhookHealthFilterSerializer(serializers.Serializer):
    """Serializer for filtering webhook health logs."""
    
    endpoint_id = serializers.UUIDField(required=False)
    is_healthy = serializers.BooleanField(required=False)
    status_code = serializers.IntegerField(required=False)
    checked_at_from = serializers.DateTimeField(required=False)
    checked_at_to = serializers.DateTimeField(required=False)
    
    def validate_status_code(self, value):
        """Validate status code filter."""
        if value is not None and (value < 100 or value > 599):
            raise serializers.ValidationError("Status code must be between 100 and 599.")
        return value
    
    def validate_checked_at_from(self, value):
        """Validate checked_at_from filter."""
        return value
    
    def validate_checked_at_to(self, value):
        """Validate checked_at_to filter."""
        return value


class WebhookHealthBatchSerializer(serializers.Serializer):
    """Serializer for batch webhook health checks."""
    
    endpoint_ids = serializers.ListField(child=serializers.UUIDField())
    
    def validate_endpoint_ids(self, value):
        """Validate endpoint IDs."""
        if not value:
            raise serializers.ValidationError("Endpoint IDs are required.")
        
        if len(value) > 50:
            raise serializers.ValidationError("Cannot check more than 50 endpoints at once.")
        
        return value


class WebhookHealthAlertSerializer(serializers.Serializer):
    """Serializer for webhook health alerts."""
    
    endpoint_id = serializers.UUIDField(read_only=True)
    endpoint_label = serializers.CharField(read_only=True)
    endpoint_url = serializers.URLField(read_only=True)
    alert_type = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        fields = [
            'endpoint_id',
            'endpoint_label',
            'endpoint_url',
            'alert_type',
            'message',
            'severity',
            'created_at'
        ]
