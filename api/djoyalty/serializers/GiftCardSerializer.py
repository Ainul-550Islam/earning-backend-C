# api/djoyalty/serializers/GiftCardSerializer.py
from rest_framework import serializers
from ..models.redemption import GiftCard


class GiftCardSerializer(serializers.ModelSerializer):
    issued_to_code = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    used_percent = serializers.SerializerMethodField()

    class Meta:
        model = GiftCard
        fields = [
            'id', 'issued_to', 'issued_to_code',
            'code', 'initial_value', 'remaining_value',
            'currency', 'status', 'is_valid',
            'expires_at', 'is_active',
            'used_at', 'issued_by', 'note',
            'used_percent',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'issued_to_code', 'is_valid', 'used_percent', 'created_at', 'updated_at']

    def get_issued_to_code(self, obj) -> str | None:
        return obj.issued_to.code if obj.issued_to else None

    def get_is_valid(self, obj) -> bool:
        from django.utils import timezone
        if obj.status != 'active':
            return False
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        return True

    def get_used_percent(self, obj) -> float:
        if not obj.initial_value or obj.initial_value == 0:
            return 0.0
        used = obj.initial_value - obj.remaining_value
        return round(float(used / obj.initial_value * 100), 1)

    def validate_initial_balance(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Gift card balance must be greater than 0.')
        return value
