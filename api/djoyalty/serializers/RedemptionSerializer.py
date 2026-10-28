# api/djoyalty/serializers/RedemptionSerializer.py
from rest_framework import serializers
from ..models.redemption import RedemptionRule, RedemptionRequest, RedemptionHistory


class RedemptionRuleSerializer(serializers.ModelSerializer):
    is_currently_valid = serializers.SerializerMethodField()

    class Meta:
        model = RedemptionRule
        fields = [
            'id', 'name', 'description',
            'reward_type', 'points_required', 'cash_value',
            'min_points', 'max_per_user_per_day',
            'min_tier', 'approval_required', 'is_active',
            'valid_from', 'valid_until',
            'image', 'terms', 'is_currently_valid',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_currently_valid', 'created_at', 'updated_at']

    def get_is_currently_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return False
        if obj.valid_from and obj.valid_from > now:
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True


class RedemptionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionHistory
        fields = ['id', 'from_status', 'to_status', 'changed_by', 'note', 'changed_at', 'created_at']
        read_only_fields = ['id', 'created_at']


class RedemptionRequestSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    history = RedemptionHistorySerializer(many=True, read_only=True)

    class Meta:
        model = RedemptionRequest
        fields = [
            'id', 'customer', 'customer_code',
            'rule', 'points_used', 'redemption_type',
            'reward_value', 'status',
            'reviewed_by', 'reviewed_at',
            'fulfilled_at', 'note', 'reference',
            'history',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'customer_code', 'reward_value', 'status',
            'reviewed_by', 'reviewed_at', 'fulfilled_at',
            'reference', 'history', 'created_at', 'updated_at',
        ]

    def validate_points_used(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Points used must be a positive number.')
        return value

    def validate(self, data):
        rule = data.get('rule')
        points_used = data.get('points_used')
        if rule and points_used:
            from decimal import Decimal
            if Decimal(str(points_used)) < Decimal(str(rule.points_required)):
                raise serializers.ValidationError(
                    f'Redemption requires at least {rule.points_required} points. Got {points_used}.'
                )
            if not rule.is_active:
                raise serializers.ValidationError('This redemption rule is no longer active.')
        return data

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
