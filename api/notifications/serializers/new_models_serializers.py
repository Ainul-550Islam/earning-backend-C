# earning_backend/api/notifications/serializers/new_models_serializers.py
"""
Serializers for all 17 new split models.
"""
from rest_framework import serializers
from django.utils import timezone


class PushDeviceSerializer(serializers.ModelSerializer):
    delivery_rate = serializers.SerializerMethodField()

    def get_delivery_rate(self, obj):
        return obj.get_delivery_rate()

    class Meta:
        from api.notifications.models.channel import PushDevice
        model = PushDevice
        fields = [
            'id', 'user', 'device_type', 'fcm_token', 'apns_token',
            'web_push_subscription', 'device_name', 'device_model',
            'os_version', 'app_version', 'is_active', 'last_used',
            'delivery_rate', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'delivery_rate', 'created_at', 'updated_at']
        extra_kwargs = {
            'fcm_token': {'write_only': True},
            'apns_token': {'write_only': True},
            'web_push_subscription': {'write_only': True},
        }


class RegisterPushDeviceSerializer(serializers.Serializer):
    device_type = serializers.ChoiceField(choices=['android', 'ios', 'web', 'desktop', 'other'])
    fcm_token = serializers.CharField(required=False, allow_blank=True)
    apns_token = serializers.CharField(required=False, allow_blank=True)
    web_push_subscription = serializers.DictField(required=False, default=dict)
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    device_model = serializers.CharField(required=False, allow_blank=True, max_length=150)
    os_version = serializers.CharField(required=False, allow_blank=True, max_length=50)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=50)

    def validate(self, data):
        dt = data.get('device_type', '')
        if dt == 'android' and not data.get('fcm_token'):
            raise serializers.ValidationError('fcm_token required for Android devices.')
        if dt == 'ios' and not data.get('apns_token'):
            raise serializers.ValidationError('apns_token required for iOS devices.')
        if dt == 'web' and not data.get('web_push_subscription'):
            raise serializers.ValidationError('web_push_subscription required for web devices.')
        return data


class PushDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.channel import PushDeliveryLog
        model = PushDeliveryLog
        fields = [
            'id', 'device', 'notification', 'status', 'provider',
            'provider_message_id', 'error_code', 'error_message',
            'delivered_at', 'created_at',
        ]
        read_only_fields = fields


class EmailDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.channel import EmailDeliveryLog
        model = EmailDeliveryLog
        fields = [
            'id', 'notification', 'recipient', 'provider', 'message_id',
            'status', 'opened_at', 'open_count', 'clicked_at', 'click_count',
            'error_message', 'created_at',
        ]
        read_only_fields = fields


class SMSDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.channel import SMSDeliveryLog
        model = SMSDeliveryLog
        fields = [
            'id', 'notification', 'phone', 'gateway', 'provider_sid',
            'status', 'cost', 'cost_currency', 'error_code', 'error_message',
            'delivered_at', 'created_at',
        ]
        read_only_fields = fields


class InAppMessageSerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()

    def get_is_expired(self, obj):
        return obj.is_expired()

    class Meta:
        from api.notifications.models.channel import InAppMessage
        model = InAppMessage
        fields = [
            'id', 'user', 'notification', 'message_type', 'title', 'body',
            'image_url', 'icon_url', 'cta_text', 'cta_url', 'extra_data',
            'is_read', 'read_at', 'is_dismissed', 'dismissed_at',
            'expires_at', 'display_priority', 'is_expired', 'created_at',
        ]
        read_only_fields = [
            'id', 'user', 'is_read', 'read_at', 'is_dismissed',
            'dismissed_at', 'is_expired', 'created_at',
        ]


class NotificationScheduleSerializer(serializers.ModelSerializer):
    is_due = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    def get_is_due(self, obj):
        return obj.is_due()

    def get_is_overdue(self, obj):
        return obj.is_overdue()

    class Meta:
        from api.notifications.models.schedule import NotificationSchedule
        model = NotificationSchedule
        fields = [
            'id', 'notification', 'send_at', 'timezone', 'status',
            'sent_at', 'failure_reason', 'created_by', 'is_due',
            'is_overdue', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'sent_at', 'failure_reason', 'is_due', 'is_overdue', 'created_at', 'updated_at']

    def validate_send_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('send_at must be in the future.')
        return value


