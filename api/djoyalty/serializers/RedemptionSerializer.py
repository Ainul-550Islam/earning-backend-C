# api/djoyalty/serializers/RedemptionSerializer.py
from rest_framework import serializers
from ..models.redemption import RedemptionRequest, RedemptionRule

class RedemptionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionRule
        fields = ['id', 'name', 'description', 'redemption_type', 'points_required', 'reward_value', 'is_active']

class RedemptionRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    class Meta:
        model = RedemptionRequest
        fields = ['id', 'customer', 'customer_name', 'rule', 'redemption_type', 'points_used', 'reward_value', 'status', 'status_display', 'note', 'reviewed_by', 'reviewed_at', 'created_at']
        read_only_fields = ['status', 'reviewed_by', 'reviewed_at', 'created_at']
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
    def get_status_display(self, obj): return obj.get_status_display()
