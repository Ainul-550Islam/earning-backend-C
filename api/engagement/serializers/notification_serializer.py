# engagement/serializers/notification_serializer.py
from rest_framework import serializers
from ..models.notification import Notification, UserPushToken


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = [
            "id", "type", "title", "body", "icon", "data",
            "is_read", "read_at", "push_sent", "created_at",
        ]
        read_only_fields = fields


class UserPushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserPushToken
        fields = ["id", "platform", "token", "device_id", "is_active"]
        extra_kwargs = {"token": {"write_only": True}}
