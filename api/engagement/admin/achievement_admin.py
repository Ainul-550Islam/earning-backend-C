# engagement/admin/achievement_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.achievement import Achievement, UserAchievement, AchievementProgress
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(Achievement)
class AchievementAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = [
        "icon_display", "name", "type", "threshold",
        "xp_reward", "coin_reward_badge", "is_active", "is_secret", "order",
    ]
    list_filter   = ["type", "is_active", "is_secret"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["type", "order", "threshold"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Definition", {
            "fields": ("slug", "name", "description", "type", "threshold"),
        }),
        ("Display", {
            "fields": ("icon", "badge_color", "order"),
        }),
        ("Rewards", {
            "fields": ("xp_reward", "coin_reward"),
        }),
        ("Visibility", {
            "fields": ("is_active", "is_secret", "tenant"),
        }),
        ("Meta", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def icon_display(self, obj):
        return format_html(
            '<span style="font-size:20px;">{}</span>', obj.icon or "🏅"
        )
    icon_display.short_description = "Icon"

    def coin_reward_badge(self, obj):
        if obj.coin_reward:
            return format_html('<span style="color:#D4AF37;">💰 {}</span>', obj.coin_reward)
        return "—"
    coin_reward_badge.short_description = "Coins"

    # Admin action: bulk unlock for all active users
    actions = ["bulk_unlock_for_all"]

    def bulk_unlock_for_all(self, request, queryset):
        from django.contrib.auth import get_user_model
        from ..services.achievement_service import AchievementService
        User  = get_user_model()
        users = User.objects.filter(is_active=True)
        count = 0
        for achievement in queryset:
            for user in users.iterator(chunk_size=200):
                ua = AchievementService._unlock(user, achievement)
                if ua:
                    count += 1
        self.message_user(request, f"Unlocked {count} achievements across users.")
    bulk_unlock_for_all.short_description = "Bulk unlock for all active users"


@admin.register(UserAchievement)
class UserAchievementAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "achievement_name", "unlocked_at", "notified", "reward_claimed"]
    list_filter   = ["notified", "reward_claimed"]
    search_fields = ["user__username", "achievement__name"]
    date_hierarchy = "unlocked_at"
    readonly_fields = ["unlocked_at", "created_at", "updated_at"]

    def achievement_name(self, obj):
        return format_html(
            '<strong>{}</strong> <span style="color:#888;">[{}]</span>',
            obj.achievement.name, obj.achievement.type,
        )
    achievement_name.short_description = "Achievement"


@admin.register(AchievementProgress)
class AchievementProgressAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "achievement_name", "progress_bar", "last_updated"]
    search_fields = ["user__username", "achievement__name"]
    readonly_fields = ["last_updated", "created_at", "updated_at"]

    def achievement_name(self, obj):
        return obj.achievement.name
    achievement_name.short_description = "Achievement"

    def progress_bar(self, obj):
        pct = obj.pct
        color = "#4CAF50" if pct >= 100 else "#2196F3"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:120px;">'
            '<div style="background:{};width:{}%;height:12px;border-radius:4px;"></div>'
            '</div> {}%',
            color, pct, pct,
        )
    progress_bar.short_description = "Progress"
