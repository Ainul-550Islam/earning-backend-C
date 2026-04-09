# api/djoyalty/admin/badge_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.engagement import Badge, UserBadge

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ['badge_display', 'trigger', 'threshold', 'points_reward', 'is_active']
    list_filter = ['trigger', 'is_active']
    search_fields = ['name']

    def badge_display(self, obj):
        return format_html('{} <strong>{}</strong>', obj.icon, obj.name)
    badge_display.short_description = 'Badge'

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ['customer', 'badge', 'points_awarded', 'awarded_at']
    search_fields = ['customer__code', 'badge__name']
    readonly_fields = ['awarded_at']
