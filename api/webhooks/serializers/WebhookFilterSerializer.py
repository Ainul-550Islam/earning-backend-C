"""Webhook Filter Serializer

This serializer handles webhook filter CRUD operations
including validation and configuration management.

FIX APPLIED:
- Added WebhookFilterCreateSerializer (for POST)
- Added WebhookFilterUpdateSerializer (for PATCH/PUT)
- Added WebhookFilterDetailSerializer (for GET single)
- Added WebhookFilterListSerializer (for GET list)
- All must be exported in serializers/__init__.py
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import WebhookFilter
from ..constants import FilterOperator


class WebhookFilterSerializer(serializers.ModelSerializer):
    """Base serializer for webhook filter CRUD operations."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    
    class Meta:
        model = WebhookFilter
        fields = [
            'id', 'endpoint', 'endpoint_name', 'field_path', 'operator', 'value',
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


class WebhookFilterCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhook filters (POST)."""
    
    class Meta:
        model = WebhookFilter
        fields = [
            'endpoint', 'field_path', 'operator', 'value', 'is_active',
        ]
    
    def validate_operator(self, value):
        """Validate filter operator."""
        if value not in [choice[0] for choice in FilterOperator.CHOICES]:
            raise serializers.ValidationError(_('Invalid operator'))
        return value
    
    def validate_value(self, value):
        """Validate filter value based on operator."""
        return value
    
    def validate_field_path(self, value):
        """Validate field path format."""
        if not value or not isinstance(value, str):
            raise serializers.ValidationError(_('Field path must be a non-empty string'))
        return value


class WebhookFilterUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating webhook filters (PATCH/PUT)."""
    
    class Meta:
        model = WebhookFilter
        fields = [
            'field_path', 'operator', 'value', 'is_active',
        ]
    
    def validate_operator(self, value):
        """Validate filter operator."""
        if value not in [choice[0] for choice in FilterOperator.CHOICES]:
            raise serializers.ValidationError(_('Invalid operator'))
        return value
    
    def validate_value(self, value):
        """Validate filter value based on operator."""
        return value


class WebhookFilterDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving single webhook filter details (GET)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    operator_display = serializers.CharField(source='get_operator_display', read_only=True)
    
    class Meta:
        model = WebhookFilter
        fields = [
            'id', 'endpoint', 'endpoint_name', 'field_path', 'operator',
            'operator_display', 'value', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'endpoint', 'created_at', 'updated_at']


class WebhookFilterListSerializer(serializers.ModelSerializer):
    """Serializer for listing webhook filters (GET list)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    
    class Meta:
        model = WebhookFilter
        fields = [
            'id', 'endpoint', 'endpoint_name', 'field_path', 'operator', 'value',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'endpoint', 'created_at', 'updated_at']

