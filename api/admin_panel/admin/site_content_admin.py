# api/admin_panel/admin/site_content_admin.py
"""Django admin for SiteContent and SiteNotification."""
from django.contrib import admin
from ..models.core import SiteContent, SiteNotification


# @admin.register(SiteContent) — registered in admin.py
class SiteContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'identifier', 'content_type', 'language', 'is_active', 'order', 'updated_at']
    list_filter = ['content_type', 'is_active', 'language']
    search_fields = ['title', 'identifier', 'content']
    list_editable = ['is_active', 'order']
    prepopulated_fields = {'identifier': ('title',)}
    ordering = ['order', 'title']
    fieldsets = (
        ('Content', {'fields': ('identifier', 'title', 'content', 'content_type', 'language')}),
        ('Status', {'fields': ('is_active', 'order')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'meta_keywords'), 'classes': ('collapse',)}),
    )

    actions = ['activate_selected', 'deactivate_selected']

    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
    activate_selected.short_description = 'Activate selected content'

    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_selected.short_description = 'Deactivate selected content'