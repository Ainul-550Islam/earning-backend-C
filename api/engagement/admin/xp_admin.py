# engagement/admin/xp_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.xp import UserXP, XPTransaction
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(UserXP)
class UserXPAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "level_badge", "total_xp", "level_pct_bar", "level_updated_at"]
    search_fields = ["user__username"]
    ordering      = ["-level", "-total_xp"]
    readonly_fields = ["level_updated_at", "created_at", "updated_at"]

    fieldsets = (
        ("User", {"fields": ("user", "tenant")}),
        ("XP", {"fields": ("total_xp", "level", "level_updated_at")}),
        ("Meta", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    # Admin action: manually grant XP
    actions = ["grant_100_xp"]

    def grant_100_xp(self, request, queryset):
        from ..services.xp_service import XPService
        for xp_obj in queryset:
            XPService.grant(xp_obj.user, 100, source="admin", note="Admin action +100 XP")
        self.message_user(request, f"Granted 100 XP to {queryset.count()} users.")
    grant_100_xp.short_description = "Grant 100 XP to selected users"

    def level_badge(self, obj):
        return format_html(
            '<span style="background:#7F77DD;color:#fff;padding:3px 10px;border-radius:12px;">'
            '⬆️ Level {}</span>',
            obj.level,
        )
    level_badge.short_description = "Level"

    def level_pct_bar(self, obj):
        pct = obj.level_pct
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:100px;display:inline-block;">'
            '<div style="background:#7F77DD;width:{}%;height:10px;border-radius:4px;"></div>'
            '</div> {}%',
            pct, pct,
        )
    level_pct_bar.short_description = "Progress"


@admin.register(XPTransaction)
class XPTransactionAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "source_badge", "amount_badge", "note", "ref_id", "created_at"]
    list_filter   = ["source"]
    search_fields = ["user__username", "note", "ref_id"]
    ordering      = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    def source_badge(self, obj):
        colors = {
            "checkin": "#4CAF50",
            "spin": "#2196F3",
            "quest": "#FF9800",
            "achievement": "#9C27B0",
            "challenge": "#F44336",
            "referral": "#00BCD4",
            "admin": "#607D8B",
        }
        color = colors.get(obj.source, "#888")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.source,
        )
    source_badge.short_description = "Source"

    def amount_badge(self, obj):
        color = "#4CAF50" if obj.amount > 0 else "#F44336"
        sign  = "+" if obj.amount > 0 else ""
        return format_html(
            '<span style="color:{};font-weight:600;">{}{} XP</span>',
            color, sign, obj.amount,
        )
    amount_badge.short_description = "XP"
