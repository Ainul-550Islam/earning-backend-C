from ..models.notifications import NotificationCenter
# api/djoyalty/serializers/NotificationExtendedSerializer.py
"""
Djoyalty Notification Extended Serializers -- NEW।
Extends existing NotificationSerializer with:
  - LoyaltyNotificationSerializer  (LoyaltyNotification model -- had no serializer)
  - PointsAlertSerializer          (PointsAlert model -- had no serializer)
  - NotificationCenterListSerializer (lightweight list view)
  - NotificationBulkReadSerializer  (mark multiple as read)
  - NotificationInboxSummarySerializer (badge count + unread list)
"""
from rest_framework import serializers
from ..models.advanced import (
    LoyaltyNotification, PointsAlert,
)


class LoyaltyNotificationSerializer(serializers.ModelSerializer):
    """
    LoyaltyNotification -- operational notification record।
    (Different from NotificationCenter which is the inbox item।)
    """
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyNotification
        fields = [
            'id', 'customer', 'customer_code',
            'notification_type', 'channel',
            'title', 'body',
            'status', 'sent_at', 'delivered_at',
            'error_message',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class PointsAlertSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = PointsAlert
        fields = [
            'id', 'customer', 'customer_code',
            'alert_type', 'threshold', 'last_triggered_at', 'is_active',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''  


class NotificationCenterListSerializer(serializers.ModelSerializer):
    """Lightweight list view -- used in inbox listing (faster)."""

    class Meta:
        model = NotificationCenter
        fields = [
            'id', 'title', 'body', 'icon',
            'notification_type', 'priority',
            'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = fields


class NotificationCenterDetailSerializer(serializers.ModelSerializer):
    """Full detail -- includes action_url, image, metadata."""

    class Meta:
        model = NotificationCenter
        fields = [
            'id', 'title', 'body', 'icon', 'image_url', 'action_url',
            'notification_type', 'channel', 'priority',
            'is_read', 'read_at',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'notification_type', 'channel', 'priority',
                            'read_at', 'metadata', 'created_at']


class NotificationBulkReadSerializer(serializers.Serializer):
    """POST /notifications/mark-read/ -- mark multiple notifications as read."""
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100,
        help_text='List of notification IDs to mark as read.',
    )
    mark_all = serializers.BooleanField(
        default=False,
        help_text='If True, ignores notification_ids and marks ALL as read.',
    )


class NotificationInboxSummarySerializer(serializers.Serializer):
    """
    GET /notifications/inbox-summary/
    Returns unread count + first 5 notifications for badge/preview।
    """
    unread_count   = serializers.IntegerField()
    total_count    = serializers.IntegerField()
    notifications  = NotificationCenterListSerializer(many=True)
