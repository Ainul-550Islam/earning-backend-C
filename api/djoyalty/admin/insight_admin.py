# api/djoyalty/admin/insight_admin.py
from django.contrib import admin
from ..models.advanced import LoyaltyInsight, LoyaltyNotification

@admin.register(LoyaltyInsight)
class LoyaltyInsightAdmin(admin.ModelAdmin):
    list_display = ['report_date', 'period', 'total_customers', 'active_customers', 'new_customers', 'total_points_issued', 'total_transactions', 'total_revenue', 'created_at']
    list_filter = ['period']
    readonly_fields = ['created_at']
    ordering = ['-report_date']

@admin.register(LoyaltyNotification)
class LoyaltyNotificationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'notification_type', 'channel', 'title', 'is_sent', 'is_read', 'created_at']
    list_filter = ['notification_type', 'channel', 'is_sent', 'is_read']
    search_fields = ['customer__code', 'title']
    readonly_fields = ['created_at']