class CreateNotificationScheduleSerializer(serializers.Serializer):
    notification_id = serializers.IntegerField()
    send_at = serializers.DateTimeField()
    timezone = serializers.CharField(default='UTC', max_length=64)

    def validate_send_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('send_at must be in the future.')
        return value


class NotificationBatchSerializer(serializers.ModelSerializer):
    progress_pct = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()

    def get_progress_pct(self, obj):
        return obj.progress_pct

    def get_success_rate(self, obj):
        return obj.success_rate

    class Meta:
        from api.notifications.models.schedule import NotificationBatch
        model = NotificationBatch
        fields = [
            'id', 'name', 'description', 'template', 'segment', 'status',
            'total_count', 'sent_count', 'delivered_count', 'failed_count',
            'skipped_count', 'progress_pct', 'success_rate', 'context',
            'started_at', 'completed_at', 'celery_task_id', 'created_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'total_count', 'sent_count', 'delivered_count',
            'failed_count', 'skipped_count', 'progress_pct', 'success_rate',
            'started_at', 'completed_at', 'celery_task_id', 'created_at', 'updated_at',
        ]


class CreateNotificationBatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    template_id = serializers.IntegerField()
    segment_conditions = serializers.DictField(default=dict)
    context = serializers.DictField(required=False, default=dict)


class NotificationQueueSerializer(serializers.ModelSerializer):
    is_ready = serializers.SerializerMethodField()

    def get_is_ready(self, obj):
        return obj.is_ready()

    class Meta:
        from api.notifications.models.schedule import NotificationQueue
        model = NotificationQueue
        fields = [
            'id', 'notification', 'priority', 'scheduled_at', 'status',
            'attempts', 'last_attempt', 'celery_task_id', 'is_ready',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'attempts', 'last_attempt',
            'celery_task_id', 'is_ready', 'created_at', 'updated_at',
        ]


