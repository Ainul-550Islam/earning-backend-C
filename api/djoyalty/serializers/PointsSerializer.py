# api/djoyalty/serializers/PointsSerializer.py
from rest_framework import serializers
from ..models.points import LoyaltyPoints, PointsTransfer

class LoyaltyPointsSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyPoints
        fields = ['id', 'customer', 'customer_name', 'balance', 'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired', 'updated_at']
        read_only_fields = ['balance', 'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired', 'updated_at']

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else ''


class PointsTransferSerializer(serializers.ModelSerializer):
    from_customer_name = serializers.SerializerMethodField()
    to_customer_name = serializers.SerializerMethodField()

    class Meta:
        model = PointsTransfer
        fields = ['id', 'from_customer', 'from_customer_name', 'to_customer', 'to_customer_name', 'points', 'status', 'note', 'created_at', 'completed_at']
        read_only_fields = ['status', 'created_at', 'completed_at']

    def get_from_customer_name(self, obj):
        return str(obj.from_customer) if obj.from_customer else ''

    def get_to_customer_name(self, obj):
        return str(obj.to_customer) if obj.to_customer else ''
