# api/djoyalty/serializers/InsightSerializer.py
from rest_framework import serializers
from ..models.advanced import LoyaltyInsight, PointsAbuseLog


class LoyaltyInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyInsight
        fields = [
            'id', 'tenant', 'report_date', 'period',
            'total_customers', 'active_customers', 'new_customers',
            'total_points_issued', 'total_points_redeemed', 'total_points_expired',
            'total_points_outstanding',
            'total_transactions', 'total_revenue',
            'redemption_rate', 'liability_amount',
            'generated_at', 'created_at',
        ]
        read_only_fields = ['id', 'generated_at', 'created_at']


class FraudLogSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsAbuseLog
        fields = [
            'id', 'customer', 'customer_code',
            'rule', 'risk_level', 'action_taken',
            'description', 'points_reversed',
            'detected_at', 'is_resolved',
            'resolved_at', 'resolved_by', 'resolution_note',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'detected_at', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
