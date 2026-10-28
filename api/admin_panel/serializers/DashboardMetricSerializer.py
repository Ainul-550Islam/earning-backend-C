# api/admin_panel/serializers/DashboardMetricSerializer.py
"""DashboardMetric serializer."""
from rest_framework import serializers
from ..models.dashboard import DashboardMetric


class DashboardMetricSerializer(serializers.ModelSerializer):
    change_percentage = serializers.FloatField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)

    class Meta:
        model = DashboardMetric
        fields = [
            'id', 'metric_key', 'label', 'value', 'previous_value',
            'change_percentage', 'unit', 'period', 'period_display',
            'metadata', 'cached_at', 'is_stale',
        ]
        read_only_fields = ['id', 'cached_at', 'change_percentage', 'is_stale']