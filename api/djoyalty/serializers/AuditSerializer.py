# api/djoyalty/serializers/AuditSerializer.py
"""
Djoyalty Audit Serializers -- NEW।
AdminAuditLog, CustomerDevice, SystemConfig, MultiCurrencyRate,
ProductCatalogRule had no serializers -- compliance/admin APIs were unreachable।
"""
from rest_framework import serializers
from ..models.audit import (
    AdminAuditLog, CustomerDevice,
    ProductCatalogRule, MultiCurrencyRate, SystemConfig,
)


class AdminAuditLogSerializer(serializers.ModelSerializer):
    """Read-only audit trail -- never writable via API."""
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = AdminAuditLog
        fields = [
            'id', 'tenant', 'customer', 'customer_code',
            'action', 'action_category', 'severity',
            'performed_by', 'performed_by_ip',
            'old_value', 'new_value', 'description',
            'object_type', 'object_id',
            'is_sensitive',
            'timestamp', 'created_at',
        ]
        read_only_fields = fields  # audit log is never mutated via API

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Mask old_value / new_value for sensitive entries
        if instance.is_sensitive:
            data['old_value'] = '***'
            data['new_value'] = '***'
        return data


class CustomerDeviceSerializer(serializers.ModelSerializer):
    """Customer FCM device token -- write on register, read for admin."""
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = CustomerDevice
        fields = [
            'id', 'customer', 'customer_code',
            'device_type', 'device_name', 'device_model',
            'app_version', 'os_version',
            'is_active', 'last_used', 'registered_at',
        ]
        read_only_fields = ['id', 'customer_code', 'last_used', 'registered_at']
        extra_kwargs = {
            'fcm_token': {'write_only': True},  # never returned in responses
        }

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class CustomerDeviceRegisterSerializer(serializers.ModelSerializer):
    """Used for POST /devices/register/ -- customer registers FCM token."""

    class Meta:
        model = CustomerDevice
        fields = ['fcm_token', 'device_type', 'device_name', 'device_model',
                  'app_version', 'os_version']

    def create(self, validated_data):
        customer = self.context['request'].loyalty_customer
        # Update or create -- token may rotate
        obj, _ = CustomerDevice.objects.update_or_create(
            fcm_token=validated_data['fcm_token'],
            defaults={**validated_data, 'customer': customer, 'is_active': True},
        )
        return obj


class SystemConfigSerializer(serializers.ModelSerializer):
    """Per-tenant runtime config -- admin only."""
    typed_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemConfig
        fields = [
            'id', 'tenant', 'key', 'value', 'value_type',
            'description', 'typed_value',
            'is_sensitive', 'updated_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'typed_value', 'created_at', 'updated_at']

    def get_typed_value(self, obj):
        if obj.is_sensitive:
            return '***'
        try:
            return obj.get_typed_value()
        except Exception:
            return obj.value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_sensitive:
            data['value'] = '***'
        return data


class MultiCurrencyRateSerializer(serializers.ModelSerializer):
    """Currency conversion rates -- admin manage, public read."""

    class Meta:
        model = MultiCurrencyRate
        fields = [
            'id', 'tenant', 'currency_code', 'currency_name',
            'currency_symbol', 'earn_rate', 'redeem_rate',
            'base_to_currency_rate',
            'is_active', 'is_base', 'effective_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductCatalogRuleSerializer(serializers.ModelSerializer):
    """SKU / category-level earn overrides."""
    is_currently_valid = serializers.SerializerMethodField()

    class Meta:
        model = ProductCatalogRule
        fields = [
            'id', 'tenant', 'name', 'description',
            'rule_type', 'target_value',
            'earn_type', 'value', 'tier_overrides',
            'priority', 'is_active',
            'valid_from', 'valid_until', 'is_currently_valid',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_currently_valid', 'created_at', 'updated_at']

    def get_is_currently_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return False
        if obj.valid_from and obj.valid_from > now:
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True
