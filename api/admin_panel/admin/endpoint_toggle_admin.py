# api/admin_panel/admin/endpoint_toggle_admin.py
"""Django admin for EndpointToggle."""
from django.contrib import admin
from ..endpoint_toggle import EndpointToggle


@admin.register(EndpointToggle)
class EndpointToggleAdmin(admin.ModelAdmin):
    list_display = ['path', 'method', 'group', 'label', 'is_enabled', 'updated_at']
    list_filter = ['is_enabled', 'group', 'method']
    search_fields = ['path', 'label', 'group']
    list_editable = ['is_enabled']
    ordering = ['group', 'path']

    actions = ['enable_selected', 'disable_selected']

    def enable_selected(self, request, queryset):
        for toggle in queryset:
            toggle.is_enabled = True
            toggle.save()
    enable_selected.short_description = 'Enable selected endpoints'

    def disable_selected(self, request, queryset):
        for toggle in queryset:
            toggle.is_enabled = False
            toggle.save()
    disable_selected.short_description = 'Disable selected endpoints'