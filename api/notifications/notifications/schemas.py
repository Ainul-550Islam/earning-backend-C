# earning_backend/api/notifications/schemas.py
"""
Schemas — OpenAPI/drf-spectacular schema definitions and request/response schemas.
"""
from rest_framework import serializers


class SendNotificationSchema(serializers.Serializer):
    user_id       = serializers.IntegerField(help_text='Target user ID')
    title         = serializers.CharField(max_length=255)
    message       = serializers.CharField(max_length=2000)
    notification_type = serializers.CharField(default='announcement')
    channel       = serializers.ChoiceField(choices=['in_app','push','email','sms','telegram','whatsapp','browser','all'], default='in_app')
    priority      = serializers.ChoiceField(choices=['lowest','low','medium','high','urgent','critical'], default='medium')
    action_url    = serializers.URLField(required=False, allow_blank=True)
    metadata      = serializers.DictField(required=False, default=dict)
    scheduled_at  = serializers.DateTimeField(required=False, allow_null=True)


class BulkSendSchema(serializers.Serializer):
    user_ids      = serializers.ListField(child=serializers.IntegerField(), max_length=100000)
    title         = serializers.CharField(max_length=255)
    message       = serializers.CharField(max_length=2000)
    notification_type = serializers.CharField(default='announcement')
    channel       = serializers.ChoiceField(choices=['in_app','push','email','sms','all'], default='in_app')
    priority      = serializers.ChoiceField(choices=['lowest','low','medium','high','urgent','critical'], default='medium')


class MarkReadSchema(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class NotificationResponseSchema(serializers.Serializer):
    id         = serializers.IntegerField(read_only=True)
    title      = serializers.CharField(read_only=True)
    message    = serializers.CharField(read_only=True)
    channel    = serializers.CharField(read_only=True)
    priority   = serializers.CharField(read_only=True)
    is_read    = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class UnreadCountResponseSchema(serializers.Serializer):
    unread_count = serializers.IntegerField(read_only=True)


class DeliveryStatsResponseSchema(serializers.Serializer):
    total     = serializers.IntegerField(read_only=True)
    sent      = serializers.IntegerField(read_only=True)
    delivered = serializers.IntegerField(read_only=True)
    failed    = serializers.IntegerField(read_only=True)
    read      = serializers.IntegerField(read_only=True)


class RegisterDeviceSchema(serializers.Serializer):
    device_type        = serializers.ChoiceField(choices=['android','ios','web','desktop','other'])
    fcm_token          = serializers.CharField(required=False, allow_blank=True)
    apns_token         = serializers.CharField(required=False, allow_blank=True)
    web_push_subscription = serializers.DictField(required=False, default=dict)
    device_name        = serializers.CharField(required=False, allow_blank=True, max_length=150)
    app_version        = serializers.CharField(required=False, allow_blank=True, max_length=50)


class OptOutSchema(serializers.Serializer):
    channel = serializers.ChoiceField(choices=['in_app','push','email','sms','telegram','whatsapp','browser','all'])
    reason  = serializers.ChoiceField(choices=['too_many','not_relevant','privacy','spam','user_request','other'], default='user_request')
    notes   = serializers.CharField(required=False, allow_blank=True)


class CampaignCreateSchema(serializers.Serializer):
    name             = serializers.CharField(max_length=255)
    description      = serializers.CharField(required=False, allow_blank=True)
    template_id      = serializers.IntegerField()
    segment_conditions = serializers.DictField(default=dict)
    send_at          = serializers.DateTimeField(required=False, allow_null=True)
    context          = serializers.DictField(required=False, default=dict)


class HealthCheckResponseSchema(serializers.Serializer):
    overall  = serializers.CharField(read_only=True)
    services = serializers.DictField(read_only=True)
    checked_at = serializers.DateTimeField(read_only=True)


class JourneyEnrollSchema(serializers.Serializer):
    journey_id = serializers.CharField()
    context    = serializers.DictField(required=False, default=dict)
