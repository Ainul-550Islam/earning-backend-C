# api/djoyalty/serializers/VoucherSerializer.py
from rest_framework import serializers
from ..models.redemption import Voucher

class VoucherSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    class Meta:
        model = Voucher
        fields = ['id', 'code', 'customer', 'customer_name', 'voucher_type', 'discount_value', 'status', 'min_order_value', 'max_discount', 'expires_at', 'used_at', 'is_valid', 'created_at']
        read_only_fields = ['code', 'created_at']
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
    def get_is_valid(self, obj):
        from django.utils import timezone
        if obj.status != 'active': return False
        if obj.expires_at and obj.expires_at < timezone.now(): return False
        return True
