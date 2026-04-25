"""Inbound Webhook Serializer

This module contains the serializer for inbound webhook models.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError
from ..constants import InboundSource

User = get_user_model()


class InboundWebhookSerializer(serializers.ModelSerializer):
    """Serializer for InboundWebhook model."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = InboundWebhook
        fields = [
            'id',
            'source',
            'url_token',
            'secret',
            'description',
            'is_active',
            'ip_whitelist',
            'allowed_origins',
            'max_payload_size',
            'signature_header',
            'event_type_header',
            'timestamp_header',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def validate_source(self, value):
        """Validate source."""
        valid_sources = [source.value for source in InboundSource]
        if value not in valid_sources:
            raise serializers.ValidationError(f"Source must be one of: {valid_sources}")
        return value
    
    def validate_url_token(self, value):
        """Validate URL token."""
        if not value:
            raise serializers.ValidationError("URL token is required.")
        
        if len(value) < 8:
            raise serializers.ValidationError("URL token must be at least 8 characters long.")
        
        return value
    
    def validate_secret(self, value):
        """Validate secret."""
        if not value:
            raise serializers.ValidationError("Secret is required.")
        
        if len(value) < 16:
            raise serializers.ValidationError("Secret must be at least 16 characters long.")
        
        return value
    
    def validate_ip_whitelist(self, value):
        """Validate IP whitelist."""
        if value is None:
            return value
        
        if not isinstance(value, list):
            raise serializers.ValidationError("IP whitelist must be a list.")
        
        import ipaddress
        for ip in value:
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                raise serializers.ValidationError(f"Invalid IP address: {ip}")
        
        return value
    
    def validate_allowed_origins(self, value):
        """Validate allowed origins."""
        if value is None:
            return value
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Allowed origins must be a list.")
        
        from urllib.parse import urlparse
        for origin in value:
            try:
                parsed = urlparse(origin)
                if not parsed.scheme or not parsed.netloc:
                    raise serializers.ValidationError(f"Invalid origin URL: {origin}")
            except ValueError:
                raise serializers.ValidationError(f"Invalid origin URL: {origin}")
        
        return value
    
    def validate_max_payload_size(self, value):
        """Validate max payload size."""
        if value <= 0:
            raise serializers.ValidationError("Max payload size must be greater than 0.")
        return value


class InboundWebhookCreateSerializer(InboundWebhookSerializer):
    """Serializer for creating inbound webhooks."""
    
    class Meta(InboundWebhookSerializer.Meta):
        fields = [
            'source',
            'description',
            'ip_whitelist',
            'allowed_origins',
            'max_payload_size',
            'signature_header',
            'event_type_header',
            'timestamp_header'
        ]


class InboundWebhookUpdateSerializer(InboundWebhookSerializer):
    """Serializer for updating inbound webhooks."""
    
    class Meta(InboundWebhookSerializer.Meta):
        fields = [
            'description',
            'is_active',
            'ip_whitelist',
            'allowed_origins',
            'max_payload_size',
            'signature_header',
            'event_type_header',
            'timestamp_header',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class InboundWebhookDetailSerializer(InboundWebhookSerializer):
    """Detailed serializer for inbound webhooks."""
    
    total_logs = serializers.SerializerMethodField()
    recent_logs = serializers.SerializerMethodField()
    
    class Meta(InboundWebhookSerializer.Meta):
        fields = InboundWebhookSerializer.Meta.fields + [
            'total_logs',
            'recent_logs'
        ]
    
    def get_total_logs(self, obj):
        """Get total number of logs."""
        return obj.logs.count()
    
    def get_recent_logs(self, obj):
        """Get recent logs count."""
        from django.utils import timezone
        from datetime import timedelta
        
        recent = timezone.now() - timedelta(hours=24)
        return obj.logs.filter(created_at__gte=recent).count()


class InboundWebhookLogSerializer(serializers.ModelSerializer):
    """Serializer for InboundWebhookLog model."""
    
    inbound_source = serializers.CharField(source='inbound.source', read_only=True)
    
    class Meta:
        model = InboundWebhookLog
        fields = [
            'id',
            'inbound',
            'inbound_source',
            'raw_payload',
            'headers',
            'signature',
            'processed',
            'processed_at',
            'error_message',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processed_at']
    
    def validate_raw_payload(self, value):
        """Validate raw payload."""
        if not value:
            raise serializers.ValidationError("Raw payload is required.")
        return value
    
    def validate_headers(self, value):
        """Validate headers."""
        if value is None:
            return value
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Headers must be a dictionary.")
        return value


class InboundWebhookRouteSerializer(serializers.ModelSerializer):
    """Serializer for InboundWebhookRoute model."""
    
    inbound_source = serializers.CharField(source='inbound.source', read_only=True)
    
    class Meta:
        model = InboundWebhookRoute
        fields = [
            'id',
            'inbound',
            'inbound_source',
            'event_pattern',
            'handler_function',
            'priority',
            'timeout_seconds',
            'retry_attempts',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_event_pattern(self, value):
        """Validate event pattern."""
        if not value:
            raise serializers.ValidationError("Event pattern is required.")
        
        # Basic regex validation
        import re
        try:
            re.compile(value)
        except re.error:
            raise serializers.ValidationError("Invalid event pattern regex.")
        
        return value
    
    def validate_handler_function(self, value):
        """Validate handler function."""
        if not value:
            raise serializers.ValidationError("Handler function is required.")
        return value
    
    def validate_priority(self, value):
        """Validate priority."""
        if value < 0:
            raise serializers.ValidationError("Priority must be non-negative.")
        return value
    
    def validate_timeout_seconds(self, value):
        """Validate timeout seconds."""
        if value <= 0:
            raise serializers.ValidationError("Timeout seconds must be greater than 0.")
        return value
    
    def validate_retry_attempts(self, value):
        """Validate retry attempts."""
        if value < 0:
            raise serializers.ValidationError("Retry attempts must be non-negative.")
        return value


class InboundWebhookErrorSerializer(serializers.ModelSerializer):
    """Serializer for InboundWebhookError model."""
    
    log_inbound_source = serializers.CharField(source='log.inbound.source', read_only=True)
    
    class Meta:
        model = InboundWebhookError
        fields = [
            'id',
            'log',
            'log_inbound_source',
            'error_type',
            'error_code',
            'error_message',
            'error_details',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_error_type(self, value):
        """Validate error type."""
        if not value:
            raise serializers.ValidationError("Error type is required.")
        return value
    
    def validate_error_code(self, value):
        """Validate error code."""
        if not value:
            raise serializers.ValidationError("Error code is required.")
        return value


class InboundWebhookProcessSerializer(serializers.Serializer):
    """Serializer for processing inbound webhooks."""
    
    raw_payload = serializers.JSONField()
    headers = serializers.JSONField(required=False)
    signature = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    
    def validate_raw_payload(self, value):
        """Validate raw payload."""
        if not value:
            raise serializers.ValidationError("Raw payload is required.")
        return value
    
    def validate_headers(self, value):
        """Validate headers."""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Headers must be a dictionary.")
        return value


class InboundWebhookValidateSerializer(serializers.Serializer):
    """Serializer for validating inbound webhooks."""
    
    signature = serializers.CharField()
    payload = serializers.JSONField()
    headers = serializers.JSONField(required=False)
    
    def validate_signature(self, value):
        """Validate signature."""
        if not value:
            raise serializers.ValidationError("Signature is required.")
        return value
    
    def validate_payload(self, value):
        """Validate payload."""
        if not value:
            raise serializers.ValidationError("Payload is required.")
        return value
