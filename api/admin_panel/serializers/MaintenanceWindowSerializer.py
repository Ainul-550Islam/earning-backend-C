# api/admin_panel/serializers/MaintenanceWindowSerializer.py
"""MaintenanceWindow serializer."""
from rest_framework import serializers
from ..models.config import MaintenanceWindow


class MaintenanceWindowSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    maintenance_type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = MaintenanceWindow
        fields = [
            'id', 'title', 'message', 'internal_note',
            'maintenance_type', 'maintenance_type_display',
            'start_at', 'end_at', 'is_active',
            'notify_users', 'notify_before_minutes',
            'created_by', 'created_by_username',
            'is_currently_active', 'duration_minutes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'is_currently_active', 'duration_minutes', 'created_at', 'updated_at']

    def validate(self, data):
        start = data.get('start_at', getattr(self.instance, 'start_at', None))
        end = data.get('end_at', getattr(self.instance, 'end_at', None))
        if start and end and end <= start:
            raise serializers.ValidationError({'end_at': 'End time must be after start time.'})
        return data