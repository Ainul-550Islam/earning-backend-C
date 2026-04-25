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
