# api/djoyalty/serializers/PublicAPISerializer.py
"""
Public white-label API serializers।
Partner merchant এর API client এর জন্য।
"""
from rest_framework import serializers


class PublicBalanceSerializer(serializers.Serializer):
    """Customer balance response for public API।"""
    customer_code = serializers.CharField(read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tier = serializers.CharField(read_only=True)


class PublicEarnRequestSerializer(serializers.Serializer):
    """Earn points request from partner।"""
    customer_code = serializers.CharField(max_length=32)
    spend_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reference = serializers.CharField(max_length=128, required=False, allow_blank=True)


class PublicEarnResponseSerializer(serializers.Serializer):
    """Earn points response to partner।"""
    customer_code = serializers.CharField(read_only=True)
    points_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    new_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)


class PublicRedeemRequestSerializer(serializers.Serializer):
    """Redeem points request from partner।"""
    customer_code = serializers.CharField(max_length=32)
    points = serializers.DecimalField(max_digits=12, decimal_places=2)
    redemption_type = serializers.ChoiceField(
        choices=['voucher', 'cashback', 'product', 'giftcard', 'donation'],
        default='cashback',
    )
    reference = serializers.CharField(max_length=128, required=False, allow_blank=True)


class PublicCustomerInfoSerializer(serializers.Serializer):
    """Minimal customer info for public API।"""
    customer_code = serializers.CharField(read_only=True)
    tier = serializers.CharField(read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
