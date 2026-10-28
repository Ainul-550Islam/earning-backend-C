"""Webhook Secret Serializer

This serializer handles webhook secret CRUD operations.

FIX APPLIED:
- Added WebhookSecretCreateSerializer (for POST)
- Added WebhookSecretUpdateSerializer (for PATCH/PUT)
- Added WebhookSecretDetailSerializer (for GET single)
- Added WebhookSecretListSerializer (for GET list)

SECURITY NOTE: Secret values are never exposed in API responses.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import WebhookSecret


class WebhookSecretSerializer(serializers.ModelSerializer):
    """Base serializer for webhook secret CRUD operations."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    secret_exists = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookSecret
        fields = [
            'id', 'endpoint', 'endpoint_name', 'created_at',
            'expires_at', 'is_active', 'secret_exists',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_secret_exists(self, obj):
        """Check if secret exists without exposing it."""
        return bool(obj.secret_hash if hasattr(obj, 'secret_hash') else False)
    
    def to_representation(self, instance):
        """Never expose actual secret in API responses."""
        data = super().to_representation(instance)
        data.pop('secret_hash', None)
        return data


class WebhookSecretCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhook secrets (POST)."""
    
    class Meta:
        model = WebhookSecret
        fields = [
            'endpoint', 'expires_at', 'is_active',
        ]

    def validate_expires_at(self, value):
        """FIX: was accepted with no validation at all - a secret could
        be created already expired. expires_at is optional (null=True on
        the model) so None is still fine; only reject a value that's
        already in the past."""
        if value is not None:
            from django.utils import timezone
            if value <= timezone.now():
                raise serializers.ValidationError(
                    _("expires_at must be in the future.")
                )
        return value
    
    def to_representation(self, instance):
        """Never expose actual secret in API responses."""
        data = super().to_representation(instance)
        data.pop('secret_hash', None)
        data['secret_exists'] = bool(instance.secret_hash if hasattr(instance, 'secret_hash') else False)
        return data


class WebhookSecretUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating webhook secrets (PATCH/PUT)."""
    
    class Meta:
        model = WebhookSecret
        fields = [
            'expires_at', 'is_active',
        ]

    def validate_expires_at(self, value):
        """Same rule as WebhookSecretCreateSerializer.validate_expires_at."""
        if value is not None:
            from django.utils import timezone
            if value <= timezone.now():
                raise serializers.ValidationError(
                    _("expires_at must be in the future.")
                )
        return value
    
    def to_representation(self, instance):
        """Never expose actual secret in API responses."""
        data = super().to_representation(instance)
        data.pop('secret_hash', None)
        return data


class WebhookSecretDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving single webhook secret details (GET)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    secret_exists = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookSecret
        fields = [
            'id', 'endpoint', 'endpoint_name', 'created_at',
            'expires_at', 'is_active', 'secret_exists',
        ]
        read_only_fields = ['id', 'endpoint', 'created_at', 'updated_at']
    
    def get_secret_exists(self, obj):
        """Check if secret exists without exposing it."""
        return bool(obj.secret_hash if hasattr(obj, 'secret_hash') else False)
    
    def to_representation(self, instance):
        """Never expose actual secret in API responses."""
        data = super().to_representation(instance)
        data.pop('secret_hash', None)
        return data


class WebhookSecretListSerializer(serializers.ModelSerializer):
    """Serializer for listing webhook secrets (GET list)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    secret_exists = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookSecret
        fields = [
            'id', 'endpoint', 'endpoint_name', 'created_at',
            'expires_at', 'is_active', 'secret_exists',
        ]
        read_only_fields = ['id', 'endpoint', 'created_at']
    
    def get_secret_exists(self, obj):
        """Check if secret exists without exposing it."""
        return bool(obj.secret_hash if hasattr(obj, 'secret_hash') else False)
    
    def to_representation(self, instance):
        """Never expose actual secret in API responses."""
        data = super().to_representation(instance)
        data.pop('secret_hash', None)
        return data
