# api/djoyalty/serializers/InsightSerializer.py
from rest_framework import serializers
from ..models.advanced import LoyaltyInsight, PointsAbuseLog

class LoyaltyInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyInsight
        fields = ['id', 'report_date', 'period', 'total_customers', 'active_customers', 'new_customers', 'total_points_issued', 'total_points_redeemed', 'total_points_expired', 'total_transactions', 'total_revenue', 'tier_distribution', 'top_earners', 'created_at']

class FraudLogSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    class Meta:
        model = PointsAbuseLog
        fields = ['id', 'customer', 'customer_name', 'risk_level', 'action_taken', 'description', 'is_resolved', 'resolved_by', 'resolved_at', 'created_at']
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
