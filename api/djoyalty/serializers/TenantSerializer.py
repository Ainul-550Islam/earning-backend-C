# api/djoyalty/serializers/TenantSerializer.py
"""
Djoyalty Tenant Serializer -- NEW।
Tenant model had no serializer -- SaaS tenant management API was unreachable।
"""
from rest_framework import serializers
from ..models.core import Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Public tenant info -- no api_key exposed."""
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'is_active', 'plan',
            'customer_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_count', 'created_at', 'updated_at']

    def get_customer_count(self, obj) -> int:
        return obj.customers.filter(is_active=True).count()


class TenantAdminSerializer(serializers.ModelSerializer):
    """Admin-only -- includes api_key, full settings।"""
    customer_count = serializers.SerializerMethodField()
    active_earn_rules = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'is_active', 'plan',
            'api_key', 'settings',
            'customer_count', 'active_earn_rules',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'api_key', 'customer_count', 'active_earn_rules',
                            'created_at', 'updated_at']

    def get_customer_count(self, obj) -> int:
        return obj.customers.filter(is_active=True).count()

    def get_active_earn_rules(self, obj) -> int:
        return obj.earn_rules.filter(is_active=True).count()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Create new tenant -- generates api_key automatically."""

    class Meta:
        model = Tenant
        fields = ['name', 'slug', 'plan', 'settings']

    def create(self, validated_data):
        import secrets
        tenant = Tenant(**validated_data)
        tenant.api_key = secrets.token_urlsafe(32)
        tenant.save()
        return tenant
