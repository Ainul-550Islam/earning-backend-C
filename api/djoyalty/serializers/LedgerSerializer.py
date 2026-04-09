# api/djoyalty/serializers/LedgerSerializer.py
from rest_framework import serializers
from ..models.points import PointsLedger

class LedgerSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = PointsLedger
        fields = ['id', 'customer', 'customer_code', 'txn_type', 'source', 'points', 'remaining_points', 'balance_after', 'description', 'reference_id', 'expires_at', 'days_until_expiry', 'created_at']
        read_only_fields = ['created_at']

    def get_customer_code(self, obj):
        return obj.customer.code if obj.customer else ''

    def get_days_until_expiry(self, obj):
        from ..utils import days_until_expiry
        return days_until_expiry(obj.expires_at)
