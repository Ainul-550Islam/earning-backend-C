# api/admin_panel/admin/feature_flag_admin.py
"""Django Admin for FeatureFlag."""
from django.contrib import admin
from django.utils.html import format_html
from ..models.config import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ['flag_key', 'label', 'status_badge', 'rollout_pct', 'updated_by', 'updated_at']
    list_filter = ['is_enabled']
    search_fields = ['flag_key', 'label', 'description']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
    ordering = ['flag_key']

    fieldsets = (
        ('Flag', {'fields': ('flag_key', 'label', 'description')}),
        ('Rollout', {'fields': ('is_enabled', 'rollout_pct', 'environments', 'allowed_user_ids')}),
        ('Metadata', {'fields': ('metadata',)}),
        ('Audit', {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Status', boolean=False)
    def status_badge(self, obj):
        if obj.is_enabled:
            color = 'green'
            label = f'✅ ON ({obj.rollout_pct}%)'
        else:
            color = 'red'
            label = '❌ OFF'
        return format_html('<span style="color:{};">{}</span>', color, label)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['enable_flags', 'disable_flags', 'set_full_rollout']

    @admin.action(description='Enable selected flags')
    def enable_flags(self, request, queryset):
        updated = queryset.update(is_enabled=True, updated_by=request.user)
        from django.core.cache import cache
        cache.delete('admin_panel:feature_flags')
        self.message_user(request, f'{updated} flag(s) enabled.')

    @admin.action(description='Disable selected flags')
    def disable_flags(self, request, queryset):
        updated = queryset.update(is_enabled=False, updated_by=request.user)
        from django.core.cache import cache
        cache.delete('admin_panel:feature_flags')
        self.message_user(request, f'{updated} flag(s) disabled.')

    @admin.action(description='Set 100% rollout for selected flags')
    def set_full_rollout(self, request, queryset):
        updated = queryset.update(rollout_pct=100, updated_by=request.user)
        self.message_user(request, f'{updated} flag(s) set to 100% rollout.')