class NotificationRetrySerializer(serializers.ModelSerializer):
    is_due = serializers.SerializerMethodField()
    has_exceeded_max = serializers.SerializerMethodField()

    def get_is_due(self, obj):
        return obj.is_due()

    def get_has_exceeded_max(self, obj):
        return obj.has_exceeded_max()

    class Meta:
        from api.notifications.models.schedule import NotificationRetry
        model = NotificationRetry
        fields = [
            'id', 'notification', 'attempt_number', 'max_attempts', 'status',
            'error_from_previous', 'error', 'retry_at', 'attempted_at',
            'is_due', 'has_exceeded_max', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class CampaignSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.campaign import CampaignSegment
        model = CampaignSegment
        fields = [
            'id', 'campaign', 'name', 'description', 'segment_type',
            'conditions', 'estimated_size', 'last_evaluated_at',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'estimated_size', 'last_evaluated_at', 'created_at', 'updated_at']


class NewNotificationCampaignSerializer(serializers.ModelSerializer):
    progress_pct = serializers.SerializerMethodField()
    segment_data = CampaignSegmentSerializer(source='segment', read_only=True)

    def get_progress_pct(self, obj):
        return obj.progress_pct

    class Meta:
        from api.notifications.models.campaign import NotificationCampaign
        model = NotificationCampaign
        fields = [
            'id', 'name', 'description', 'template', 'segment', 'segment_data',
            'status', 'send_at', 'total_users', 'sent_count', 'failed_count',
            'context', 'started_at', 'completed_at', 'celery_task_id',
            'created_by', 'progress_pct', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'total_users', 'sent_count', 'failed_count',
            'started_at', 'completed_at', 'celery_task_id', 'progress_pct',
            'created_at', 'updated_at',
        ]


class CreateNewCampaignSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    template_id = serializers.IntegerField()
    segment_conditions = serializers.DictField(default=dict)
    send_at = serializers.DateTimeField(required=False, allow_null=True)
    context = serializers.DictField(required=False, default=dict)


class CampaignABTestSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.campaign import CampaignABTest
        model = CampaignABTest
        fields = [
            'id', 'campaign', 'variant_a', 'variant_b', 'split_pct',
            'winning_metric', 'winner', 'variant_a_stats', 'variant_b_stats',
            'winner_declared_at', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'winner', 'variant_a_stats', 'variant_b_stats',
            'winner_declared_at', 'created_at', 'updated_at',
        ]


class CampaignResultSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.campaign import CampaignResult
        model = CampaignResult
        fields = [
            'id', 'campaign', 'sent', 'delivered', 'failed', 'opened',
            'clicked', 'converted', 'unsubscribed', 'delivery_rate',
            'open_rate', 'click_rate', 'conversion_rate', 'total_cost',
            'cost_currency', 'calculated_at',
        ]
        read_only_fields = fields


class NotificationInsightSerializer(serializers.ModelSerializer):
    delivery_rate = serializers.SerializerMethodField()
    open_rate = serializers.SerializerMethodField()
    click_rate = serializers.SerializerMethodField()

    def get_delivery_rate(self, obj):
        return obj.delivery_rate

    def get_open_rate(self, obj):
        return obj.open_rate

    def get_click_rate(self, obj):
        return obj.click_rate

    class Meta:
        from api.notifications.models.analytics import NotificationInsight
        model = NotificationInsight
        fields = [
            'id', 'date', 'channel', 'sent', 'delivered', 'failed',
            'opened', 'clicked', 'unsubscribed', 'unique_users_reached',
            'delivery_rate', 'open_rate', 'click_rate', 'total_cost',
            'cost_currency', 'breakdown', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class DeliveryRateSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.analytics import DeliveryRate
        model = DeliveryRate
        fields = [
            'id', 'date', 'channel', 'delivery_pct', 'open_pct',
            'click_pct', 'sample_size', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class OptOutTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        from api.notifications.models.analytics import OptOutTracking
        model = OptOutTracking
        fields = [
            'id', 'user', 'channel', 'is_active', 'reason', 'notes',
            'triggered_by', 'actioned_by', 'opted_out_at', 'opted_in_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'opted_out_at', 'opted_in_at', 'created_at', 'updated_at']


class OptOutRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser', 'all']
    )
    reason = serializers.ChoiceField(
        choices=['too_many', 'not_relevant', 'privacy', 'spam', 'user_request', 'other'],
        default='user_request',
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class NotificationFatigueSerializer(serializers.ModelSerializer):
    effective_daily_limit = serializers.SerializerMethodField()
    effective_weekly_limit = serializers.SerializerMethodField()

    def get_effective_daily_limit(self, obj):
        return obj.get_effective_daily_limit()

    def get_effective_weekly_limit(self, obj):
        return obj.get_effective_weekly_limit()

    class Meta:
        from api.notifications.models.analytics import NotificationFatigue
        model = NotificationFatigue
        fields = [
            'id', 'user', 'sent_today', 'sent_this_week', 'sent_this_month',
            'daily_limit', 'weekly_limit', 'effective_daily_limit',
            'effective_weekly_limit', 'is_fatigued', 'last_evaluated_at',
            'daily_reset_at', 'weekly_reset_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'sent_today', 'sent_this_week', 'sent_this_month',
            'is_fatigued', 'last_evaluated_at', 'daily_reset_at', 'weekly_reset_at',
            'effective_daily_limit', 'effective_weekly_limit', 'created_at', 'updated_at',
        ]


class UserNotificationStatusSerializer(serializers.Serializer):
    """Full notification status summary for a user."""
    unread_count = serializers.IntegerField()
    unread_in_app = serializers.IntegerField()
    is_fatigued = serializers.BooleanField()
    opted_out_channels = serializers.ListField(child=serializers.CharField())
    active_devices = serializers.IntegerField()
    sent_today = serializers.IntegerField()
    sent_this_week = serializers.IntegerField()
