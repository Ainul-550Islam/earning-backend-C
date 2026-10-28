# api/djoyalty/admin/notification_admin.py
"""Django Admin for Notification models।"""
from django.contrib import admin
from ..models.notifications import NotificationCenter, NotificationTemplate, NotificationPreference


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'channel', 'priority', 'is_active']
    list_filter = ['channel', 'priority', 'is_active']
    search_fields = ['name', 'event_type']
    list_editable = ['is_active']


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'customer', 'in_app_enabled', 'push_enabled',
        'email_enabled', 'sms_enabled', 'max_per_day',
    ]
    list_filter = ['push_enabled', 'sms_enabled', 'email_enabled']
    search_fields = ['customer__code', 'customer__email']
    raw_id_fields = ['customer']


@admin.register(NotificationCenter)
class NotificationCenterAdmin(admin.ModelAdmin):
    list_display = [
        'customer', 'notification_type', 'title_preview',
        'channel', 'is_read', 'priority', 'created_at',
    ]
    list_filter = ['notification_type', 'channel', 'is_read', 'priority']
    search_fields = ['customer__code', 'title', 'body']
    readonly_fields = ['created_at', 'read_at', 'sent_at']
    date_hierarchy = 'created_at'
    raw_id_fields = ['customer']

    def title_preview(self, obj):
        return obj.title[:50]
    title_preview.short_description = 'Title'

    actions = ['mark_as_read']

    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{updated} notifications marked as read.')
    mark_as_read.short_description = 'Mark selected as read'
