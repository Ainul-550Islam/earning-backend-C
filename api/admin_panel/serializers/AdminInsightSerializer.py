# api/admin_panel/serializers/AdminInsightSerializer.py
"""AdminInsight serializer."""
from rest_framework import serializers
from ..models.reports import AdminInsight


class AdminInsightSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    priority_color = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = AdminInsight
        fields = [
            'id', 'insight_id', 'type', 'type_display',
            'title', 'body', 'data', 'priority', 'priority_display', 'priority_color',
            'is_read', 'is_dismissed',
            'action_url', 'action_label',
            'expires_at', 'is_expired',
            'generated_by_task', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'insight_id', 'generated_by_task',
            'created_at', 'updated_at', 'is_expired',
            'priority_color', 'type_display', 'priority_display',
        ]