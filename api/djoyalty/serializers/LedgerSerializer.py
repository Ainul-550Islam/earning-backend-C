# api/djoyalty/serializers/LedgerSerializer.py
from rest_framework import serializers
from ..models.points import PointsLedger, PointsAdjustment, PointsRate


class LedgerSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = PointsLedger
        fields = [
            'id', 'customer', 'customer_code',
            'txn_type', 'source', 'points', 'remaining_points',
            'balance_after', 'description', 'reference_id',
            'expires_at', 'days_until_expiry', 'is_reversed',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'days_until_expiry', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_days_until_expiry(self, obj) -> int | None:
        if not obj.expires_at:
            return None
        from ..utils import days_until
        return days_until(obj.expires_at)


class PointsAdjustmentSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsAdjustment
        fields = [
            'id', 'customer', 'customer_code',
            'points', 'reason', 'adjusted_by', 'admin_note',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class PointsRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointsRate
        fields = [
            'id', 'tenant', 'earn_rate', 'point_value',
            'currency', 'effective_date', 'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
