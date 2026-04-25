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
