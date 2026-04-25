# earning_backend/api/notifications/admin_new_models.py
"""
Admin registration for all 17 new split models.
Import this from admin.py to register.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone


# ============================================================
# channel.py admins
# ============================================================

@admin.register_check
def register_push_device(model_admin_site):
    from notifications.models.channel import PushDevice

    @admin.register(PushDevice)
    class PushDeviceAdmin(admin.ModelAdmin):
        list_display = ['user', 'device_type', 'device_name', 'is_active', 'last_used', 'delivery_rate_display']
        list_filter = ['device_type', 'is_active']
        search_fields = ['user__username', 'user__email', 'device_name', 'device_model']
        readonly_fields = ['created_at', 'updated_at', 'last_used']
        ordering = ['-last_used']
        list_select_related = ['user']

        def delivery_rate_display(self, obj):
            rate = obj.get_delivery_rate()
            color = 'green' if rate >= 80 else ('orange' if rate >= 50 else 'red')
            return format_html('<span style="color:{}">{:.1f}%</span>', color, rate)
        delivery_rate_display.short_description = 'Delivery Rate'

        actions = ['deactivate_devices', 'activate_devices']

        def deactivate_devices(self, request, queryset):
            queryset.update(is_active=False, updated_at=timezone.now())
            self.message_user(request, f'{queryset.count()} devices deactivated.')
        deactivate_devices.short_description = 'Deactivate selected devices'

        def activate_devices(self, request, queryset):
            queryset.update(is_active=True, updated_at=timezone.now())
            self.message_user(request, f'{queryset.count()} devices activated.')
        activate_devices.short_description = 'Activate selected devices'


def register_all_new_models():
    """Register all new split models with Django admin."""
    try:
        from notifications.models.channel import (
            PushDevice, PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog, InAppMessage
        )
        from notifications.models.schedule import (
            NotificationSchedule, NotificationBatch, NotificationQueue, NotificationRetry
        )
        from notifications.models.campaign import (
            CampaignSegment, NotificationCampaign as NewNotificationCampaign,
            CampaignABTest, CampaignResult
        )
        from notifications.models.analytics import (
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

                actions = ['mark_all_read', 'dismiss_all']

                def mark_all_read(self, request, queryset):
                    from django.utils import timezone
                    queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
                    self.message_user(request, f'Marked as read.')
                mark_all_read.short_description = 'Mark selected as read'

                def dismiss_all(self, request, queryset):
                    from django.utils import timezone
                    queryset.filter(is_dismissed=False).update(is_dismissed=True, dismissed_at=timezone.now())
                    self.message_user(request, 'Dismissed.')
                dismiss_all.short_description = 'Dismiss selected messages'

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

                actions = ['cancel_schedules']

                def cancel_schedules(self, request, queryset):
                    queryset.filter(status='pending').update(
                        status='cancelled', updated_at=timezone.now()
                    )
                    self.message_user(request, 'Cancelled selected schedules.')
                cancel_schedules.short_description = 'Cancel selected schedules'

        if not admin.site.is_registered(NotificationBatch):
            @admin.register(NotificationBatch)
            class NotificationBatchAdmin(admin.ModelAdmin):
                list_display = [
                    'id', 'name', 'status', 'total_count', 'sent_count',
                    'failed_count', 'progress_pct_display', 'created_at'
                ]
                list_filter = ['status']
                search_fields = ['name', 'description']
                readonly_fields = [
                    'created_at', 'updated_at', 'started_at', 'completed_at',
                    'sent_count', 'failed_count', 'total_count', 'celery_task_id'
                ]
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

                def progress_pct_display(self, obj):
                    pct = obj.progress_pct
                    return format_html('<progress value="{}" max="100"></progress> {:.1f}%', pct, pct)
                progress_pct_display.short_description = 'Progress'

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
                list_display = [
                    'id', 'name', 'status', 'total_users', 'sent_count',
                    'failed_count', 'send_at', 'created_at'
                ]
                list_filter = ['status']
                search_fields = ['name', 'description']
                readonly_fields = [
                    'created_at', 'updated_at', 'started_at', 'completed_at',
                    'sent_count', 'failed_count', 'total_users', 'celery_task_id'
                ]
                ordering = ['-created_at']
                date_hierarchy = 'created_at'

                actions = ['start_campaigns', 'cancel_campaigns']

                def start_campaigns(self, request, queryset):
                    from notifications.services.CampaignService import campaign_service
                    started = 0
                    for campaign in queryset.filter(status__in=('draft', 'scheduled')):
                        result = campaign_service.start_campaign(campaign.pk)
                        if result.get('success'):
                            started += 1
                    self.message_user(request, f'Started {started} campaign(s).')
                start_campaigns.short_description = 'Start selected campaigns'

                def cancel_campaigns(self, request, queryset):
                    from notifications.services.CampaignService import campaign_service
                    cancelled = 0
                    for campaign in queryset:
                        result = campaign_service.cancel_campaign(campaign.pk)
                        if result.get('success'):
                            cancelled += 1
                    self.message_user(request, f'Cancelled {cancelled} campaign(s).')
                cancel_campaigns.short_description = 'Cancel selected campaigns'

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
                list_display = [
                    'campaign', 'sent', 'delivered', 'opened', 'clicked',
                    'delivery_rate', 'open_rate', 'click_rate', 'calculated_at'
                ]
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

                actions = ['resubscribe_users']

                def resubscribe_users(self, request, queryset):
                    count = queryset.filter(is_active=True).update(
                        is_active=False, opted_in_at=timezone.now(), updated_at=timezone.now()
                    )
                    self.message_user(request, f'Re-subscribed {count} user(s).')
                resubscribe_users.short_description = 'Re-subscribe selected users'

        if not admin.site.is_registered(NotificationFatigue):
            @admin.register(NotificationFatigue)
            class NotificationFatigueAdmin(admin.ModelAdmin):
                list_display = [
                    'user', 'sent_today', 'sent_this_week', 'sent_this_month',
                    'is_fatigued', 'daily_limit', 'weekly_limit', 'last_evaluated_at'
                ]
                list_filter = ['is_fatigued']
                search_fields = ['user__username', 'user__email']
                readonly_fields = [
                    'sent_today', 'sent_this_week', 'sent_this_month',
                    'is_fatigued', 'last_evaluated_at', 'daily_reset_at',
                    'weekly_reset_at', 'created_at', 'updated_at'
                ]
                ordering = ['-sent_this_week']
                list_select_related = ['user']

                actions = ['clear_fatigue', 'reset_counters']

                def clear_fatigue(self, request, queryset):
                    queryset.update(is_fatigued=False, last_evaluated_at=timezone.now(), updated_at=timezone.now())
                    self.message_user(request, f'Cleared fatigue for {queryset.count()} user(s).')
                clear_fatigue.short_description = 'Clear fatigue flag'

                def reset_counters(self, request, queryset):
                    queryset.update(
                        sent_today=0, sent_this_week=0,
                        is_fatigued=False, updated_at=timezone.now()
                    )
                    self.message_user(request, f'Reset counters for {queryset.count()} user(s).')
                reset_counters.short_description = 'Reset send counters'

        print('[OK] All new split models registered with admin.')

    except Exception as e:
        import traceback
        print(f'[WARN] admin_new_models register error: {e}')
        traceback.print_exc()
