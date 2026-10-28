# api/admin_panel/admin/config_admin.py
"""Django Admin for Config models (SystemConfig, APIRateConfig, EmailTemplate)."""
from django.contrib import admin
from django.utils.html import format_html
from ..models.config import SystemConfig, APIRateConfig, EmailTemplate


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'group', 'value_type', 'value_preview', 'is_public', 'is_readonly', 'updated_at']
    list_filter = ['group', 'value_type', 'is_public', 'is_readonly', 'is_encrypted']
    search_fields = ['key', 'label', 'description']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
    ordering = ['group', 'key']
    list_per_page = 50

    fieldsets = (
        ('Key & Value', {
            'fields': ('key', 'value', 'value_type', 'group', 'label', 'description')
        }),
        ('Flags', {
            'fields': ('is_public', 'is_encrypted', 'is_readonly', 'validation_regex')
        }),
        ('Audit', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Value Preview')
    def value_preview(self, obj):
        if obj.is_encrypted:
            return format_html('<span style="color:gray;">***</span>')
        val = obj.value[:60]
        return format_html('<code>{}</code>', val + ('…' if len(obj.value) > 60 else ''))

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['clear_cache_for_selected']

    @admin.action(description='Clear cache for selected configs')
    def clear_cache_for_selected(self, request, queryset):
        from django.core.cache import cache
        for config in queryset:
            cache.delete(f'admin_panel:config:{config.key}')
        cache.delete('admin_panel:config_all')
        self.message_user(request, f'Cache cleared for {queryset.count()} config(s).')


@admin.register(APIRateConfig)
class APIRateConfigAdmin(admin.ModelAdmin):
    list_display = ['endpoint_pattern', 'method', 'limit', 'window_seconds', 'rate_per_minute', 'is_active']
    list_filter = ['is_active', 'method', 'applies_to_admins']
    search_fields = ['endpoint_pattern', 'description']
    readonly_fields = ['rate_per_minute', 'created_at', 'updated_at']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'subject', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['key', 'name', 'subject']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
    ordering = ['key']

    fieldsets = (
        ('Template', {'fields': ('key', 'name', 'subject', 'is_active')}),
        ('Content', {'fields': ('body_html', 'body_text', 'variables')}),
        ('Sender', {'fields': ('from_name', 'from_email', 'reply_to')}),
        ('Audit', {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)