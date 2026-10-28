"""
Django admin configuration for Telemetry Observability.
"""
from django.contrib import admin
from django.utils import timezone

from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.alert import Alert
from .models.dashboard_widget import DashboardWidget
from .models.health_status import HealthStatus


@admin.register(MetricEvent)
class MetricEventAdmin(admin.ModelAdmin):
    """
    Admin interface for MetricEvent.
    """
    list_display = ['name', 'metric_type', 'value', 'unit', 'source', 'service', 'environment', 'timestamp']
    list_filter = ['metric_type', 'source', 'service', 'environment', 'timestamp']
    search_fields = ['name', 'source', 'service']
    readonly_fields = ['timestamp', 'created_at', 'updated_at']
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'metric_type', 'value', 'unit')
        }),
        ('Source Information', {
            'fields': ('source', 'service', 'environment')
        }),
        ('Labels', {
            'fields': ('labels',)
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'created_at', 'updated_at')
        }),
    )


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """
    Admin interface for LogEntry.
    """
    list_display = ['level', 'message', 'logger_name', 'source', 'service', 'environment', 'timestamp']
    list_filter = ['level', 'source', 'service', 'environment', 'timestamp']
    search_fields = ['message', 'logger_name', 'source']
    readonly_fields = ['timestamp', 'created_at', 'updated_at']
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('level', 'message', 'logger_name')
        }),
        ('Source Information', {
            'fields': ('source', 'service', 'environment')
        }),
        ('Additional Information', {
            'fields': ('stack_trace', 'context', 'tags')
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'created_at', 'updated_at')
        }),
    )


@admin.register(TraceSpan)
class TraceSpanAdmin(admin.ModelAdmin):
    """
    Admin interface for TraceSpan.
    """
    list_display = ['operation_name', 'trace_id', 'span_id', 'service', 'duration_ms', 'status', 'start_time']
    list_filter = ['status', 'service', 'start_time']
    search_fields = ['operation_name', 'trace_id', 'span_id', 'service']
    readonly_fields = ['trace_id', 'span_id', 'start_time', 'created_at', 'updated_at']
    ordering = ['-start_time']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('trace_id', 'span_id', 'parent_span_id', 'operation_name')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration_ms')
        }),
        ('Status', {
            'fields': ('status', 'service')
        }),
        ('Additional Information', {
            'fields': ('tags', 'logs', 'context')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """
    Admin interface for Alert.
    """
    list_display = ['name', 'alert_type', 'severity', 'status', 'source', 'service', 'triggered_at']
    list_filter = ['alert_type', 'severity', 'status', 'source', 'service', 'triggered_at']
    search_fields = ['name', 'message', 'source']
    readonly_fields = ['triggered_at', 'created_at', 'updated_at']
    ordering = ['-triggered_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'alert_type', 'severity', 'status')
        }),
        ('Condition', {
            'fields': ('condition', 'message')
        }),
        ('Source Information', {
            'fields': ('source', 'service', 'environment')
        }),
        ('Resolution', {
            'fields': ('triggered_at', 'resolved_at', 'acknowledged_by', 'acknowledged_at')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        for alert in queryset:
            alert.acknowledge(request.user)
        self.message_user(request, f"{queryset.count()} alerts acknowledged.")
    acknowledge_alerts.short_description = "Acknowledge selected alerts"
    
    def resolve_alerts(self, request, queryset):
        """Resolve selected alerts."""
        for alert in queryset:
            alert.resolve()
        self.message_user(request, f"{queryset.count()} alerts resolved.")
    resolve_alerts.short_description = "Resolve selected alerts"


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    """
    Admin interface for DashboardWidget.
    """
    list_display = ['name', 'widget_type', 'data_source', 'position_x', 'position_y', 'width', 'height', 'is_active']
    list_filter = ['widget_type', 'data_source', 'is_active']
    search_fields = ['name']
    ordering = ['position_y', 'position_x']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'widget_type', 'data_source', 'is_active')
        }),
        ('Configuration', {
            'fields': ('query', 'config', 'refresh_interval')
        }),
        ('Layout', {
            'fields': ('position_x', 'position_y', 'width', 'height')
        }),
        ('Parent Dashboard', {
            'fields': ('dashboard',)
        }),
    )


@admin.register(HealthStatus)
class HealthStatusAdmin(admin.ModelAdmin):
    """
    Admin interface for HealthStatus.
    """
    list_display = ['service_name', 'component_name', 'status', 'health_score', 'uptime', 'response_time_ms', 'error_rate', 'last_check']
    list_filter = ['status', 'environment', 'last_check']
    search_fields = ['service_name', 'component_name']
    readonly_fields = ['last_check', 'created_at', 'updated_at']
    ordering = ['-last_check']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('service_name', 'component_name', 'status', 'health_score')
        }),
        ('Metrics', {
            'fields': ('uptime', 'response_time_ms', 'error_rate')
        }),
        ('Environment', {
            'fields': ('environment',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'last_check', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['mark_healthy', 'mark_unhealthy']
    
    def mark_healthy(self, request, queryset):
        """Mark selected statuses as healthy."""
        queryset.update(status='healthy', health_score=100)
        self.message_user(request, f"{queryset.count()} health statuses marked as healthy.")
    mark_healthy.short_description = "Mark as healthy"
    
    def mark_unhealthy(self, request, queryset):
        """Mark selected statuses as unhealthy."""
        queryset.update(status='unhealthy', health_score=0)
        self.message_user(request, f"{queryset.count()} health statuses marked as unhealthy.")
    mark_unhealthy.short_description = "Mark as unhealthy"
