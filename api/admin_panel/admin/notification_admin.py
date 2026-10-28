# api/admin_panel/admin/notification_admin.py
"""Django admin for SiteNotification."""
from django.contrib import admin
from ..models.core import SiteNotification


# @admin.register(SiteNotification) — registered in admin.py
class SiteNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'notification_type', 'is_active', 'show_on_login', 'priority', 'start_date', 'end_date']
    list_filter = ['notification_type', 'is_active', 'show_on_login']
    search_fields = ['title', 'message']
    list_editable = ['is_active', 'priority']
    ordering = ['-priority', '-created_at']
    fieldsets = (
        ('Content', {'fields': ('title', 'message', 'notification_type')}),
        ('Visibility', {'fields': ('is_active', 'show_on_login', 'priority', 'start_date', 'end_date')}),
    )

    actions = ['activate_selected', 'deactivate_selected']

    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
    activate_selected.short_description = 'Activate selected notifications'

    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_selected.short_description = 'Deactivate selected notifications'