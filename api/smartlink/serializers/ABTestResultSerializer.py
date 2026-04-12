from rest_framework import serializers
from ..models import ABTestResult


class ABTestResultSerializer(serializers.ModelSerializer):
    winner_name = serializers.CharField(source='winner_version.name', read_only=True)
    control_name = serializers.CharField(source='control_version.name', read_only=True)
    is_significant = serializers.SerializerMethodField()

    class Meta:
        model = ABTestResult
        fields = [
            'id', 'smartlink', 'status',
            'winner_version', 'winner_name',
            'control_version', 'control_name',
            'confidence_level', 'uplift_percent',
            'control_cr', 'winner_cr',
            'control_clicks', 'winner_clicks',
            'p_value', 'is_significant',
            'started_at', 'completed_at', 'auto_applied',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'confidence_level', 'uplift_percent',
            'control_cr', 'winner_cr', 'control_clicks', 'winner_clicks',
            'p_value', 'started_at', 'completed_at', 'created_at', 'updated_at',
        ]

    def get_is_significant(self, obj):
        return obj.is_significant
