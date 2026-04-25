"""Inbound Webhook Log Serializer

This module contains the serializer for the InboundWebhookLog model.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import InboundWebhookLog, InboundWebhook

User = get_user_model()


class InboundWebhookLogSerializer(serializers.ModelSerializer):
    """Serializer for InboundWebhookLog model."""
    
    inbound_source = serializers.CharField(source='inbound.source', read_only=True)
    inbound_url_token = serializers.CharField(source='inbound.url_token', read_only=True)
    
    class Meta:
        model = InboundWebhookLog
        fields = [
            'id',
            'inbound',
            'inbound_source',
            'inbound_url_token',
            'raw_payload',
            'headers',
            'signature',
            'signature_valid',
            'processed',
            'processed_at',
            'error_message',
            'ip_address',
            'user_agent',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'processed_at',
            'signature_valid', 'processed'
        ]
    
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
    
    def validate_signature(self, value):
        """Validate signature."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Signature must be a string.")
        return value
    
    def validate_ip_address(self, value):
        """Validate IP address."""
        if value is None:
            return value
        
        import ipaddress
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise serializers.ValidationError(f"Invalid IP address: {value}")
        return value
    
    def validate_user_agent(self, value):
        """Validate user agent."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("User agent must be a string.")
        return value


class InboundWebhookLogCreateSerializer(InboundWebhookLogSerializer):
    """Serializer for creating inbound webhook logs."""
    
    class Meta(InboundWebhookLogSerializer.Meta):
        fields = [
            'inbound',
            'raw_payload',
            'headers',
            'signature',
            'ip_address',
            'user_agent'
        ]


class InboundWebhookLogUpdateSerializer(InboundWebhookLogSerializer):
    """Serializer for updating inbound webhook logs."""
    
    class Meta(InboundWebhookLogSerializer.Meta):
        fields = [
            'processed',
            'processed_at',
            'error_message',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class InboundWebhookLogDetailSerializer(InboundWebhookLogSerializer):
    """Detailed serializer for inbound webhook logs."""
    
    inbound = serializers.PrimaryKeyRelatedField(queryset=InboundWebhook.objects.all())
    
    class Meta(InboundWebhookLogSerializer.Meta):
        fields = InboundWebhookLogSerializer.Meta.fields


class InboundWebhookLogListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing inbound webhook logs."""
    
    inbound_source = serializers.CharField(source='inbound.source', read_only=True)
    inbound_url_token = serializers.CharField(source='inbound.url_token', read_only=True)
    
    class Meta:
        model = InboundWebhookLog
        fields = [
            'id',
            'inbound_source',
            'inbound_url_token',
            'processed',
            'signature_valid',
            'ip_address',
            'created_at'
        ]


class InboundWebhookLogProcessSerializer(serializers.Serializer):
    """Serializer for processing inbound webhook logs."""
    
    processed = serializers.BooleanField(required=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    
    def validate_processed(self, value):
        """Validate processed status."""
        return value
    
    def validate_error_message(self, value):
        """Validate error message."""
        if value is None:
            return value
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Error message must be a string.")
        return value


class InboundWebhookLogStatsSerializer(serializers.Serializer):
    """Serializer for inbound webhook log statistics."""
    
    total_count = serializers.IntegerField(read_only=True)
    processed_count = serializers.IntegerField(read_only=True)
    unprocessed_count = serializers.IntegerField(read_only=True)
    signature_valid_count = serializers.IntegerField(read_only=True)
    signature_invalid_count = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'total_count',
            'processed_count',
            'unprocessed_count',
            'signature_valid_count',
            'signature_invalid_count',
            'success_rate'
        ]


class InboundWebhookLogFilterSerializer(serializers.Serializer):
    """Serializer for filtering inbound webhook logs."""
    
    inbound_id = serializers.UUIDField(required=False)
    source = serializers.CharField(required=False)
    processed = serializers.BooleanField(required=False)
    signature_valid = serializers.BooleanField(required=False)
    created_at_from = serializers.DateTimeField(required=False)
    created_at_to = serializers.DateTimeField(required=False)
    ip_address = serializers.IPAddressField(required=False)
    
    def validate_source(self, value):
        """Validate source filter."""
        if value is None:
            return value
        
        from ..constants import InboundSource
        valid_sources = [source.value for source in InboundSource]
        if value not in valid_sources:
            raise serializers.ValidationError(f"Source must be one of: {valid_sources}")
        return value
    
    def validate_created_at_from(self, value):
        """Validate created_at_from filter."""
        return value
    
    def validate_created_at_to(self, value):
        """Validate created_at_to filter."""
        return value


class InboundWebhookLogBatchSerializer(serializers.Serializer):
    """Serializer for batch processing inbound webhook logs."""
    
    log_ids = serializers.ListField(child=serializers.UUIDField())
    processed = serializers.BooleanField(required=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    
    def validate_log_ids(self, value):
        """Validate log IDs."""
        if not value:
            raise serializers.ValidationError("Log IDs are required.")
        
        if len(value) > 100:
            raise serializers.ValidationError("Cannot process more than 100 logs at once.")
        
        return value
    
    def validate_processed(self, value):
        """Validate processed status."""
        return value
