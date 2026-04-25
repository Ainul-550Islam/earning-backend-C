#!/bin/bash
# ================================================================
# Webhook Admin Files - Complete Fix Script
# Usage: Run this from your project root in Git Bash
# cd ~/New\ folder\ \(8\)/earning_backend
# bash fix_all_webhook_admins.sh
# ================================================================

set -e
ADMIN_DIR="api/webhooks/admin"
echo "🔧 Starting webhook admin fix..."

# ================================================================
# 1. analytics_admin.py
# ================================================================
cat > "$ADMIN_DIR/analytics_admin.py" << 'EOF'
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
EOF

echo "✅ analytics_admin.py done"

# ================================================================
# 2. delivery_log_admin.py
# ================================================================
cat > "$ADMIN_DIR/delivery_log_admin.py" << 'EOF'
"""Webhook Delivery Log Admin Configuration

This module contains the Django admin configuration for the WebhookDeliveryLog model.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone
import json

from ..models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from ..models.constants import DeliveryStatus


@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookDeliveryLog model."""

    list_display = ['endpoint', 'event_type', 'status', 'http_status_code', 'duration_ms', 'attempt_number']

    list_filter = ['status', 'http_status_code', 'event_type', 'attempt_number', 'endpoint__status', 'endpoint__owner']

    search_fields = ['event_type', 'endpoint__label', 'endpoint__url', 'endpoint__owner__username', 'error_message']

    readonly_fields = ['id', 'updated_at', 'payload_preview', 'request_headers_preview', 'signature_preview', 'response_body_preview']

    raw_id_fields = ('endpoint',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('endpoint', 'event_type', 'status', 'attempt_number', 'max_attempts')
        }),
        ('Request Details', {
            'fields': ('payload_preview', 'request_headers_preview', 'signature_preview'),
            'classes': ('collapse',)
        }),
        ('Response Details', {
            'fields': ('http_status_code', 'response_body_preview', 'duration_ms')
        }),
        ('Retry Information', {
            'fields': ('next_retry_at', 'dispatched_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('endpoint', 'endpoint__owner')

    def payload_preview(self, obj):
        if not obj.payload:
            return "No payload"
        payload_str = json.dumps(obj.payload, indent=2)
        preview = payload_str[:200] + "..." if len(payload_str) > 200 else payload_str
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    payload_preview.short_description = 'Payload Preview'

    def request_headers_preview(self, obj):
        if not obj.request_headers:
            return "No headers"
        headers_str = json.dumps(obj.request_headers, indent=2)
        preview = headers_str[:200] + "..." if len(headers_str) > 200 else headers_str
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    request_headers_preview.short_description = 'Request Headers'

    def signature_preview(self, obj):
        if not obj.signature:
            return "No signature"
        s = str(obj.signature)
        preview = s[:50] + "..." + s[-50:] if len(s) > 100 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    signature_preview.short_description = 'Signature'

    def response_body_preview(self, obj):
        if not obj.response_body:
            return "No response body"
        s = str(obj.response_body)
        preview = s[:200] + "..." if len(s) > 200 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    response_body_preview.short_description = 'Response Body'

    def status_badge(self, obj):
        color_map = {
            DeliveryStatus.SUCCESS: 'green', DeliveryStatus.FAILED: 'red',
            DeliveryStatus.PENDING: 'orange', DeliveryStatus.RETRYING: 'blue',
            DeliveryStatus.EXHAUSTED: 'darkred'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def http_status_badge(self, obj):
        if not obj.http_status_code:
            return "N/A"
        code = obj.http_status_code
        color = 'green' if 200 <= code < 300 else 'blue' if 300 <= code < 400 else 'orange' if 400 <= code < 500 else 'red' if 500 <= code < 600 else 'gray'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, code)
    http_status_badge.short_description = 'HTTP Status'

    def duration_display(self, obj):
        if not obj.duration_ms:
            return "N/A"
        d = obj.duration_ms
        color = 'green' if d < 100 else 'orange' if d < 500 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{}ms</span>', color, d)
    duration_display.short_description = 'Duration'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.retry_delivery'):
            actions.append('retry_delivery')
        if request.user.has_perm('webhooks.create_replay'):
            actions.append('create_replay')
        if request.user.has_perm('webhooks.delete_delivery_logs'):
            actions.append('delete_old_logs')
        return actions

    def retry_delivery(self, request, queryset):
        from ..services.core import DispatchService
        service = DispatchService()
        results = []
        for log in queryset:
            if log.status == DeliveryStatus.SUCCESS:
                results.append(f"{log.id}: Already successful")
                continue
            try:
                result = service.retry_delivery(log)
                results.append(f"{log.id}: {'Success' if result else 'Failed'}")
            except Exception as e:
                results.append(f"{log.id}: Error - {str(e)}")
        self.message_user(request, f"Retry results: {'; '.join(results)}")
    retry_delivery.short_description = 'Retry selected deliveries'

    def create_replay(self, request, queryset):
        from ..services.replay import ReplayService
        service = ReplayService()
        created_count = 0
        for log in queryset:
            if log.status != DeliveryStatus.FAILED:
                continue
            try:
                service.create_replay(original_log=log, replayed_by=request.user, reason='Manual replay from admin')
                created_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to create replay for {log.id}: {str(e)}", level='error')
        self.message_user(request, f"Successfully created {created_count} replays.")
    create_replay.short_description = 'Create replay for failed deliveries'

    def delete_old_logs(self, request, queryset):
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count = 0
        for log in queryset:
            if log.created_at < cutoff_date:
                log.delete()
                deleted_count += 1
        self.message_user(request, f"Successfully deleted {deleted_count} old logs.")
    delete_old_logs.short_description = 'Delete old logs (90+ days)'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('webhooks.change_deliverylog')

    def delete_model(self, request, obj):
        self.message_user(request, f"Deleted delivery log: {obj.id} for {obj.event_type}", level='warning')
        super().delete_model(request, obj)

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


WebhookDeliveryLogAdmin.list_display = ['endpoint', 'event_type', 'status_badge', 'http_status_badge', 'duration_display', 'attempt_number']
EOF

echo "✅ delivery_log_admin.py done"

# ================================================================
# 3. inbound_admin.py
# ================================================================
cat > "$ADMIN_DIR/inbound_admin.py" << 'EOF'
"""Inbound Webhook Admin Configuration

This module contains the Django admin configuration for inbound webhook models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
import json

from ..models import (
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError
)
from ..models.constants import InboundSource, ErrorType


@admin.register(InboundWebhook)
class InboundWebhookAdmin(admin.ModelAdmin):
    """Admin configuration for InboundWebhook model."""

    list_display = ['source', 'url_token', 'is_active', 'total_logs', 'success_rate', 'last_activity', 'created_at']
    list_filter = ['source', 'is_active', 'created_at', 'created_by']
    search_fields = ['source', 'url_token', 'description', 'created_by__username']
    readonly_fields = ['id', 'created_at', 'total_logs', 'last_activity']
    raw_id_fields = ('created_by',)

    fieldsets = (
        ('Basic Information', {'fields': ('source', 'url_token', 'description', 'is_active', 'created_by')}),
        ('Security', {'fields': ('secret', 'ip_whitelist', 'allowed_origins')}),
        ('Configuration', {'fields': ('max_payload_size', 'signature_header', 'event_type_header', 'timestamp_header')}),
        ('Statistics', {'fields': ('total_logs', 'success_rate', 'last_activity'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by').annotate(
            total_logs=Count('logs'),
            success_logs=Count('logs', filter=Q(logs__processed=True)),
            failed_logs=Count('logs', filter=Q(logs__processed=False))
        )

    def total_logs(self, obj):
        return obj.logs.count()
    total_logs.short_description = 'Total Logs'

    def success_rate(self, obj):
        total = obj.logs.count()
        if total == 0:
            return "0%"
        success = obj.logs.filter(processed=True).count()
        rate = (success / total) * 100
        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, rate)
    success_rate.short_description = 'Success Rate'

    def last_activity(self, obj):
        last_log = obj.logs.order_by('-created_at').first()
        return last_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_log else "No activity"
    last_activity.short_description = 'Last Activity'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.toggle_inbound'):
            actions.append('toggle_active')
        if request.user.has_perm('webhooks.rotate_inbound_secret'):
            actions.append('rotate_secret')
        if request.user.has_perm('webhooks.test_inbound'):
            actions.append('test_inbound')
        return actions

    def toggle_active(self, request, queryset):
        updated_count = 0
        for inbound in queryset:
            inbound.is_active = not inbound.is_active
            inbound.save()
            updated_count += 1
            status = 'activated' if inbound.is_active else 'deactivated'
            self.message_user(request, f"Inbound webhook {inbound.source} ({inbound.url_token}) {status}")
        self.message_user(request, f"Successfully updated {updated_count} inbound webhooks.")
    toggle_active.short_description = 'Toggle active status'

    def rotate_secret(self, request, queryset):
        from ..services.core import SecretRotationService
        service = SecretRotationService()
        rotated_count = 0
        for inbound in queryset:
            try:
                new_secret = service.rotate_inbound_secret(inbound)
                rotated_count += 1
                self.message_user(request, f"Rotated secret for {inbound.source}: {new_secret[:8]}...")
            except Exception as e:
                self.message_user(request, f"Failed to rotate secret for {inbound.source}: {str(e)}", level='error')
        self.message_user(request, f"Successfully rotated {rotated_count} secrets.")
    rotate_secret.short_description = 'Rotate secrets for selected inbound webhooks'

    def test_inbound(self, request, queryset):
        from ..services.inbound import InboundWebhookService
        service = InboundWebhookService()
        results = []
        for inbound in queryset:
            try:
                test_payload = {'event': {'type': 'webhook.test', 'data': {'test': True, 'timestamp': str(timezone.now())}}}
                headers = {'Content-Type': 'application/json', 'X-Test-Signature': 'test-signature'}
                result = service.process_inbound_webhook(inbound=inbound, payload=test_payload, headers=headers, ip_address='127.0.0.1')
                results.append(f"{inbound.source}: {'Success' if result['success'] else 'Failed'}")
            except Exception as e:
                results.append(f"{inbound.source}: Error - {str(e)}")
        self.message_user(request, f"Test results: {'; '.join(results)}")
    test_inbound.short_description = 'Test selected inbound webhooks'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(InboundWebhookLog)
class InboundWebhookLogAdmin(admin.ModelAdmin):
    """Admin configuration for InboundWebhookLog model."""

    list_display = ['inbound', 'processed', 'signature_valid', 'ip_address', 'created_at']
    list_filter = ['inbound__source', 'processed', 'signature_valid', 'created_at']
    search_fields = ['inbound__source', 'ip_address', 'error_message']
    readonly_fields = ['id', 'created_at', 'raw_payload_preview', 'headers_preview', 'signature_preview']
    raw_id_fields = ('inbound',)

    fieldsets = (
        ('Basic Information', {'fields': ('inbound', 'processed', 'signature_valid', 'ip_address')}),
        ('Request Details', {'fields': ('raw_payload_preview', 'headers_preview', 'signature_preview'), 'classes': ('collapse',)}),
        ('Processing Information', {'fields': ('processed_at', 'error_message'), 'classes': ('collapse',)}),
        ('System Information', {'fields': ('id', 'created_at'), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('inbound', 'inbound__created_by')

    def raw_payload_preview(self, obj):
        if not obj.raw_payload:
            return "No payload"
        s = json.dumps(obj.raw_payload, indent=2)
        preview = s[:200] + "..." if len(s) > 200 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    raw_payload_preview.short_description = 'Raw Payload'

    def headers_preview(self, obj):
        if not obj.headers:
            return "No headers"
        s = json.dumps(obj.headers, indent=2)
        preview = s[:200] + "..." if len(s) > 200 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    headers_preview.short_description = 'Headers'

    def signature_preview(self, obj):
        if not obj.signature:
            return "No signature"
        s = str(obj.signature)
        preview = s[:50] + "..." + s[-50:] if len(s) > 100 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    signature_preview.short_description = 'Signature'

    def processed_badge(self, obj):
        color = 'green' if obj.processed else 'orange'
        status = 'Processed' if obj.processed else 'Pending'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, status)
    processed_badge.short_description = 'Processed'

    def signature_badge(self, obj):
        if obj.signature_valid is None:
            return format_html('<span style="background: gray; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">N/A</span>')
        color = 'green' if obj.signature_valid else 'red'
        status = 'Valid' if obj.signature_valid else 'Invalid'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, status)
    signature_badge.short_description = 'Signature'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(InboundWebhookRoute)
class InboundWebhookRouteAdmin(admin.ModelAdmin):
    """Admin configuration for InboundWebhookRoute model."""

    list_display = ['inbound', 'event_pattern', 'handler_function', 'is_active', 'created_at']
    list_filter = ['inbound__source', 'is_active', 'created_at']
    search_fields = ['inbound__source', 'event_pattern', 'handler_function']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ('inbound',)

    fieldsets = (
        ('Basic Information', {'fields': ('inbound', 'event_pattern', 'handler_function', 'is_active')}),
        ('Configuration', {'fields': ('priority', 'timeout_seconds', 'retry_attempts')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('inbound')


@admin.register(InboundWebhookError)
class InboundWebhookErrorAdmin(admin.ModelAdmin):
    """Admin configuration for InboundWebhookError model."""

    list_display = ['log', 'error_type', 'created_at']
    list_filter = ['error_type', 'created_at']
    search_fields = ['error_message', 'log__inbound__source']
    readonly_fields = ['id', 'created_at', 'error_details']
    raw_id_fields = ('log',)

    fieldsets = (
        ('Basic Information', {'fields': ('log', 'error_type')}),
        ('Error Details', {'fields': ('error_message', 'error_details')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('log', 'log__inbound')

    def error_details(self, obj):
        if not obj.error_message:
            return "No error message"
        s = str(obj.error_message)
        preview = s[:500] + "..." if len(s) > 500 else s
        return format_html('<pre style="background: #ffebee; padding: 5px; font-size: 11px; color: #c62828;">{}</pre>', preview)
    error_details.short_description = 'Error Details'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


InboundWebhookLogAdmin.list_display = ['inbound', 'processed_badge', 'signature_badge', 'ip_address', 'created_at']
EOF

echo "✅ inbound_admin.py done"

# ================================================================
# 4. replay_admin.py
# ================================================================
cat > "$ADMIN_DIR/replay_admin.py" << 'EOF'
"""Webhook Replay Admin Configuration

This module contains the Django admin configuration for webhook replay models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Q
from django.utils import timezone
import json

from ..models import (
    WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ..models.constants import ReplayStatus


@admin.register(WebhookReplay)
class WebhookReplayAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookReplay model."""

    list_display = ['original_log', 'replayed_by', 'reason', 'status', 'replayed_at', 'created_at']
    list_filter = ['status', 'reason', 'created_at', 'replayed_by', 'original_log__endpoint__status']
    search_fields = ['reason', 'original_log__endpoint__label', 'original_log__endpoint__url', 'replayed_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'original_log_preview', 'new_log_preview']
    raw_id_fields = ('original_log', 'new_log', 'replayed_by')

    fieldsets = (
        ('Basic Information', {'fields': ('original_log', 'replayed_by', 'reason', 'status')}),
        ('Replay Results', {'fields': ('new_log', 'replayed_at')}),
        ('Log Details', {'fields': ('original_log_preview', 'new_log_preview'), 'classes': ('collapse',)}),
        ('System Information', {'fields': ('id', 'created_at', 'updated_at'), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'original_log', 'original_log__endpoint', 'original_log__endpoint__owner',
            'new_log', 'new_log__endpoint', 'replayed_by'
        )

    def original_log_preview(self, obj):
        if not obj.original_log:
            return "No original log"
        log = obj.original_log
        return format_html(
            '<div style="background: #f5f5f5; padding: 5px; font-size: 11px;">'
            '<strong>Endpoint:</strong> {}<br><strong>Event:</strong> {}<br>'
            '<strong>Status:</strong> {}<br><strong>Created:</strong> {}</div>',
            log.endpoint.label or log.endpoint.url, log.event_type, log.status,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
    original_log_preview.short_description = 'Original Log'

    def new_log_preview(self, obj):
        if not obj.new_log:
            return "No new log"
        log = obj.new_log
        return format_html(
            '<div style="background: #e8f5e8; padding: 5px; font-size: 11px;">'
            '<strong>Endpoint:</strong> {}<br><strong>Event:</strong> {}<br>'
            '<strong>Status:</strong> {}<br><strong>Created:</strong> {}</div>',
            log.endpoint.label or log.endpoint.url, log.event_type, log.status,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
    new_log_preview.short_description = 'New Log'

    def status_badge(self, obj):
        color_map = {
            ReplayStatus.PENDING: 'orange', ReplayStatus.PROCESSING: 'blue',
            ReplayStatus.COMPLETED: 'green', ReplayStatus.FAILED: 'red', ReplayStatus.CANCELLED: 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.process_replay'):
            actions.append('process_replay')
        if request.user.has_perm('webhooks.cancel_replay'):
            actions.append('cancel_replay')
        if request.user.has_perm('webhooks.delete_replay'):
            actions.append('delete_old_replays')
        return actions

    def process_replay(self, request, queryset):
        from ..services.replay import ReplayService
        service = ReplayService()
        results = []
        for replay in queryset:
            if replay.status in [ReplayStatus.COMPLETED, ReplayStatus.PROCESSING]:
                results.append(f"{replay.id}: Already {replay.status}")
                continue
            try:
                result = service.process_replay(replay)
                results.append(f"{replay.id}: {'Success' if result['success'] else 'Failed'}")
            except Exception as e:
                results.append(f"{replay.id}: Error - {str(e)}")
        self.message_user(request, f"Process results: {'; '.join(results)}")
    process_replay.short_description = 'Process selected replays'

    def cancel_replay(self, request, queryset):
        from ..services.replay import ReplayService
        service = ReplayService()
        canceled_count = 0
        for replay in queryset:
            if replay.status in [ReplayStatus.COMPLETED, ReplayStatus.CANCELLED]:
                continue
            try:
                result = service.cancel_replay(replay, reason="Cancelled from admin")
                if result['success']:
                    canceled_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to cancel replay {replay.id}: {str(e)}", level='error')
        self.message_user(request, f"Successfully canceled {canceled_count} replays.")
    cancel_replay.short_description = 'Cancel selected replays'

    def delete_old_replays(self, request, queryset):
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = 0
        for replay in queryset:
            if replay.created_at < cutoff_date:
                replay.delete()
                deleted_count += 1
        self.message_user(request, f"Successfully deleted {deleted_count} old replays.")
    delete_old_replays.short_description = 'Delete old replays (30+ days)'

    def has_add_permission(self, request):
        return False

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookReplayBatch)
class WebhookReplayBatchAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookReplayBatch model."""

    list_display = ['event_type', 'count', 'status', 'completion_percentage', 'created_at']
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['event_type', 'reason', 'created_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completion_percentage']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ('event_type', 'reason', 'status')}),
        ('Batch Details', {'fields': ('count', 'date_from', 'date_to', 'endpoint_filter', 'status_filter')}),
        ('Processing Information', {'fields': ('completed_at', 'completion_percentage')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related().annotate(
            completed_items=Count('items', filter=Q(items__status=ReplayStatus.COMPLETED)),
            total_items=Count('items')
        )

    def completion_percentage(self, obj):
        total = obj.items.count()
        if total == 0:
            return "0%"
        completed = obj.items.filter(status=ReplayStatus.COMPLETED).count()
        percentage = (completed / total) * 100
        color = 'green' if percentage >= 90 else 'orange' if percentage >= 50 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, percentage)
    completion_percentage.short_description = 'Completion'

    def status_badge(self, obj):
        color_map = {
            ReplayStatus.PENDING: 'orange', ReplayStatus.PROCESSING: 'blue',
            ReplayStatus.COMPLETED: 'green', ReplayStatus.FAILED: 'red', ReplayStatus.CANCELLED: 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.process_replay_batch'):
            actions.append('process_batch')
        if request.user.has_perm('webhooks.cancel_replay_batch'):
            actions.append('cancel_batch')
        return actions

    def process_batch(self, request, queryset):
        from ..services.replay import ReplayService
        service = ReplayService()
        results = []
        for batch in queryset:
            if batch.status in [ReplayStatus.COMPLETED, ReplayStatus.PROCESSING]:
                results.append(f"{batch.batch_id}: Already {batch.status}")
                continue
            try:
                result = service.process_replay_batch(batch)
                results.append(f"{batch.batch_id}: {'Success' if result['success'] else 'Failed'}")
            except Exception as e:
                results.append(f"{batch.batch_id}: Error - {str(e)}")
        self.message_user(request, f"Process results: {'; '.join(results)}")
    process_batch.short_description = 'Process selected replay batches'

    def cancel_batch(self, request, queryset):
        from ..services.replay import ReplayService
        service = ReplayService()
        canceled_count = 0
        for batch in queryset:
            if batch.status in [ReplayStatus.COMPLETED, ReplayStatus.CANCELLED]:
                continue
            try:
                result = service.cancel_replay_batch(batch, reason="Cancelled from admin")
                if result['success']:
                    canceled_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to cancel batch {batch.batch_id}: {str(e)}", level='error')
        self.message_user(request, f"Successfully canceled {canceled_count} replay batches.")
    cancel_batch.short_description = 'Cancel selected replay batches'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookReplayItem)
class WebhookReplayItemAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookReplayItem model."""

    list_display = ['batch', 'original_log', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'batch__event_type']
    search_fields = ['batch__batch_id', 'original_log__endpoint__label', 'original_log__endpoint__url', 'error_message']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ('batch', 'original_log', 'new_log')

    fieldsets = (
        ('Basic Information', {'fields': ('batch', 'original_log', 'status')}),
        ('Replay Results', {'fields': ('new_log', 'replayed_at', 'error_message')}),
        ('System Information', {'fields': ('id', 'created_at', 'updated_at'), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'batch', 'batch__created_by', 'original_log', 'original_log__endpoint',
            'new_log', 'new_log__endpoint'
        )

    def status_badge(self, obj):
        color_map = {
            ReplayStatus.PENDING: 'orange', ReplayStatus.PROCESSING: 'blue',
            ReplayStatus.COMPLETED: 'green', ReplayStatus.FAILED: 'red', ReplayStatus.CANCELLED: 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


WebhookReplayAdmin.list_display = ['original_log', 'replayed_by', 'reason', 'status_badge', 'replayed_at', 'created_at']
WebhookReplayBatchAdmin.list_display = ['event_type', 'count', 'status_badge', 'completion_percentage', 'created_at']
WebhookReplayItemAdmin.list_display = ['batch', 'original_log', 'status_badge', 'created_at']
EOF

echo "✅ replay_admin.py done"

# ================================================================
# 5. template_admin.py
# ================================================================
cat > "$ADMIN_DIR/template_admin.py" << 'EOF'
"""Webhook Template Admin Configuration

This module contains the Django admin configuration for webhook template models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Q
from django.utils import timezone
import json

from ..models import (
    WebhookTemplate, WebhookBatch, WebhookBatchItem, WebhookSecret
)
from ..models.constants import BatchStatus


@admin.register(WebhookTemplate)
class WebhookTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookTemplate model."""

    list_display = ['name', 'is_active', 'usage_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['id', 'created_at', 'usage_count', 'template_preview']
    raw_id_fields = ()

    fieldsets = (
        ('Basic Information', {'fields': ('name', 'description', 'is_active')}),
        ('Template Configuration', {
            'fields': ('payload_template', 'template_preview'),
            'description': 'Configure the Jinja2 template for payload transformation'
        }),
        ('Validation', {'fields': ('schema_validation', 'required_fields')}),
        ('Usage Statistics', {'fields': ('usage_count', 'last_used_at'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related().annotate(usage_count=Count('endpoints'))

    def usage_count(self, obj):
        count = obj.endpoints.count()
        url = reverse('admin:webhooks_webhookendpoint_changelist') + f'?payload_template__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    usage_count.short_description = 'Usage Count'

    def template_preview(self, obj):
        if not obj.payload_template:
            return "No template"
        s = obj.payload_template
        preview = s[:300] + "..." if len(s) > 300 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    template_preview.short_description = 'Template Preview'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.test_template'):
            actions.append('test_template')
        if request.user.has_perm('webhooks.clone_template'):
            actions.append('clone_template')
        return actions

    def test_template(self, request, queryset):
        from ..services.core import TemplateEngine
        engine = TemplateEngine()
        results = []
        for template in queryset:
            try:
                test_payload = {'user_id': 12345, 'user_email': 'test@example.com', 'timestamp': str(timezone.now())}
                engine.render_template(template.payload_template, test_payload)
                results.append(f"{template.name}: Success")
            except Exception as e:
                results.append(f"{template.name}: Error - {str(e)}")
        self.message_user(request, f"Template test results: {'; '.join(results)}")
    test_template.short_description = 'Test selected templates'

    def clone_template(self, request, queryset):
        cloned_count = 0
        for template in queryset:
            try:
                new_template = WebhookTemplate.objects.create(
                    name=f"{template.name} (Clone)", description=template.description,
                    event_type=template.event_type, payload_template=template.payload_template,
                    schema_validation=template.schema_validation, required_fields=template.required_fields,
                    is_active=False, created_by=request.user
                )
                cloned_count += 1
                self.message_user(request, f"Cloned template: {template.name} -> {new_template.name}")
            except Exception as e:
                self.message_user(request, f"Failed to clone template {template.name}: {str(e)}", level='error')
        self.message_user(request, f"Successfully cloned {cloned_count} templates.")
    clone_template.short_description = 'Clone selected templates'

    def save_model(self, request, obj, form, change):
        if obj.payload_template:
            try:
                from ..services.core import TemplateEngine
                engine = TemplateEngine()
                engine.render_template(obj.payload_template, {'test': True})
            except Exception as e:
                raise ValueError(f"Invalid template syntax: {str(e)}")
        super().save_model(request, obj, form, change)

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookBatch)
class WebhookBatchAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookBatch model."""

    list_display = ['batch_id', 'endpoint', 'event_count', 'completion_percentage', 'created_at']
    list_filter = ['created_at', 'endpoint__status', 'endpoint__owner']
    search_fields = ['batch_id', 'endpoint__label', 'endpoint__url', 'endpoint__owner__username']
    readonly_fields = ['id', 'created_at', 'completion_percentage']
    raw_id_fields = ('endpoint',)

    fieldsets = (
        ('Basic Information', {'fields': ('batch_id', 'endpoint')}),
        ('Batch Details', {'fields': ('event_count', 'priority', 'metadata')}),
        ('Processing Information', {'fields': ('started_at', 'completed_at', 'completion_percentage')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('endpoint', 'endpoint__owner').annotate(
            completed_items=Count('items', filter=Q(items__status=BatchStatus.COMPLETED)),
            total_items=Count('items')
        )

    def completion_percentage(self, obj):
        total = obj.items.count()
        if total == 0:
            return "0%"
        completed = obj.items.filter(status=BatchStatus.COMPLETED).count()
        percentage = (completed / total) * 100
        color = 'green' if percentage >= 90 else 'orange' if percentage >= 50 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, percentage)
    completion_percentage.short_description = 'Completion'

    def status_badge(self, obj):
        color_map = {
            BatchStatus.PENDING: 'orange', BatchStatus.PROCESSING: 'blue',
            BatchStatus.COMPLETED: 'green', BatchStatus.FAILED: 'red', BatchStatus.CANCELLED: 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.process_batch'):
            actions.append('process_batch')
        if request.user.has_perm('webhooks.cancel_batch'):
            actions.append('cancel_batch')
        if request.user.has_perm('webhooks.retry_batch'):
            actions.append('retry_batch')
        return actions

    def process_batch(self, request, queryset):
        from ..services.batch import BatchService
        service = BatchService()
        results = []
        for batch in queryset:
            if batch.status in [BatchStatus.COMPLETED, BatchStatus.PROCESSING]:
                results.append(f"{batch.batch_id}: Already {batch.status}")
                continue
            try:
                result = service.process_batch(batch)
                results.append(f"{batch.batch_id}: {'Success' if result['success'] else 'Failed'}")
            except Exception as e:
                results.append(f"{batch.batch_id}: Error - {str(e)}")
        self.message_user(request, f"Process results: {'; '.join(results)}")
    process_batch.short_description = 'Process selected batches'

    def cancel_batch(self, request, queryset):
        from ..services.batch import BatchService
        service = BatchService()
        canceled_count = 0
        for batch in queryset:
            if batch.status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED]:
                continue
            try:
                result = service.cancel_batch(batch, reason="Cancelled from admin")
                if result['success']:
                    canceled_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to cancel batch {batch.batch_id}: {str(e)}", level='error')
        self.message_user(request, f"Successfully canceled {canceled_count} batches.")
    cancel_batch.short_description = 'Cancel selected batches'

    def retry_batch(self, request, queryset):
        from ..services.batch import BatchService
        service = BatchService()
        retried_count = 0
        for batch in queryset:
            try:
                result = service.retry_batch(batch)
                if result['success']:
                    retried_count += result['retry_count']
            except Exception as e:
                self.message_user(request, f"Failed to retry batch {batch.batch_id}: {str(e)}", level='error')
        self.message_user(request, f"Successfully retried {retried_count} items.")
    retry_batch.short_description = 'Retry failed items in selected batches'

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookBatchItem)
class WebhookBatchItemAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookBatchItem model."""

    list_display = ['batch', 'event_data_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['batch__batch_id', 'batch__endpoint__label', 'batch__endpoint__url', 'error_message']
    readonly_fields = ['id', 'created_at', 'event_data_preview']
    raw_id_fields = ('batch', 'delivery_log')

    fieldsets = (
        ('Basic Information', {'fields': ('batch',)}),
        ('Event Data', {'fields': ('event_data_preview', 'delivery_log')}),
        ('Error Information', {'fields': ('error_message',), 'classes': ('collapse',)}),
        ('System Information', {'fields': ('id', 'created_at'), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'batch', 'batch__endpoint', 'batch__created_by', 'delivery_log', 'delivery_log__endpoint'
        )

    def event_data_preview(self, obj):
        if not obj.event_data:
            return "No event data"
        s = json.dumps(obj.event_data, indent=2)
        preview = s[:200] + "..." if len(s) > 200 else s
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    event_data_preview.short_description = 'Event Data'

    def status_badge(self, obj):
        color_map = {
            BatchStatus.PENDING: 'orange', BatchStatus.PROCESSING: 'blue',
            BatchStatus.COMPLETED: 'green', BatchStatus.FAILED: 'red', BatchStatus.CANCELLED: 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, obj.status.title())
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


@admin.register(WebhookSecret)
class WebhookSecretAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookSecret model."""

    list_display = ['endpoint', 'is_active', 'created_at', 'expires_at']
    list_filter = ['is_active', 'created_at', 'expires_at', 'endpoint__status']
    search_fields = ['endpoint__label', 'endpoint__url', 'endpoint__owner__username']
    readonly_fields = ['id', 'created_at', 'secret_hash_preview']
    raw_id_fields = ('endpoint',)

    fieldsets = (
        ('Basic Information', {'fields': ('endpoint', 'is_active')}),
        ('Secret Information', {'fields': ('secret_hash_preview', 'expires_at')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('endpoint', 'endpoint__owner')

    def secret_hash_preview(self, obj):
        if not obj.secret_hash:
            return "No secret hash"
        h = str(obj.secret_hash)
        preview = h[:16] + "..." + h[-16:]
        return format_html('<pre style="background: #f5f5f5; padding: 5px; font-size: 11px;">{}</pre>', preview)
    secret_hash_preview.short_description = 'Secret Hash'

    def status_badge(self, obj):
        color = 'green' if obj.is_active else 'red'
        status = 'Active' if obj.is_active else 'Inactive'
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{}</span>', color, status)
    status_badge.short_description = 'Status'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.has_perm('webhooks.rotate_secret'):
            actions.append('rotate_secret')
        if request.user.has_perm('webhooks.deactivate_secret'):
            actions.append('deactivate_secret')
        return actions

    def rotate_secret(self, request, queryset):
        from ..services.core import SecretRotationService
        service = SecretRotationService()
        rotated_count = 0
        for secret in queryset:
            try:
                new_secret = service.rotate_secret(secret.endpoint)
                rotated_count += 1
                self.message_user(request, f"Rotated secret for {secret.endpoint.label or secret.endpoint.url}: {new_secret[:8]}...")
            except Exception as e:
                self.message_user(request, f"Failed to rotate secret for {secret.endpoint.label or secret.endpoint.url}: {str(e)}", level='error')
        self.message_user(request, f"Successfully rotated {rotated_count} secrets.")
    rotate_secret.short_description = 'Rotate secrets for selected endpoints'

    def deactivate_secret(self, request, queryset):
        deactivated_count = 0
        for secret in queryset:
            if not secret.is_active:
                continue
            secret.is_active = False
            secret.save()
            deactivated_count += 1
            self.message_user(request, f"Deactivated secret for {secret.endpoint.label or secret.endpoint.url}")
        self.message_user(request, f"Successfully deactivated {deactivated_count} secrets.")
    deactivate_secret.short_description = 'Deactivate selected secrets'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('webhooks.change_webhooksecret')

    class Media:
        css = {'all': ('admin/css/webhooks.css',)}


WebhookBatchAdmin.list_display = ['batch_id', 'endpoint', 'event_count', 'status_badge', 'completion_percentage', 'created_at']
WebhookBatchItemAdmin.list_display = ['batch', 'event_data_preview', 'status_badge', 'created_at']
WebhookSecretAdmin.list_display = ['endpoint', 'status_badge', 'created_at', 'expires_at']
EOF

echo "✅ template_admin.py done"

# ================================================================
# Clear Python cache
# ================================================================
find api/webhooks/admin/__pycache__ -name "*.pyc" -delete 2>/dev/null || true
echo "🗑️  Cleared pycache"

echo ""
echo "============================================"
echo "✅ ALL FILES FIXED! Now run:"
echo "   python manage.py runserver"
echo "============================================"
