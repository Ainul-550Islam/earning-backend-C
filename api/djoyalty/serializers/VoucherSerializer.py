# api/djoyalty/serializers/VoucherSerializer.py
from rest_framework import serializers
from ..models.redemption import Voucher, VoucherRedemption


class VoucherSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Voucher
        fields = [
            'id', 'customer', 'customer_code',
            'code', 'voucher_type', 'discount_value',
            'points_cost', 'status', 'is_valid',
            'expires_at', 'is_used', 'used_at',
            'merchant', 'terms', 'minimum_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_code', 'is_valid', 'is_used', 'used_at', 'created_at', 'updated_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_is_valid(self, obj) -> bool:
        from django.utils import timezone
        if obj.status != 'active':
            return False
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        return True


class VoucherRedemptionSerializer(serializers.ModelSerializer):
    voucher_code = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = VoucherRedemption
        fields = [
            'id', 'voucher', 'voucher_code',
            'customer', 'customer_code',
            'order_reference', 'discount_applied',
            'merchant_ref', 'location', 'used_at',
            'created_at',
        ]
        read_only_fields = ['id', 'voucher_code', 'customer_code', 'created_at']

    def get_voucher_code(self, obj) -> str:
        return obj.voucher.code if obj.voucher else ''

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
