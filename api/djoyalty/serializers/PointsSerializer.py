# api/djoyalty/serializers/PointsSerializer.py
from rest_framework import serializers
from ..models.points import LoyaltyPoints, PointsTransfer, PointsConversion, PointsReservation


class LoyaltyPointsSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyPoints
        fields = [
            'id', 'customer', 'customer_code',
            'balance', 'available_balance',
            'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired',
            'pending_balance', 'frozen_balance',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_code', 'available_balance', 'created_at', 'updated_at']

    def get_available_balance(self, obj) -> str:
        return str(obj.available_balance)

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class PointsTransferSerializer(serializers.ModelSerializer):
    from_customer_code = serializers.SerializerMethodField()
    to_customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsTransfer
        fields = [
            'id', 'from_customer', 'from_customer_code',
            'to_customer', 'to_customer_code',
            'points', 'fee', 'status', 'note', 'reference',
            'created_at', 'completed_at',
        ]
        read_only_fields = ['id', 'status', 'reference', 'from_customer_code', 'to_customer_code', 'created_at', 'completed_at']

    def get_from_customer_code(self, obj) -> str:
        return obj.from_customer.code if obj.from_customer else ''

    def get_to_customer_code(self, obj) -> str:
        return obj.to_customer.code if obj.to_customer else ''

    def validate_points(self, value):
        from decimal import Decimal
        if value is None or Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Points must be a positive number.')
        if Decimal(str(value)) < Decimal('1'):
            raise serializers.ValidationError('Minimum transfer is 1 point.')
        return value

    def validate(self, data):
        from_c = data.get('from_customer')
        to_c = data.get('to_customer')
        if from_c and to_c and from_c == to_c:
            raise serializers.ValidationError('Cannot transfer points to yourself.')
        return data


class PointsConversionSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsConversion
        fields = [
            'id', 'customer', 'customer_code',
            'points_amount', 'cash_amount', 'rate',
            'conversion_type', 'status', 'reference',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'created_at']

    def validate_points_amount(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Points amount must be positive.')
        return value

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class PointsReservationSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsReservation
        fields = [
            'id', 'customer', 'customer_code',
            'points', 'reason', 'reference',
            'expires_at', 'is_released', 'is_confirmed',
            'released_at', 'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'is_released', 'is_confirmed', 'released_at', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
