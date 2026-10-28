# api/admin_panel/admin/activity_admin.py
"""Django admin for activity models."""
from django.contrib import admin
from ..models.activity import AdminActivity, AdminSession, AdminNote, AdminBookmark, AdminSearch


@admin.register(AdminActivity)
class AdminActivityAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'model_name', 'object_id', 'status', 'ip', 'created_at']
    list_filter = ['action', 'status', 'method']
    search_fields = ['actor__username', 'action', 'model_name', 'ip', 'object_id']
    readonly_fields = ['actor', 'action', 'model_name', 'object_id', 'object_repr',
                       'changes', 'ip', 'user_agent', 'path', 'method',
                       'response_code', 'status', 'extra', 'created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AdminSession)
class AdminSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip', 'started_at', 'last_seen', 'is_active', 'status']
    list_filter = ['is_active', 'status']
    search_fields = ['user__username', 'ip', 'user_agent']
    readonly_fields = ['user', 'session_key', 'ip', 'user_agent', 'started_at', 'last_seen', 'ended_at']
    ordering = ['-started_at']

    actions = ['force_logout_selected']

    def force_logout_selected(self, request, queryset):
        from django.utils import timezone
        queryset.filter(is_active=True).update(
            is_active=False, status='force_logout', ended_at=timezone.now(),
            force_logout_by=request.user, force_logout_reason='Admin bulk force logout'
        )
    force_logout_selected.short_description = 'Force logout selected sessions'


@admin.register(AdminNote)
class AdminNoteAdmin(admin.ModelAdmin):
    list_display = ['created_by', 'content_type', 'object_id', 'is_pinned', 'is_private', 'created_at']
    list_filter = ['is_pinned', 'is_private']
    search_fields = ['note', 'created_by__username']
    raw_id_fields = ['created_by']