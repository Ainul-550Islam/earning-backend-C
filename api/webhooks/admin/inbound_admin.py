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
