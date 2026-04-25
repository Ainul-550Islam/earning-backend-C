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
