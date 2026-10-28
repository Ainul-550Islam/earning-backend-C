# engagement/admin/checkin_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.checkin import DailyCheckIn
from .mixins import TenantFilterMixin, UserLinkMixin, CoinsBadgeMixin


@admin.register(DailyCheckIn)
class DailyCheckInAdmin(TenantFilterMixin, UserLinkMixin, CoinsBadgeMixin, admin.ModelAdmin):
    list_display  = [
        "user_link", "date", "streak_badge", "coins_display",
        "xp_earned", "bonus_badge", "reward_claimed_icon", "shield_icon",
    ]
    list_filter   = ["date", "bonus_claimed", "reward_claimed", "streak_shield_used"]
    search_fields = ["user__username", "user__email"]
    date_hierarchy = "date"
    readonly_fields = ["created_at", "updated_at"]
    ordering      = ["-date"]

    fieldsets = (
        ("User & Date", {
            "fields": ("user", "tenant", "date"),
        }),
        ("Rewards", {
            "fields": ("coins_earned", "xp_earned", "consecutive_days"),
        }),
        ("Status Flags", {
            "fields": ("bonus_claimed", "reward_claimed", "streak_shield_used", "note"),
        }),
        ("Meta", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def streak_badge(self, obj):
        days = obj.consecutive_days
        if days >= 30:
            color, icon = "#9C27B0", "🔥"
        elif days >= 14:
            color, icon = "#FF5722", "🔥"
        elif days >= 7:
            color, icon = "#FFD700", "🔥"
        elif days >= 3:
            color, icon = "#4CAF50", "⭐"
        else:
            color, icon = "#2196F3", "📅"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;">'
            '{} {} days</span>',
            color, icon, days,
        )
    streak_badge.short_description = "Streak"

    def coins_display(self, obj):
        return format_html(
            '<span style="color:#D4AF37;font-weight:600;">💰 {}</span>',
            obj.coins_earned,
        )
    coins_display.short_description = "Coins"

    def bonus_badge(self, obj):
        if obj.bonus_claimed:
            return format_html('<span style="color:#4CAF50;">✔ Bonus</span>')
        return format_html('<span style="color:#999;">—</span>')
    bonus_badge.short_description = "Bonus"

    def reward_claimed_icon(self, obj):
        return format_html(
            '<span style="color:{};">{}</span>',
            "#4CAF50" if obj.reward_claimed else "#F44336",
            "✔" if obj.reward_claimed else "✘",
        )
    reward_claimed_icon.short_description = "Reward"

    def shield_icon(self, obj):
        return format_html("🛡️") if obj.streak_shield_used else "—"
    shield_icon.short_description = "Shield"
