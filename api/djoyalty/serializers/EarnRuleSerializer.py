# api/djoyalty/serializers/EarnRuleSerializer.py
from rest_framework import serializers
from ..models.earn_rules import EarnRule, BonusEvent

class EarnRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarnRule
        fields = ['id', 'name', 'description', 'rule_type', 'trigger', 'points_value', 'multiplier', 'min_spend', 'max_earn_per_txn', 'max_earn_per_day', 'applicable_tiers', 'is_active', 'valid_from', 'valid_until', 'priority', 'created_at']
        read_only_fields = ['created_at']

class BonusEventSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    class Meta:
        model = BonusEvent
        fields = ['id', 'customer', 'customer_name', 'points', 'reason', 'triggered_by', 'created_at']
        read_only_fields = ['created_at']
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
