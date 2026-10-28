# engagement/admin/quest_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.quest import Quest, UserQuest
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(Quest)
class QuestAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["icon_display", "title", "type_badge", "action", "target",
                     "coin_reward", "xp_reward", "is_active", "order"]
    list_filter   = ["type", "is_active"]
    search_fields = ["title", "slug", "action"]
    prepopulated_fields = {"slug": ("title",)}
    ordering      = ["type", "order"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Definition", {"fields": ("slug", "title", "description", "type", "icon")}),
        ("Mechanics", {"fields": ("action", "target", "order")}),
        ("Rewards",   {"fields": ("coin_reward", "xp_reward")}),
        ("Visibility",{"fields": ("is_active", "tenant")}),
        ("Meta",      {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def icon_display(self, obj):
        return format_html('<span style="font-size:18px;">{}</span>', obj.icon or "📋")
    icon_display.short_description = "Icon"

    def type_badge(self, obj):
        colors = {"daily": "#4CAF50", "weekly": "#2196F3", "special": "#FF9800"}
        color  = colors.get(obj.type, "#888")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.type,
        )
    type_badge.short_description = "Type"


@admin.register(UserQuest)
class UserQuestAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = [
        "user_link", "quest_title", "status_badge",
        "progress_bar", "period_date", "completed_at", "reward_claimed",
    ]
    list_filter   = ["status", "quest__type", "reward_claimed"]
    search_fields = ["user__username", "quest__title"]
    ordering      = ["-period_date"]
    readonly_fields = ["completed_at", "created_at", "updated_at"]

    def quest_title(self, obj):
        return format_html("<strong>{}</strong>", obj.quest.title)
    quest_title.short_description = "Quest"

    def status_badge(self, obj):
        colors = {"active": "#2196F3", "completed": "#4CAF50", "expired": "#F44336"}
        color  = colors.get(obj.status, "#888")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.status,
        )
    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        pct   = obj.pct
        color = "#4CAF50" if pct >= 100 else "#2196F3"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:100px;display:inline-block;">'
            '<div style="background:{};width:{}%;height:10px;border-radius:4px;"></div>'
            '</div> {}/{}',
            color, pct, obj.progress, obj.quest.target,
        )
    progress_bar.short_description = "Progress"
