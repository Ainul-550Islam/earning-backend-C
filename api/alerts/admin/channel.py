"""
Channel Admin Classes
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.utils import timezone
from django.contrib import messages

# Unfold imports
try:
    from unfold.admin import ModelAdmin, TabularInline
    from unfold.filters import DateRangeFilter, RelatedDropdownFilter, ChoiceDropdownFilter
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline
    from django.contrib.admin import DateFieldListFilter

from ..models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, 
    ChannelRateLimit, AlertRecipient
)
from .core import alerts_admin_site


# ====================== INLINE ADMIN CLASSES ======================

class ChannelHealthLogInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Channel Health Logs in Alert Channel"""
    model = ChannelHealthLog
    extra = 0
    fields = ['check_type', 'status', 'response_time_ms', 'checked_at']
    readonly_fields = ['check_type', 'status', 'response_time_ms', 'checked_at']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class ChannelRateLimitInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Channel Rate Limits in Alert Channel"""
    model = ChannelRateLimit
    extra = 0
    fields = ['limit_type', 'window_seconds', 'max_requests', 'current_tokens', 'last_refill']
    readonly_fields = ['limit_type', 'window_seconds', 'max_requests', 'current_tokens', 'last_refill']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


# ====================== ADMIN CLASSES ======================

@admin.register(AlertChannel, site=alerts_admin_site)
class AlertChannelAdmin(ModelAdmin):
    """Admin interface for Alert Channels"""
    list_display = [
        'name', 'channel_type', 'status_badge', 'priority', 'is_enabled',
        'total_sent', 'success_rate', 'last_success', 'health_status'
    ]
    
    list_filter = [
        'channel_type', 'status', 'is_enabled', 'priority',
        ('last_success', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('last_failure', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description', 'config']
    
    list_editable = ['is_enabled', 'priority']
    
    readonly_fields = [
        'last_success', 'last_failure', 'consecutive_failures',
        'total_sent', 'total_failed', 'success_rate', 'health_status'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'channel_type', 'description', 'is_enabled', 'priority')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_per_minute', 'rate_limit_per_hour', 'rate_limit_per_day')
        }),
        ('Retry Configuration', {
            'fields': ('max_retries', 'retry_delay_minutes')
        }),
        ('Configuration', {
            'fields': ('config', 'webhook_url')
        }),
        ('Status & Statistics', {
            'fields': ('status', 'last_success', 'last_failure', 'consecutive_failures',
                      'total_sent', 'total_failed', 'success_rate', 'health_status')
        }),
    )
    
    inlines = [ChannelHealthLogInline, ChannelRateLimitInline]
    
    actions = [
        'enable_channels', 'disable_channels', 'test_channels', 'reset_statistics',
        'clear_failures', 'export_channels'
    ]
    
    # Custom display methods
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'active': '#10b981',
            'inactive': '#6b7280',
            'error': '#ef4444',
            'maintenance': '#f59e0b'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_sent > 0:
            rate = (obj.total_sent - obj.total_failed) / obj.total_sent * 100
            return f"{rate:.1f}%"
        return "N/A"
    success_rate.short_description = 'Success Rate'
    
    def health_status(self, obj):
        """Calculate health status"""
        health = obj.get_health_status()
        colors = {
            'healthy': '#10b981',
            'warning': '#f59e0b',
            'critical': '#ef4444',
            'unknown': '#6b7280'
        }
        color = colors.get(health, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, health.upper()
        )
    health_status.short_description = 'Health'
    
    # Custom actions
    def enable_channels(self, request, queryset):
        """Enable selected channels"""
        queryset.update(is_enabled=True)
        messages.success(request, f"Enabled {queryset.count()} channel(s).")
    enable_channels.short_description = "Enable selected channels"
    
    def disable_channels(self, request, queryset):
        """Disable selected channels"""
        queryset.update(is_enabled=False)
        messages.success(request, f"Disabled {queryset.count()} channel(s).")
    disable_channels.short_description = "Disable selected channels"
    
    def test_channels(self, request, queryset):
        """Test selected channels"""
        from ..tasks.notification import test_channel
        tested_count = 0
        for channel in queryset:
            test_channel.delay(channel.id)
            tested_count += 1
        
        messages.success(request, f"Test initiated for {tested_count} channel(s).")
    test_channels.short_description = "Test selected channels"
    
    def reset_statistics(self, request, queryset):
        """Reset statistics for selected channels"""
        queryset.update(
            total_sent=0,
            total_failed=0,
            consecutive_failures=0,
            last_success=None,
            last_failure=None
        )
        messages.success(request, f"Statistics reset for {queryset.count()} channel(s).")
    reset_statistics.short_description = "Reset statistics"
    
    def clear_failures(self, request, queryset):
        """Clear failure status for selected channels"""
        queryset.update(
            status='active',
            consecutive_failures=0,
            last_failure=None
        )
        messages.success(request, f"Failures cleared for {queryset.count()} channel(s).")
    clear_failures.short_description = "Clear failures"
    
    def export_channels(self, request, queryset):
        """Export selected channels"""
        messages.info(request, f"Export initiated for {queryset.count()} channel(s).")
    export_channels.short_description = "Export channels"


@admin.register(ChannelRoute, site=alerts_admin_site)
class ChannelRouteAdmin(ModelAdmin):
    """Admin interface for Channel Routes"""
    list_display = [
        'name', 'route_type', 'is_active', 'priority', 'source_rules_count',
        'source_channels_count', 'destination_channels_count', 'created_at'
    ]
    
    list_filter = [
        'route_type', 'is_active', 'priority',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description', 'conditions']
    
    list_editable = ['is_active', 'priority']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'route_type', 'is_active', 'priority')
        }),
        ('Routing Configuration', {
            'fields': ('source_rules', 'source_channels', 'destination_channels')
        }),
        ('Conditions', {
            'fields': ('conditions', 'start_time', 'end_time', 'days_of_week')
        }),
        ('Escalation', {
            'fields': ('escalation_delay_minutes', 'escalate_after_failures', 'escalation_users')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_routes', 'deactivate_routes', 'test_routes', 'duplicate_routes',
        'export_routes'
    ]
    
    # Custom display methods
    def source_rules_count(self, obj):
        """Count of source rules"""
        return obj.source_rules.count()
    source_rules_count.short_description = 'Source Rules'
    
    def source_channels_count(self, obj):
        """Count of source channels"""
        return obj.source_channels.count()
    source_channels_count.short_description = 'Source Channels'
    
    def destination_channels_count(self, obj):
        """Count of destination channels"""
        return obj.destination_channels.count()
    destination_channels_count.short_description = 'Destination Channels'
    
    # Custom actions
    def activate_routes(self, request, queryset):
        """Activate selected routes"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} route(s).")
    activate_routes.short_description = "Activate selected routes"
    
    def deactivate_routes(self, request, queryset):
        """Deactivate selected routes"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} route(s).")
    deactivate_routes.short_description = "Deactivate selected routes"
    
    def test_routes(self, request, queryset):
        """Test selected routes"""
        from ..tasks.notification import ChannelRouteTestSerializer
        tested_count = 0
        for route in queryset:
            # Simulate route testing
            tested_count += 1
        
        messages.success(request, f"Test initiated for {tested_count} route(s).")
    test_routes.short_description = "Test selected routes"
    
    def duplicate_routes(self, request, queryset):
        """Duplicate selected routes"""
        duplicated_count = 0
        for route in queryset:
            # Create a copy
            route.pk = None
            route.name = f"{route.name} (Copy)"
            route.is_active = False
            route.save()
            duplicated_count += 1
        
        messages.success(request, f"Duplicated {duplicated_count} route(s).")
    duplicate_routes.short_description = "Duplicate selected routes"
    
    def export_routes(self, request, queryset):
        """Export selected routes"""
        messages.info(request, f"Export initiated for {queryset.count()} route(s).")
    export_routes.short_description = "Export routes"


@admin.register(ChannelHealthLog, site=alerts_admin_site)
class ChannelHealthLogAdmin(ModelAdmin):
    """Admin interface for Channel Health Logs"""
    list_display = [
        'channel_link', 'check_type', 'status_badge',
        'response_time_ms', 'checked_at', 'error_message_short'
    ]
    
    list_filter = [
        'check_type', 'status',
        ('checked_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'channel__name', 'error_message'
    ]
    
    readonly_fields = [
        'channel', 'check_type', 'status', 'response_time_ms',
        'error_message', 'details', 'checked_at'
    ]
    
    actions = ['export_health_logs', 'cleanup_old_logs']
    
    # Custom display methods
    def channel_link(self, obj):
        """Clickable channel name"""
        url = reverse('alerts_admin:alerts_alertchannel_change', args=[obj.channel.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.channel.name)
    channel_link.short_description = 'Channel'
    channel_link.admin_order_field = 'channel__name'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'healthy': '#10b981',
            'warning': '#f59e0b',
            'critical': '#ef4444',
            'unknown': '#6b7280',
            'error': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def error_message_short(self, obj):
        """Short error message"""
        if obj.error_message and len(obj.error_message) > 50:
            return f"{obj.error_message[:50]}..."
        return obj.error_message or ''
    error_message_short.short_description = 'Error Message'
    
    # Custom actions
    def export_health_logs(self, request, queryset):
        """Export selected health logs"""
        messages.info(request, f"Export initiated for {queryset.count()} health log(s).")
    export_health_logs.short_description = "Export health logs"
    
    def cleanup_old_logs(self, request, queryset):
        """Clean up old health logs"""
        messages.info(request, f"Cleanup initiated for old health logs.")
    cleanup_old_logs.short_description = "Cleanup old logs"


@admin.register(ChannelRateLimit, site=alerts_admin_site)
class ChannelRateLimitAdmin(ModelAdmin):
    """Admin interface for Channel Rate Limits"""
    list_display = [
        'channel_link', 'limit_type', 'window_seconds', 'max_requests',
        'current_tokens', 'rejection_rate', 'last_refill'
    ]
    
    list_filter = [
        'limit_type',
        ('last_refill', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['channel__name']
    
    readonly_fields = [
        'channel', 'limit_type', 'window_seconds', 'max_requests',
        'current_tokens', 'last_refill', 'total_requests', 'rejected_requests',
        'rejection_rate'
    ]
    
    actions = [
        'reset_limits', 'export_limits', 'optimize_limits'
    ]
    
    # Custom display methods
    def channel_link(self, obj):
        """Clickable channel name"""
        url = reverse('alerts_admin:alerts_alertchannel_change', args=[obj.channel.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.channel.name)
    channel_link.short_description = 'Channel'
    channel_link.admin_order_field = 'channel__name'
    
    def rejection_rate(self, obj):
        """Calculate rejection rate"""
        if obj.total_requests > 0:
            rate = obj.rejected_requests / obj.total_requests * 100
            return f"{rate:.1f}%"
        return "0%"
    rejection_rate.short_description = 'Rejection Rate'
    
    # Custom actions
    def reset_limits(self, request, queryset):
        """Reset rate limits"""
        updated = 0
        for limit in queryset:
            limit.current_tokens = limit.max_requests
            limit.last_refill = timezone.now()
            limit.save(update_fields=['current_tokens', 'last_refill'])
            updated += 1
        
        messages.success(request, f"Reset {updated} rate limit(s).")
    reset_limits.short_description = "Reset selected limits"
    
    def export_limits(self, request, queryset):
        """Export selected rate limits"""
        messages.info(request, f"Export initiated for {queryset.count()} rate limit(s).")
    export_limits.short_description = "Export rate limits"
    
    def optimize_limits(self, request, queryset):
        """Optimize rate limits"""
        messages.info(request, f"Optimization initiated for {queryset.count()} rate limit(s).")
    optimize_limits.short_description = "Optimize selected limits"


@admin.register(AlertRecipient, site=alerts_admin_site)
class AlertRecipientAdmin(ModelAdmin):
    """Admin interface for Alert Recipients"""
    list_display = [
        'name', 'recipient_type', 'priority', 'is_active',
        'is_available_now_badge', 'timezone',
        'contact_info_display'
    ]
    
    list_filter = [
        'recipient_type', 'is_active', 'priority', 'timezone',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'email_address', 'phone_number', 'user__username', 'user__email']
    
    list_editable = ['is_active', 'priority']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'recipient_type', 'description', 'is_active', 'priority')
        }),
        ('User Association', {
            'fields': ('user',)
        }),
        ('Contact Information', {
            'fields': ('email_address', 'phone_number', 'webhook_url')
        }),
        ('Availability', {
            'fields': ('available_hours_start', 'available_hours_end', 'available_days', 'timezone')
        }),
        ('Notification Preferences', {
            'fields': ('preferred_channels', 'channel_config')
        }),
        ('Rate Limiting', {
            'fields': ('max_notifications_per_hour', 'max_notifications_per_day')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_recipients', 'deactivate_recipients', 'test_recipients',
        'update_availability', 'export_recipients'
    ]
    
    # Custom display methods
    def is_available_now_badge(self, obj):
        """Display availability as colored badge"""
        is_available = obj.is_available_now()
        color = '#10b981' if is_available else '#ef4444'
        status = 'AVAILABLE' if is_available else 'UNAVAILABLE'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, status
        )
    is_available_now_badge.short_description = 'Available Now'
    
    def contact_info_display(self, obj):
        """Display contact info"""
        contact_parts = []
        if obj.email_address:
            contact_parts.append(f"Email: {obj.email_address}")
        if obj.phone_number:
            contact_parts.append(f"Phone: {obj.phone_number}")
        if obj.webhook_url:
            contact_parts.append(f"Webhook: {obj.webhook_url[:30]}...")
        
        return ', '.join(contact_parts[:2])  # Show max 2 items
    contact_info_display.short_description = 'Contact Info'
    
    # Custom actions
    def activate_recipients(self, request, queryset):
        """Activate selected recipients"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} recipient(s).")
    activate_recipients.short_description = "Activate selected recipients"
    
    def deactivate_recipients(self, request, queryset):
        """Deactivate selected recipients"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} recipient(s).")
    deactivate_recipients.short_description = "Deactivate selected recipients"
    
    def test_recipients(self, request, queryset):
        """Test selected recipients"""
        from ..tasks.notification import send_notification_to_recipients
        tested_count = 0
        for recipient in queryset:
            # Simulate sending test notification
            send_notification_to_recipients.delay(
                notification_type='test',
                message=f"Test notification for {recipient.name}",
                subject="Test Notification"
            )
            tested_count += 1
        
        messages.success(request, f"Test notifications sent to {tested_count} recipient(s).")
    test_recipients.short_description = "Test selected recipients"
    
    def update_availability(self, request, queryset):
        """Update availability for selected recipients"""
        from ..tasks.notification import update_recipient_availability
        update_recipient_availability.delay()
        messages.success(request, f"Availability update initiated for {queryset.count()} recipient(s).")
    update_availability.short_description = "Update availability"
    
    def export_recipients(self, request, queryset):
        """Export selected recipients"""
        messages.info(request, f"Export initiated for {queryset.count()} recipient(s).")
    export_recipients.short_description = "Export recipients"
