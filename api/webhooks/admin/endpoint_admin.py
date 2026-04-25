"""Webhook Endpoint Admin Configuration

This module contains the Django admin configuration for the WebhookEndpoint model.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone

from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..models.constants import WebhookStatus


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookEndpoint model."""

    list_display = [
        'label', 'url', 'status', 'http_method',
        'success_rate', 'last_triggered_at', 'owner'
    ]

    list_filter = [
        'status', 'http_method', 'verify_ssl', 'owner'
    ]

    search_fields = [
        'label', 'url', 'description',
        'owner__username', 'owner__email'
    ]

    readonly_fields = ['id', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'label', 'url', 'description', 'owner', 'status'
            )
        }),
        ('Configuration', {
            'fields': (
                'http_method', 'timeout_seconds', 'max_retries',
                'verify_ssl', 'rate_limit_per_min'
            )
        }),
        ('Security', {
            'fields': ('secret_key', 'ip_whitelist', 'headers')
        }),
        ('Template', {
            'fields': ('payload_template', 'version')
        }),
        ('Statistics', {
            'fields': ('last_triggered_at',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        })
    )

    raw_id_fields = ('owner', 'payload_template')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('owner', 'payload_template')

    def success_rate(self, obj):
        """Calculate success rate as a percentage."""
        if obj.total_deliveries == 0:
            return "0%"

        rate = (obj.success_deliveries / obj.total_deliveries) * 100
        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    success_rate.short_description = 'Success Rate'
    success_rate.admin_order_field = 'success_rate'

    def get_subscriptions_count(self, obj):
        """Get the number of active subscriptions."""
        count = obj.subscriptions.filter(is_active=True).count()
        url = reverse('admin:webhooks_webhooksubscription_changelist') + f'?endpoint__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    get_subscriptions_count.short_description = 'Active Subscriptions'

    def health_status(self, obj):
        """Display health status based on recent deliveries."""
        recent_deliveries = obj.delivery_logs.filter(
            created_at__gte=obj.created_at.replace(hour=0, minute=0, second=0)
        )

        if not recent_deliveries.exists():
            return format_html('<span style="color: gray;">No Data</span>')

        success_count = recent_deliveries.filter(status='success').count()
        total_count = recent_deliveries.count()
        rate = (success_count / total_count) * 100

        if rate >= 95:
            color, status = 'green', 'Excellent'
        elif rate >= 85:
            color, status = 'blue', 'Good'
        elif rate >= 70:
            color, status = 'orange', 'Fair'
        else:
            color, status = 'red', 'Poor'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ({:.1f}%)</span>',
            color, status, rate
        )
    health_status.short_description = 'Health Status'

    def get_actions(self, request):
        """Add custom actions."""
        actions = super().get_actions(request)

        if request.user.has_perm('webhooks.test_webhook'):
            actions.append('test_webhook')

        if request.user.has_perm('webhooks.rotate_secret'):
            actions.append('rotate_secret')

        if request.user.has_perm('webhooks.check_health'):
            actions.append('check_health')

        return actions

    def test_webhook(self, request, queryset):
        """Test webhook endpoints."""
        from ..services.core import DispatchService

        service = DispatchService()
        results = []

        for endpoint in queryset:
            try:
                result = service.emit(
                    endpoint=endpoint,
                    event_type='webhook.test',
                    payload={'test': True, 'timestamp': str(timezone.now())}
                )
                results.append(f"{endpoint.url}: {'Success' if result else 'Failed'}")
            except Exception as e:
                results.append(f"{endpoint.url}: Error - {str(e)}")

        self.message_user(request, f"Test results: {'; '.join(results)}")
    test_webhook.short_description = 'Test selected webhook endpoints'

    def rotate_secret(self, request, queryset):
        """Rotate secrets for selected endpoints."""
        from ..services.core import SecretRotationService

        service = SecretRotationService()
        rotated_count = 0

        for endpoint in queryset:
            try:
                new_secret = service.rotate_secret(endpoint)
                rotated_count += 1
                self.message_user(
                    request,
                    f"Rotated secret for {endpoint.url}: {new_secret[:8]}..."
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to rotate secret for {endpoint.url}: {str(e)}",
                    level='error'
                )

        self.message_user(request, f"Successfully rotated {rotated_count} secrets.")
    rotate_secret.short_description = 'Rotate secrets for selected endpoints'

    def check_health(self, request, queryset):
        """Check health of selected endpoints."""
        from ..services.analytics import HealthMonitorService

        service = HealthMonitorService()
        results = []

        for endpoint in queryset:
            try:
                health = service.check_endpoint_health(endpoint)
                status = 'Healthy' if health['is_healthy'] else 'Unhealthy'
                results.append(f"{endpoint.url}: {status}")
            except Exception as e:
                results.append(f"{endpoint.url}: Error - {str(e)}")

        self.message_user(request, f"Health check results: {'; '.join(results)}")
    check_health.short_description = 'Check health of selected endpoints'

    def save_model(self, request, obj):
        """Override save to handle secret key generation."""
        if not obj.pk and not obj.secret_key:
            from api.webhooks.models_flat import _generate_secret_key
            obj.secret_key = _generate_secret_key()

        super().save_model(request, obj)

    def delete_model(self, request, obj):
        """Override delete to handle cascade deletion."""
        self.message_user(
            request,
            f"Deleted webhook endpoint: {obj.label or obj.url}",
            level='warning'
        )
        super().delete_model(request, obj)

    class Media:
        css = {
            'all': ('admin/css/webhooks.css',)
        }


class WebhookSubscriptionInline(admin.TabularInline):
    """Inline admin for WebhookSubscription model."""

    model = WebhookSubscription
    extra = 0
    readonly_fields = ['id', 'updated_at']
    fields = ('event_type', 'is_active', 'filter_config')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('endpoint')


class WebhookDeliveryLogInline(admin.TabularInline):
    """Inline admin for WebhookDeliveryLog model."""

    model = WebhookDeliveryLog
    extra = 0
    readonly_fields = [
        'id', 'updated_at', 'payload', 'request_headers', 'signature'
    ]
    fields = (
        'event_type', 'status', 'http_status_code',
        'duration_ms', 'attempt_number'
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('webhooks.delete_deliverylog')


WebhookEndpointAdmin.inlines = [
    WebhookSubscriptionInline,
    WebhookDeliveryLogInline
]
