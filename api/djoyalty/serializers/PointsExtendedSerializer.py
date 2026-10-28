# api/djoyalty/serializers/PointsExtendedSerializer.py
"""
Djoyalty Points Extended Serializers -- NEW।
PointsExpiry, PointsAlert -- had no serializers।
These are critical: customers need to know their expiring points।
"""
from rest_framework import serializers
from ..models.points import PointsExpiry, PointsAdjustment, PointsRate


class PointsExpirySerializer(serializers.ModelSerializer):
    """
    Shows customer their upcoming / past point expiry events।
    Critical for engagement -- 'Your 500 points expire in 7 days!'
    """
    customer_code = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PointsExpiry
        fields = [
            'id', 'customer', 'customer_code',
            'points', 'expires_at',
            'is_processed', 'processed_at',
            'days_until_expiry', 'is_expired',
            'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_days_until_expiry(self, obj) -> int:
        from django.utils import timezone
        if obj.expires_at and not obj.is_processed:
            delta = obj.expires_at.date() - timezone.now().date()
            return delta.days
        return 0

    def get_is_expired(self, obj) -> bool:
        from django.utils import timezone
        if obj.is_processed:
            return True
        if obj.expires_at and obj.expires_at < timezone.now():
            return True
        return False


class PointsExpiryWarningSerializer(serializers.ModelSerializer):
    """
    Lightweight version for notification payload।
    Used by send_expiry_warnings_task।
    """
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = PointsExpiry
        fields = ['id', 'points', 'expires_at', 'days_remaining']

    def get_days_remaining(self, obj) -> int:
        from django.utils import timezone
        if obj.expires_at:
            delta = obj.expires_at.date() - timezone.now().date()
            return max(delta.days, 0)
        return 0


class PointsAdjustmentDetailSerializer(serializers.ModelSerializer):
    """
    Full points adjustment record -- for admin audit + customer history।
    PointsAdjustment had a serializer in LedgerSerializer but only partial fields।
    """
    customer_code = serializers.SerializerMethodField()
    adjusted_by_display = serializers.SerializerMethodField()

    class Meta:
        model = PointsAdjustment
        fields = [
            'id', 'customer', 'customer_code',
            'adjustment_type', 'points',
            'reason', 'note',
            'adjusted_by', 'adjusted_by_display',
            'balance_before', 'balance_after',
            'reference',
            'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_adjusted_by_display(self, obj) -> str:
        return str(obj.adjusted_by) if obj.adjusted_by else 'System'


class PointsAdjustmentCreateSerializer(serializers.Serializer):
    """
    Admin creates a points adjustment।
    POST /customers/{id}/points/adjust/
    """
    points      = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason      = serializers.ChoiceField(choices=[
        'correction', 'goodwill', 'promotion', 'fraud_reversal',
        'migration', 'complaint_resolution', 'other',
    ])
    note        = serializers.CharField(max_length=500, required=False, allow_blank=True)
    reference   = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_points(self, value):
        from decimal import Decimal
        if value == Decimal('0'):
            raise serializers.ValidationError('Adjustment cannot be zero.')
        return value


class PointsRateDetailSerializer(serializers.ModelSerializer):
    """
    Full points rate info -- base earn rate configuration।
    """
    class Meta:
        model = PointsRate
        fields = [
            'id', 'tenant',
            'base_earn_rate',
            'currency',
            'is_active',
            'effective_from', 'effective_until',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
