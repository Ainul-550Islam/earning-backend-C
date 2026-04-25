"""Webhook Subscription Admin Configuration

This module contains the Django admin configuration for the WebhookSubscription model.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone

from ..models import WebhookSubscription, WebhookFilter
from ..models.constants import WebhookStatus


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    """Admin configuration for WebhookSubscription model."""

    list_display = [
        'endpoint',
        'event_type',
        'is_active',
        'filter_count',
        'created_at',
        'updated_at'
    ]

    list_filter = [
        'is_active',
        'event_type',
        'created_at',
        'endpoint__status',
        'endpoint__owner'
    ]

    search_fields = [
        'event_type',
        'endpoint__label',
        'endpoint__url',
        'endpoint__owner__username'
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]

    raw_id_fields = ('endpoint',)

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'endpoint',
                'event_type',
                'is_active'
            )
        }),
        ('Filter Configuration', {
            'fields': (
                'filter_config',
            ),
            'description': 'Configure filters to control when this subscription triggers'
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('endpoint', 'endpoint__owner')

    def filter_count(self, obj):
        """Display the number of filters applied to this subscription."""
        if not obj.filter_config:
            return "0"

        filter_count = len(obj.filter_config)
        color = 'green' if filter_count <= 2 else 'orange' if filter_count <= 5 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, filter_count
        )
    filter_count.short_description = 'Filters'

    def get_endpoint_status(self, obj):
        """Display the status of the associated endpoint."""
        status = obj.endpoint.status
        color_map = {
            WebhookStatus.ACTIVE: 'green',
            WebhookStatus.INACTIVE: 'gray',
            WebhookStatus.SUSPENDED: 'red',
            WebhookStatus.PAUSED: 'orange'
        }
        color = color_map.get(status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status.title()
        )
    get_endpoint_status.short_description = 'Endpoint Status'

    def get_delivery_count(self, obj):
        """Get the number of deliveries for this subscription."""
        count = obj.endpoint.delivery_logs.filter(
            event_type=obj.event_type
        ).count()

        url = reverse('admin:webhooks_webhookdeliverylog_changelist') + \
               f'?endpoint__id__exact={obj.endpoint.id}&event_type__exact={obj.event_type}'

        return format_html(
            '<a href="{}">{}</a>',
            url, count
        )
    get_delivery_count.short_description = 'Deliveries'

    def get_success_rate(self, obj):
        """Calculate success rate for this subscription."""
        deliveries = obj.endpoint.delivery_logs.filter(event_type=obj.event_type)

        if not deliveries.exists():
            return "N/A"

        success_count = deliveries.filter(status='success').count()
        total_count = deliveries.count()
        rate = (success_count / total_count) * 100

        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    get_success_rate.short_description = 'Success Rate'

    def get_actions(self, request):
        """Add custom actions."""
        actions = super().get_actions(request)

        if request.user.has_perm('webhooks.toggle_subscription'):
            actions.append('toggle_active')

        if request.user.has_perm('webhooks.test_subscription'):
            actions.append('test_subscription')

        return actions

    def toggle_active(self, request, queryset):
        """Toggle active status for selected subscriptions."""
        updated_count = 0

        for subscription in queryset:
            subscription.is_active = not subscription.is_active
            subscription.save()
            updated_count += 1

            status = 'activated' if subscription.is_active else 'deactivated'
            self.message_user(
                request,
                f"{subscription.event_type} subscription for {subscription.endpoint.label or subscription.endpoint.url} {status}"
            )

        self.message_user(request, f"Successfully updated {updated_count} subscriptions.")
    toggle_active.short_description = 'Toggle active status'

    def test_subscription(self, request, queryset):
        """Test selected subscriptions."""
        from ..services.core import DispatchService

        service = DispatchService()
        results = []

        for subscription in queryset:
            try:
                result = service.emit(
                    endpoint=subscription.endpoint,
                    event_type=subscription.event_type,
                    payload={
                        'test': True,
                        'subscription_id': str(subscription.id),
                        'timestamp': str(timezone.now())
                    }
                )
                status = 'Success' if result else 'Failed'
                results.append(f"{subscription.event_type} for {subscription.endpoint.label or subscription.endpoint.url}: {status}")
            except Exception as e:
                results.append(f"{subscription.event_type} for {subscription.endpoint.label or subscription.endpoint.url}: Error - {str(e)}")

        self.message_user(request, f"Test results: {'; '.join(results)}")
    test_subscription.short_description = 'Test selected subscriptions'

    def save_model(self, request, obj, form, change):
        """Override save to validate filter configuration."""
        if obj.filter_config:
            try:
                from ..services.filtering import FilterService
                service = FilterService()
                service.validate_filter_config(obj.filter_config)
            except Exception as e:
                raise ValueError(f"Invalid filter configuration: {str(e)}")

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """Override delete to handle cascade deletion."""
        self.message_user(
            request,
            f"Deleted webhook subscription: {obj.event_type} for {obj.endpoint.label or obj.endpoint.url}",
            level='warning'
        )
        super().delete_model(request, obj)

    class Media:
        css = {
            'all': ('admin/css/webhooks.css',)
        }

WebhookSubscriptionAdmin.inlines = []
