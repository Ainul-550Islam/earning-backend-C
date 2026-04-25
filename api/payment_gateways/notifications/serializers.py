# api/payment_gateways/notifications/serializers.py
from rest_framework import serializers
from .models import InAppNotification, DeviceToken

class InAppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = InAppNotification
        fields = ['id','notification_type','title','message','is_read','read_at','metadata','created_at']
        read_only_fields = ['id','created_at','read_at']

class InAppNotificationListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = InAppNotification
        fields = ['id','notification_type','title','is_read','created_at']

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviceToken
        fields = ['id','token','platform','is_active','created_at']
        read_only_fields = ['id','created_at']

    def validate_token(self, value):
        request = self.context.get('request')
        if not request:
            return value
        # Ensure token is unique per user
        qs = DeviceToken.objects.filter(token=value)
        instance = self.instance
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            # Update existing token to this user instead of raising
            qs.update(user=request.user, is_active=True)
        return value
