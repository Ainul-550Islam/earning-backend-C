# api/djoyalty/serializers/GiftCardSerializer.py
"""Gift card serializer।"""
from rest_framework import serializers
from django.utils import timezone
from ..models.redemption import GiftCard


class GiftCardSerializer(serializers.ModelSerializer):
    """Gift card serializer with computed fields।"""
    issued_to_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    used_amount = serializers.SerializerMethodField()

    class Meta:
        model = GiftCard
        fields = [
            'id', 'code', 'initial_value', 'remaining_value',
            'used_amount', 'status', 'issued_to', 'issued_to_name',
            'expires_at', 'days_until_expiry', 'is_valid',
            'created_at', 'used_at',
        ]
        read_only_fields = ['code', 'created_at', 'remaining_value', 'used_at']

    def get_issued_to_name(self, obj):
        """Issued customer name।"""
        return str(obj.issued_to) if obj.issued_to else 'Unassigned'

    def get_is_valid(self, obj):
        """Gift card usable কিনা।"""
        if obj.status != 'active':
            return False
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        if obj.remaining_value <= 0:
            return False
        return True

    def get_days_until_expiry(self, obj):
        """Expiry পর্যন্ত কত দিন বাকি।"""
        if not obj.expires_at:
            return None
        now = timezone.now()
        if obj.expires_at <= now:
            return 0
        return (obj.expires_at - now).days

    def get_used_amount(self, obj):
        """Used amount = initial - remaining।"""
        return str(obj.initial_value - obj.remaining_value)


class GiftCardMiniSerializer(serializers.ModelSerializer):
    """Minimal gift card info — list display এর জন্য।"""
    class Meta:
        model = GiftCard
        fields = ['id', 'code', 'remaining_value', 'status', 'expires_at']
