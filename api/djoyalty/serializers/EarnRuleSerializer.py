# api/djoyalty/serializers/EarnRuleSerializer.py
from rest_framework import serializers
from ..models.earn_rules import EarnRule, EarnRuleCondition, EarnRuleTierMultiplier, EarnTransaction, BonusEvent, EarnRuleLog


class EarnRuleConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarnRuleCondition
        fields = ['id', 'condition_type', 'operator', 'value', 'is_active']
        read_only_fields = ['id']


class EarnRuleTierMultiplierSerializer(serializers.ModelSerializer):
    tier_name = serializers.SerializerMethodField()

    class Meta:
        model = EarnRuleTierMultiplier
        fields = ['id', 'tier', 'tier_name', 'multiplier']
        read_only_fields = ['id', 'tier_name']

    def get_tier_name(self, obj) -> str:
        return obj.tier.name if obj.tier else ''


class EarnRuleSerializer(serializers.ModelSerializer):
    conditions = EarnRuleConditionSerializer(many=True, read_only=True)
    tier_multipliers = EarnRuleTierMultiplierSerializer(many=True, read_only=True)
    is_currently_valid = serializers.SerializerMethodField()

    class Meta:
        model = EarnRule
        fields = [
            'id', 'name', 'description',
            'rule_type', 'trigger',
            'points_value', 'multiplier',
            'min_spend', 'max_earn_per_txn', 'max_per_day',
            'applicable_tiers',
            'valid_from', 'valid_until',
            'is_active', 'priority',
            'is_currently_valid',
            'conditions', 'tier_multipliers',
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

    def validate_points_value(self, value):
        from decimal import Decimal
        if Decimal(str(value)) < 0:
            raise serializers.ValidationError('Points value cannot be negative.')
        return value

    def validate_multiplier(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Multiplier must be greater than 0.')
        return value

    def validate(self, data):
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError(
                {'valid_until': 'valid_until must be after valid_from.'}
            )
        points = data.get('points_value', 0)
        multiplier = data.get('multiplier', 1)
        from decimal import Decimal
        if Decimal(str(points)) == 0 and Decimal(str(multiplier)) == 1:
            raise serializers.ValidationError(
                'Earn rule must have either a points_value > 0 or a multiplier != 1.'
            )
        return data


class EarnTransactionSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    rule_name = serializers.SerializerMethodField()

    class Meta:
        model = EarnTransaction
        fields = [
            'id', 'customer', 'customer_code',
            'rule', 'rule_name',
            'spend_amount', 'points_earned',
            'source', 'source_id', 'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'rule_name', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_rule_name(self, obj) -> str:
        return obj.rule.name if obj.rule else ''


class BonusEventSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = BonusEvent
        fields = [
            'id', 'customer', 'customer_code',
            'points', 'reason', 'triggered_by',
            'campaign', 'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class EarnRuleLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = EarnRuleLog
        fields = [
            'id', 'rule', 'rule_name',
            'customer', 'customer_code',
            'triggered_at', 'points_awarded',
            'reason', 'success', 'error_message',
            'created_at',
        ]
        read_only_fields = ['id', 'rule_name', 'customer_code', 'created_at']

    def get_rule_name(self, obj) -> str:
        return obj.rule.name if obj.rule else ''

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
