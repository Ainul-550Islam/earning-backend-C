"""Webhook Analytics Admin Configuration

This module contains the Django admin configuration for webhook analytics models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
import json

from ..models import (
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat,
    WebhookRateLimit, WebhookRetryAnalysis
)
from ..models.constants import WebhookStatus


@admin.register(WebhookAnalytics)
class WebhookAnalyticsAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookAnalytics model."""

    list_display = [
        'total_sent',
        'failed_count',
        'success_rate',
        'avg_latency_ms'
    ]

    list_filter = []

    search_fields = [
        'endpoint__label',
        'endpoint__url',
        'endpoint__owner__username'
    ]

    readonly_fields = ['id']

    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {
            'fields': ()
        }),
        ('Delivery Statistics', {
            'fields': (
                'total_sent',
                'failed_count',
                'success_rate'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'avg_latency_ms',
                'min_latency_ms',
                'max_latency_ms',
                'p95_latency_ms',
                'p99_latency_ms'
            )
        }),
        ('Error Analysis', {
            'fields': (
                'error_breakdown',
                'retry_count',
                'exhausted_count'
            )
        }),
        ('Timestamps', {
            'fields': (),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related()

    def success_rate(self, obj):
        """Display success rate as a colored percentage."""
        if obj.total_sent == 0:
            return "0%"
        rate = (obj.success_count / obj.total_sent) * 100
        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    success_rate.short_description = 'Success Rate'
    success_rate.admin_order_field = 'success_rate'

    def avg_latency_display(self, obj):
        """Display average latency with color coding."""
        if not obj.avg_latency_ms:
            return "N/A"
        latency = obj.avg_latency_ms
        color = 'green' if latency < 100 else 'orange' if latency < 500 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}ms</span>',
            color, latency
        )
    avg_latency_display.short_description = 'Avg Latency'

    def error_breakdown_display(self, obj):
        """Display error breakdown as a formatted string."""
        if not obj.error_breakdown:
            return "No errors"
        breakdown = obj.error_breakdown
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except:
                return str(breakdown)[:50] + "..."
        error_count = sum(breakdown.values()) if isinstance(breakdown, dict) else 0
        return f"{error_count} errors"
    error_breakdown_display.short_description = 'Error Count'

    def get_actions(self, request):
        """Add custom actions."""
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.generate_analytics'):
            actions.append('generate_analytics')
        if request.user.has_perm('webhooks.export_analytics'):
            actions.append('export_analytics')
        return actions

    def generate_analytics(self, request, queryset):
        """Generate analytics for selected endpoints."""
        from ..services.analytics import WebhookAnalyticsService
        service = WebhookAnalyticsService()
        generated_count = 0
        for analytics in queryset:
            try:
                service.generate_daily_analytics(endpoint=analytics.endpoint, days=7)
                generated_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to generate analytics for {analytics.endpoint.label}: {str(e)}", level='error')
        self.message_user(request, f"Successfully generated analytics for {generated_count} endpoints.")
    generate_analytics.short_description = 'Generate analytics for selected endpoints'

    def export_analytics(self, request, queryset):
        """Export selected analytics to CSV."""
        import csv
        import os
        from datetime import datetime
        export_dir = 'exports'
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'webhook_analytics_{timestamp}.csv'
        filepath = os.path.join(export_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Endpoint', 'Date', 'Total Sent', 'Success Count', 'Failed Count', 'Success Rate (%)', 'Avg Latency (ms)'])
            for analytics in queryset:
                writer.writerow([
                    analytics.endpoint.label or analytics.endpoint.url,
                    analytics.date, analytics.total_sent, analytics.success_count, analytics.failed_count,
                    (analytics.success_count / analytics.total_sent * 100) if analytics.total_sent > 0 else 0,
                    analytics.avg_latency_ms or 0
                ])
        self.message_user(request, f"Successfully exported analytics to {filepath}")
    export_analytics.short_description = 'Export selected analytics to CSV'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookHealthLog)
class WebhookHealthLogAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookHealthLog model."""

    list_display = ['is_healthy', 'status_code', 'response_time_ms', 'checked_at']
    list_filter = ['is_healthy', 'status_code', 'checked_at']
    search_fields = ['endpoint__label', 'endpoint__url', 'endpoint__owner__username', 'error']
    readonly_fields = ['id']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ('is_healthy', 'checked_at')}),
        ('Health Check Results', {'fields': ('status_code', 'response_time_ms', 'error')}),
        ('System Information', {'fields': ('id',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

    def health_badge(self, obj):
        color = 'green' if obj.is_healthy else 'red'
        status = 'Healthy' if obj.is_healthy else 'Unhealthy'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, status)
    health_badge.short_description = 'Health Status'

    def response_time_display(self, obj):
        if not obj.response_time_ms:
            return "N/A"
        t = obj.response_time_ms
        color = 'green' if t < 200 else 'orange' if t < 1000 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{}ms</span>', color, t)
    response_time_display.short_description = 'Response Time'

    def status_code_badge(self, obj):
        if not obj.status_code:
            return "N/A"
        code = obj.status_code
        color = 'green' if 200 <= code < 300 else 'blue' if 300 <= code < 400 else 'orange' if 400 <= code < 500 else 'red' if 500 <= code < 600 else 'gray'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, code)
    status_code_badge.short_description = 'HTTP Status'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.check_health'):
            actions.append('check_health')
        if request.user.has_perm('webhooks.cleanup_health_logs'):
            actions.append('cleanup_old_logs')
        return actions

    def check_health(self, request, queryset):
        from ..services.analytics import HealthMonitorService
        service = HealthMonitorService()
        results = []
        for log in queryset:
            try:
                health = service.check_endpoint_health(log.endpoint)
                status = 'Healthy' if health['is_healthy'] else 'Unhealthy'
                results.append(f"{log.endpoint.label or log.endpoint.url}: {status}")
            except Exception as e:
                results.append(f"{log.endpoint.label or log.endpoint.url}: Error - {str(e)}")
        self.message_user(request, f"Health check results: {'; '.join(results)}")
    check_health.short_description = 'Check health for selected endpoints'

    def cleanup_old_logs(self, request, queryset):
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = sum(1 for log in queryset if log.checked_at < cutoff_date and log.delete())
        self.message_user(request, f"Successfully deleted {deleted_count} old health logs.")
    cleanup_old_logs.short_description = 'Delete old health logs (30+ days)'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookEventStat)
class WebhookEventStatAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookEventStat model."""

    list_display = ['event_type']
    list_filter = ['event_type']
    search_fields = ['event_type', 'endpoint__label', 'endpoint__url', 'endpoint__owner__username']
    readonly_fields = ['id']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ('event_type',)}),
        ('Statistics', {'fields': ('avg_response_time_ms',)}),
        ('Timestamps', {'fields': (), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

    def success_rate(self, obj):
        if obj.count == 0:
            return "0%"
        rate = (obj.success_count / obj.count) * 100
        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, rate)
    success_rate.short_description = 'Success Rate'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookRateLimit)
class WebhookRateLimitAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookRateLimit model."""

    list_display = ['window_seconds', 'max_requests', 'current_count', 'utilization', 'reset_at']
    list_filter = ['window_seconds']
    search_fields = ['endpoint__label', 'endpoint__url', 'endpoint__owner__username']
    readonly_fields = ['id']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ('window_seconds', 'max_requests')}),
        ('Current Status', {'fields': ('current_count', 'reset_at')}),
        ('Timestamps', {'fields': (), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

    def utilization(self, obj):
        if obj.max_requests == 0:
            return "0%"
        u = (obj.current_count / obj.max_requests) * 100
        color = 'green' if u < 70 else 'orange' if u < 90 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, u)
    utilization.short_description = 'Utilization'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.reset_rate_limits'):
            actions.append('reset_limits')
        if request.user.has_perm('webhooks.cleanup_rate_limits'):
            actions.append('cleanup_expired')
        return actions

    def reset_limits(self, request, queryset):
        from ..services.analytics import RateLimiterService
        service = RateLimiterService()
        reset_count = 0
        for rate_limit in queryset:
            try:
                service.reset_rate_limit(rate_limit.endpoint, rate_limit.window_seconds)
                reset_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to reset rate limit for {rate_limit.endpoint.label}: {str(e)}", level='error')
        self.message_user(request, f"Successfully reset {reset_count} rate limits.")
    reset_limits.short_description = 'Reset rate limits for selected endpoints'

    def cleanup_expired(self, request, queryset):
        from ..services.analytics import RateLimiterService
        service = RateLimiterService()
        result = service.cleanup_expired_rate_limits()
        self.message_user(request, f"Successfully cleaned up {result['cleaned_count']} expired rate limits.")
    cleanup_expired.short_description = 'Clean up expired rate limits'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookRetryAnalysis)
class WebhookRetryAnalysisAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookRetryAnalysis model."""

    list_display = ['retry_rate']
    list_filter = []
    search_fields = ['endpoint__label', 'endpoint__url', 'endpoint__owner__username']
    readonly_fields = ['id']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ()}),
        ('Retry Statistics', {'fields': ('retry_rate', 'avg_retry_attempts')}),
        ('Performance Metrics', {'fields': ('avg_retry_delay_ms', 'max_retry_delay_ms', 'total_retry_time_ms')}),
        ('Timestamps', {'fields': (), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

    def retry_rate(self, obj):
        if obj.total_retries == 0:
            return "0%"
        rate = (obj.successful_retries / obj.total_retries) * 100
        color = 'green' if rate >= 70 else 'orange' if rate >= 50 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, rate)
    retry_rate.short_description = 'Retry Success Rate'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


WebhookHealthLogAdmin.list_display = ['health_badge', 'status_code_badge', 'response_time_display', 'checked_at']
