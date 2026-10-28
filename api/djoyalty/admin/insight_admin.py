# api/djoyalty/admin/insight_admin.py
from django.contrib import admin
from ..models.advanced import LoyaltyInsight, LoyaltyNotification, LoyaltySubscription


@admin.register(LoyaltyInsight)
class LoyaltyInsightAdmin(admin.ModelAdmin):
    list_display = ['report_date', 'period', 'total_customers', 'active_customers',
                    'total_points_issued', 'total_points_redeemed', 'total_revenue', 'generated_at']
    list_filter = ['period', 'report_date']
    readonly_fields = ['generated_at', 'created_at', 'updated_at']
    ordering = ['-report_date']
    fieldsets = [
        ('Report Info', {'fields': ['tenant', 'report_date', 'period', 'generated_at']}),
        ('Customers', {'fields': ['total_customers', 'active_customers', 'new_customers']}),
        ('Points', {'fields': ['total_points_issued', 'total_points_redeemed', 'total_points_expired',
                               'total_points_outstanding', 'liability_amount', 'redemption_rate']}),
        ('Revenue', {'fields': ['total_transactions', 'total_revenue']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]


@admin.register(LoyaltyNotification)
class LoyaltyNotificationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'notification_type', 'channel', 'is_sent', 'is_read', 'scheduled_at', 'sent_at', 'created_at']
    list_filter = ['notification_type', 'channel', 'is_sent', 'is_read']
    search_fields = ['customer__code', 'message', 'title']
    readonly_fields = ['created_at', 'sent_at', 'read_at']
    fieldsets = [
        ('Notification', {'fields': ['customer', 'notification_type', 'channel', 'title', 'message']}),
        ('Status', {'fields': ['is_sent', 'sent_at', 'is_read', 'read_at', 'scheduled_at']}),
        ('Metadata', {'fields': ['metadata', 'created_at']}),
    ]

    actions = ['mark_sent']

    def mark_sent(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_sent=False).update(is_sent=True, sent_at=timezone.now())
        self.message_user(request, f'{count} notifications marked as sent.')
    mark_sent.short_description = 'Mark selected as sent'


@admin.register(LoyaltySubscription)
class LoyaltySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'plan_name', 'multiplier', 'monthly_fee', 'bonus_points_monthly',
                    'is_active', 'started_at', 'next_renewal_at']
    list_filter = ['plan_name', 'is_active']
    search_fields = ['customer__code', 'plan_name']
    readonly_fields = ['started_at', 'created_at', 'updated_at', 'cancelled_at']
    fieldsets = [
        ('Subscription', {'fields': ['customer', 'plan_name', 'is_active']}),
        ('Benefits', {'fields': ['multiplier', 'monthly_fee', 'bonus_points_monthly']}),
        ('Schedule', {'fields': ['started_at', 'next_renewal_at', 'expires_at', 'cancelled_at']}),
        ('Payment', {'fields': ['payment_reference', 'cancel_reason']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    actions = ['cancel_subscriptions']

    def cancel_subscriptions(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_active=True).update(
            is_active=False, cancelled_at=timezone.now(),
            cancel_reason='Admin bulk cancel'
        )
        self.message_user(request, f'{count} subscriptions cancelled.')
    cancel_subscriptions.short_description = 'Cancel selected active subscriptions'
