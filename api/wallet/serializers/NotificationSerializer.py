# api/wallet/serializers/NotificationSerializer.py
from rest_framework import serializers

class WalletNotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    class Meta:
        from ..models.notification import WalletNotification
        model  = WalletNotification
        fields = ["id","event_type","title","message","data","is_read","read_at","created_at","time_ago"]
        read_only_fields = fields

    def get_time_ago(self, obj):
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now()) + " ago"
