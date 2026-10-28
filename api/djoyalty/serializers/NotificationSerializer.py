# api/djoyalty/serializers/NotificationSerializer.py
from rest_framework import serializers
from ..models.notifications import NotificationCenter, NotificationTemplate, NotificationPreference


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'event_type', 'channel', 'title_template',
            'body_template', 'icon', 'priority', 'is_active',
        ]
        read_only_fields = ['id']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'in_app_enabled', 'push_enabled', 'email_enabled', 'sms_enabled',
            'points_notifications', 'tier_notifications', 'badge_notifications',
            'campaign_notifications', 'expiry_notifications', 'offer_notifications',
            'cashout_notifications', 'marketing_notifications', 'max_per_day',
            'quiet_hours_start', 'quiet_hours_end',
        ]
        read_only_fields = ['id']


class NotificationCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCenter
        fields = [
            'id', 'title', 'body', 'icon', 'image_url', 'action_url',
            'notification_type', 'channel', 'priority',
            'is_read', 'read_at', 'created_at', 'metadata',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_title(self, value):
        if not value or not str(value).strip():
            from rest_framework import serializers
            raise serializers.ValidationError('Notification title cannot be empty.')
        return str(value).strip()
