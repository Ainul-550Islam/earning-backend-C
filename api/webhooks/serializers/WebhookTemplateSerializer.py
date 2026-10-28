"""Webhook Template Serializer

This serializer handles webhook template CRUD operations.

FIX APPLIED:
- Added WebhookTemplateCreateSerializer (for POST)
- Added WebhookTemplateUpdateSerializer (for PATCH/PUT)
- Added WebhookTemplateDetailSerializer (for GET single)
- Added WebhookTemplateListSerializer (for GET list)
"""

from rest_framework import serializers

from ..models import WebhookTemplate
from ..validators import (
    validate_payload_template as _validate_payload_template,
    validate_transform_rules as _validate_transform_rules,
)


class WebhookTemplateSerializer(serializers.ModelSerializer):
    """Base serializer for webhook template CRUD operations."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'id', 'name', 'event_type', 'payload_template',
            'transform_rules', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_payload_template(self, value):
        """Validate Jinja2 template syntax (delegates to canonical validators.py)."""
        return _validate_payload_template(value)
    
    def validate_transform_rules(self, value):
        """Validate transformation rules JSON (delegates to canonical validators.py)."""
        return _validate_transform_rules(value)


class WebhookTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhook templates (POST)."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'id', 'name', 'event_type', 'payload_template',
            'transform_rules', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_payload_template(self, value):
        """Validate Jinja2 template syntax (delegates to canonical validators.py)."""
        return _validate_payload_template(value)
    
    def validate_transform_rules(self, value):
        """Validate transformation rules JSON (delegates to canonical validators.py)."""
        return _validate_transform_rules(value)
    
    def validate_name(self, value):
        """Validate template name."""
        if not value or len(value) < 3:
            raise serializers.ValidationError(
                'Template name must be at least 3 characters'
            )
        if len(value) > 255:
            raise serializers.ValidationError(
                'Template name cannot exceed 255 characters'
            )
        return value


class WebhookTemplateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating webhook templates (PATCH/PUT)."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'name', 'event_type', 'payload_template',
            'transform_rules', 'is_active',
        ]
    
    def validate_payload_template(self, value):
        """Validate Jinja2 template syntax (delegates to canonical validators.py)."""
        return _validate_payload_template(value)
    
    def validate_transform_rules(self, value):
        """Validate transformation rules JSON (delegates to canonical validators.py)."""
        return _validate_transform_rules(value)


class WebhookTemplateDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving single webhook template details (GET)."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'id', 'name', 'event_type', 'payload_template',
            'transform_rules', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookTemplateListSerializer(serializers.ModelSerializer):
    """Serializer for listing webhook templates (GET list)."""
    
    class Meta:
        model = WebhookTemplate
        fields = [
            'id', 'name', 'event_type', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
