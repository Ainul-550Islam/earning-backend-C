# engagement/admin/battle_pass_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.battle_pass import BattlePass, BattlePassTier, UserBattlePass, BattlePassXPSource
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(BattlePass)
class BattlePassAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["season_badge", "name", "status_badge", "premium_price_coins",
                     "total_tiers", "enrolled_count", "starts_at", "ends_at"]
    list_filter   = ["is_active"]
    search_fields = ["name"]
    ordering      = ["-season_num"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Season",   {"fields": ("name", "season_num", "description", "cover_image", "is_active", "tenant")}),
        ("Schedule", {"fields": ("starts_at", "ends_at")}),
        ("Settings", {"fields": ("premium_price_coins", "total_tiers")}),
        ("Meta",     {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def season_badge(self, obj):
        return format_html(
            '<span style="background:#7F77DD;color:#fff;padding:3px 10px;border-radius:12px;">'
            'S{}</span>', obj.season_num
        )
    season_badge.short_description = "Season"

    def status_badge(self, obj):
        now = timezone.now()
        if not obj.is_active:
            color, label = "#888", "Inactive"
        elif now < obj.starts_at:
            color, label = "#FF9800", "Upcoming"
        elif now > obj.ends_at:
            color, label = "#607D8B", "Ended"
        else:
            color, label = "#4CAF50", "Live"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:8px;">{}</span>',
            color, label
        )
    status_badge.short_description = "Status"

    def enrolled_count(self, obj):
        return obj.user_passes.count()
    enrolled_count.short_description = "Enrolled"


class BattlePassTierInline(admin.TabularInline):
    model  = BattlePassTier
    extra  = 0
    fields = ["tier_number", "xp_required", "free_coins", "free_xp",
              "premium_coins", "premium_xp", "is_milestone"]


@admin.register(BattlePassTier)
class BattlePassTierAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["season_num", "tier_number", "xp_required",
                     "free_coins", "free_xp", "premium_coins", "premium_xp", "milestone_icon"]
    list_filter   = ["battle_pass", "is_milestone"]
    ordering      = ["battle_pass__season_num", "tier_number"]
    readonly_fields = ["created_at", "updated_at"]

    def season_num(self, obj):
        return f"S{obj.battle_pass.season_num}"
    season_num.short_description = "Season"

    def milestone_icon(self, obj):
        return format_html("⭐") if obj.is_milestone else "—"
    milestone_icon.short_description = "Milestone"


@admin.register(UserBattlePass)
class UserBattlePassAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "season_num", "premium_badge",
                     "tier_progress", "current_xp", "last_claimed_tier"]
    list_filter   = ["is_premium", "battle_pass__season_num"]
    search_fields = ["user__username"]
    readonly_fields = ["premium_unlocked_at", "created_at", "updated_at"]

    def season_num(self, obj):
        return f"S{obj.battle_pass.season_num}"
    season_num.short_description = "Season"

    def premium_badge(self, obj):
        if obj.is_premium:
            return format_html('<span style="color:#FFD700;font-weight:600;">PRO</span>')
        return format_html('<span style="color:#888;">Free</span>')
    premium_badge.short_description = "Track"

    def tier_progress(self, obj):
        total = obj.battle_pass.total_tiers
        pct   = int(obj.current_tier / total * 100) if total else 0
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:80px;display:inline-block;">'
            '<div style="background:#7F77DD;width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}/{}',
            pct, obj.current_tier, total,
        )
    tier_progress.short_description = "Tiers"


@admin.register(BattlePassXPSource)
class BattlePassXPSourceAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["battle_pass", "action", "xp_amount", "daily_cap", "created_at"]
    list_filter   = ["battle_pass"]
    search_fields = ["action"]
    readonly_fields = ["created_at", "updated_at"]
