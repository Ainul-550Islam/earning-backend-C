# api/admin_panel/serializers/SiteNotificationSerializer.py
"""SiteNotification serializers — migrated from serializers.py."""
from rest_framework import serializers
from django.utils import timezone
from ..models.core import SiteNotification


class SiteNotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True
    )
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = SiteNotification
        fields = [
            'id', 'title', 'message', 'notification_type', 'notification_type_display',
            'is_active', 'show_on_login', 'start_date', 'end_date',
            'priority', 'created_at', 'updated_at', 'is_current',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_current(self, obj) -> bool:
        return obj.is_current()

    def validate(self, data):
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        return data


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating notifications."""
    class Meta:
        model = SiteNotification
        fields = [
            'title', 'message', 'notification_type',
            'is_active', 'show_on_login', 'start_date', 'end_date', 'priority',
        ]

    def validate(self, data):
        start = data.get('start_date')
        end = data.get('end_date')
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        return data