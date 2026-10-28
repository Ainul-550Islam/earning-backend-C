# api/admin_panel/admin/maintenance_admin.py
"""Django Admin for MaintenanceWindow."""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.config import MaintenanceWindow


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'maintenance_type', 'start_at', 'end_at',
        'status_badge', 'notify_users', 'duration_minutes', 'created_by'
    ]
    list_filter = ['maintenance_type', 'is_active', 'notify_users']
    search_fields = ['title', 'message', 'internal_note']
    readonly_fields = ['is_currently_active', 'duration_minutes', 'created_at', 'updated_at']
    raw_id_fields = ['created_by']
    date_hierarchy = 'start_at'

    fieldsets = (
        ('Window Details', {
            'fields': ('title', 'maintenance_type', 'start_at', 'end_at')
        }),
        ('Messages', {
            'fields': ('message', 'internal_note')
        }),
        ('Notifications', {
            'fields': ('notify_users', 'notify_before_minutes')
        }),
        ('Status', {
            'fields': ('is_active', 'is_currently_active', 'duration_minutes')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.is_currently_active:
            return format_html('<span style="color:red;font-weight:bold;">🔴 ACTIVE</span>')
        now = timezone.now()
        if obj.start_at > now:
            return format_html('<span style="color:orange;">⏳ Upcoming</span>')
        return format_html('<span style="color:green;">✅ Ended</span>')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['activate_windows', 'deactivate_windows']

    @admin.action(description='Activate selected maintenance windows')
    def activate_windows(self, request, queryset):
        from django.core.cache import cache
        for window in queryset:
            window.is_active = True
            window.save(update_fields=['is_active'])
            cache.set('admin_panel:maintenance_mode_active', True, 86400)
            cache.set('admin_panel:maintenance_message', window.message, 86400)
        self.message_user(request, f'{queryset.count()} window(s) activated.')

    @admin.action(description='Deactivate selected maintenance windows')
    def deactivate_windows(self, request, queryset):
        from django.core.cache import cache
        queryset.update(is_active=False)
        if not MaintenanceWindow.objects.filter(is_active=True).exists():
            cache.delete('admin_panel:maintenance_mode_active')
        self.message_user(request, f'{queryset.count()} window(s) deactivated.')