# api/admin_panel/admin/dashboard_admin.py
"""Django admin for dashboard models."""
from django.contrib import admin
from ..models.dashboard import DashboardWidget, DashboardLayout, DashboardMetric, DashboardAlert, QuickAction


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['title', 'widget_type', 'size', 'user', 'is_visible', 'updated_at']
    list_filter = ['widget_type', 'size', 'is_visible']
    search_fields = ['title', 'user__username']
    raw_id_fields = ['user']


@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ['metric_key', 'label', 'value', 'unit', 'period', 'cached_at']
    list_filter = ['period']
    search_fields = ['metric_key', 'label']
    readonly_fields = ['cached_at']


@admin.register(DashboardAlert)
class DashboardAlertAdmin(admin.ModelAdmin):
    list_display = ['label', 'metric', 'threshold', 'operator', 'is_active', 'last_triggered', 'trigger_count']
    list_filter = ['is_active', 'operator']
    search_fields = ['label']
    readonly_fields = ['last_triggered', 'trigger_count']


@admin.register(QuickAction)
class QuickActionAdmin(admin.ModelAdmin):
    list_display = ['label', 'url', 'icon', 'color', 'sort_order', 'is_active']
    list_filter = ['is_active', 'color']
    list_editable = ['sort_order', 'is_active']
    search_fields = ['label', 'url']
    ordering = ['sort_order', 'label']