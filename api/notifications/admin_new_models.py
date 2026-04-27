# earning_backend/api/notifications/admin_new_models.py
"""
Admin registration for all new split models.
Import this from admin.py to register.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone


def register_all_new_models():
    """Register all new split models with Django admin."""
    from django.contrib.admin.exceptions import AlreadyRegistered
    try:
        from api.notifications.models.channel import (
            PushDevice, PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog, InAppMessage
        )
        from api.notifications.models.schedule import (
            NotificationSchedule, NotificationBatch, NotificationQueue, NotificationRetry
        )
        from api.notifications.models.campaign import (
            CampaignSegment, NotificationCampaign as NewNotificationCampaign,
            CampaignABTest, CampaignResult
        )
        from api.notifications.models.analytics import (
            NotificationInsight, DeliveryRate, OptOutTracking, NotificationFatigue
        )

        # --- channel models ---
        if not admin.site.is_registered(PushDevice):
            @admin.register(PushDevice)
            class PushDeviceAdmin(admin.ModelAdmin):
                list_display = ['user', 'device_type', 'device_name', 'is_active', 'last_used']
                list_filter = ['device_type', 'is_active']
                search_fields = ['user__username', 'user__email', 'device_name']
                readonly_fields = ['created_at', 'updated_at', 'last_used']
                ordering = ['-last_used']
                list_select_related = ['user']

        if not admin.site.is_registered(PushDeliveryLog):
            @admin.register(PushDeliveryLog)
            class PushDeliveryLogAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'device', 'status', 'provider', 'delivered_at', 'created_at']
                list_filter = ['status', 'provider']
                search_fields = ['notification__title', 'provider_message_id']
                readonly_fields = ['created_at', 'updated_at']
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

        if not admin.site.is_registered(EmailDeliveryLog):
            @admin.register(EmailDeliveryLog)
            class EmailDeliveryLogAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'recipient', 'status', 'provider', 'opened_at', 'created_at']
                list_filter = ['status', 'provider']
                search_fields = ['recipient', 'message_id', 'notification__title']
                readonly_fields = ['created_at', 'updated_at']
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

        if not admin.site.is_registered(SMSDeliveryLog):
            @admin.register(SMSDeliveryLog)
            class SMSDeliveryLogAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'phone', 'gateway', 'status', 'cost', 'delivered_at', 'created_at']
                list_filter = ['status', 'gateway']
                search_fields = ['phone', 'provider_sid', 'notification__title']
                readonly_fields = ['created_at', 'updated_at']
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

        if not admin.site.is_registered(InAppMessage):
            @admin.register(InAppMessage)
            class InAppMessageAdmin(admin.ModelAdmin):
                list_display = ['id', 'user', 'message_type', 'title', 'is_read', 'is_dismissed', 'display_priority', 'created_at']
                list_filter = ['message_type', 'is_read', 'is_dismissed']
                search_fields = ['user__username', 'title', 'body']
                readonly_fields = ['created_at', 'updated_at', 'read_at', 'dismissed_at']
                ordering = ['display_priority', '-created_at']
                list_select_related = ['user']
                date_hierarchy = 'created_at'

        # --- schedule models ---
        if not admin.site.is_registered(NotificationSchedule):
            @admin.register(NotificationSchedule)
            class NotificationScheduleAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'send_at', 'timezone', 'status', 'sent_at']
                list_filter = ['status', 'timezone']
                search_fields = ['notification__title']
                readonly_fields = ['created_at', 'updated_at', 'sent_at']
                ordering = ['send_at']
                date_hierarchy = 'send_at'

        if not admin.site.is_registered(NotificationBatch):
            @admin.register(NotificationBatch)
            class NotificationBatchAdmin(admin.ModelAdmin):
                list_display = ['id', 'name', 'status', 'total_count', 'sent_count', 'failed_count', 'created_at']
                list_filter = ['status']
                search_fields = ['name', 'description']
                readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'sent_count', 'failed_count', 'total_count', 'celery_task_id']
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

        if not admin.site.is_registered(NotificationQueue):
            @admin.register(NotificationQueue)
            class NotificationQueueAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'priority', 'status', 'attempts', 'scheduled_at', 'created_at']
                list_filter = ['status', 'priority']
                search_fields = ['notification__title']
                readonly_fields = ['created_at', 'updated_at', 'last_attempt']
                ordering = ['-priority', 'scheduled_at']

        if not admin.site.is_registered(NotificationRetry):
            @admin.register(NotificationRetry)
            class NotificationRetryAdmin(admin.ModelAdmin):
                list_display = ['id', 'notification', 'attempt_number', 'max_attempts', 'status', 'retry_at', 'attempted_at']
                list_filter = ['status']
                search_fields = ['notification__title', 'error']
                readonly_fields = ['created_at', 'updated_at', 'attempted_at']
                ordering = ['notification', 'attempt_number']

        # --- campaign models ---
        if not admin.site.is_registered(CampaignSegment):
            @admin.register(CampaignSegment)
            class CampaignSegmentAdmin(admin.ModelAdmin):
                list_display = ['id', 'name', 'segment_type', 'estimated_size', 'last_evaluated_at', 'created_at']
                list_filter = ['segment_type']
                search_fields = ['name', 'description']
                readonly_fields = ['created_at', 'updated_at', 'estimated_size', 'last_evaluated_at']
                ordering = ['-created_at']

        if not admin.site.is_registered(NewNotificationCampaign):
            @admin.register(NewNotificationCampaign)
            class NewNotificationCampaignAdmin(admin.ModelAdmin):
                list_display = ['id', 'name', 'status', 'total_users', 'sent_count', 'failed_count', 'send_at', 'created_at']
                list_filter = ['status']
                search_fields = ['name', 'description']
                readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'sent_count', 'failed_count', 'total_users', 'celery_task_id']
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

        if not admin.site.is_registered(CampaignABTest):
            @admin.register(CampaignABTest)
            class CampaignABTestAdmin(admin.ModelAdmin):
                list_display = ['id', 'campaign', 'split_pct', 'winning_metric', 'winner', 'is_active', 'winner_declared_at']
                list_filter = ['winner', 'winning_metric', 'is_active']
                search_fields = ['campaign__name']
                readonly_fields = ['created_at', 'updated_at', 'winner', 'winner_declared_at']

        if not admin.site.is_registered(CampaignResult):
            @admin.register(CampaignResult)
            class CampaignResultAdmin(admin.ModelAdmin):
                list_display = ['campaign', 'sent', 'delivered', 'opened', 'clicked', 'delivery_rate', 'open_rate', 'click_rate', 'calculated_at']
                readonly_fields = [f.name for f in CampaignResult._meta.fields]
                ordering = ['-calculated_at']

        # --- analytics models ---
        if not admin.site.is_registered(NotificationInsight):
            @admin.register(NotificationInsight)
            class NotificationInsightAdmin(admin.ModelAdmin):
                list_display = ['date', 'channel', 'sent', 'delivered', 'opened', 'clicked', 'unsubscribed']
                list_filter = ['channel']
                readonly_fields = [f.name for f in NotificationInsight._meta.fields]
                ordering = ['-date', 'channel']
                date_hierarchy = 'date'

        if not admin.site.is_registered(DeliveryRate):
            @admin.register(DeliveryRate)
            class DeliveryRateAdmin(admin.ModelAdmin):
                list_display = ['date', 'channel', 'delivery_pct', 'open_pct', 'click_pct', 'sample_size']
                list_filter = ['channel']
                readonly_fields = [f.name for f in DeliveryRate._meta.fields]
                ordering = ['-date', 'channel']
                date_hierarchy = 'date'

        if not admin.site.is_registered(OptOutTracking):
            @admin.register(OptOutTracking)
            class OptOutTrackingAdmin(admin.ModelAdmin):
                list_display = ['user', 'channel', 'is_active', 'reason', 'opted_out_at', 'opted_in_at']
                list_filter = ['channel', 'is_active', 'reason']
                search_fields = ['user__username', 'user__email', 'notes']
                readonly_fields = ['created_at', 'updated_at', 'opted_out_at']
                ordering = ['-opted_out_at']
                list_select_related = ['user']
                date_hierarchy = 'opted_out_at'

        if not admin.site.is_registered(NotificationFatigue):
            @admin.register(NotificationFatigue)
            class NotificationFatigueAdmin(admin.ModelAdmin):
                list_display = ['user', 'sent_today', 'sent_this_week', 'sent_this_month', 'is_fatigued', 'daily_limit', 'weekly_limit', 'last_evaluated_at']
                list_filter = ['is_fatigued']
                search_fields = ['user__username', 'user__email']
                readonly_fields = ['sent_today', 'sent_this_week', 'sent_this_month', 'is_fatigued', 'last_evaluated_at', 'daily_reset_at', 'weekly_reset_at', 'created_at', 'updated_at']
                ordering = ['-sent_this_week']
                list_select_related = ['user']

        print('[OK] All new split models registered with admin.')

    except Exception as e:
        print(f'[WARN] admin_new_models register error: {e}')
