# engagement/admin/spin_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.spinwheel import SpinWheel
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(SpinWheel)
class SpinWheelAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = [
        "user_link", "coins_won_badge", "xp_earned",
        "spun_at_display", "boost_icon", "outcome_idx",
    ]
    list_filter   = ["is_boosted", "outcome_idx"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["spun_at", "created_at", "updated_at"]
    ordering      = ["-spun_at"]

    fieldsets = (
        ("User", {
            "fields": ("user", "tenant"),
        }),
        ("Outcome", {
            "fields": ("coins_won", "xp_earned", "outcome_idx", "is_boosted"),
        }),
        ("Meta", {
            "fields": ("spun_at", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def coins_won_badge(self, obj):
        coins = float(obj.coins_won)
        if coins >= 50:
            color = "#FFD700"
        elif coins >= 10:
            color = "#FF9800"
        elif coins >= 5:
            color = "#4CAF50"
        else:
            color = "#2196F3"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;">'
            '💰 {}</span>',
            color, coins,
        )
    coins_won_badge.short_description = "Won"

    def spun_at_display(self, obj):
        if not obj.spun_at:
            return "—"
        delta = timezone.now() - obj.spun_at
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        mins = delta.seconds // 60
        if mins > 0:
            return f"{mins}m ago"
        return "just now"
    spun_at_display.short_description = "Spun At"

    def boost_icon(self, obj):
        return format_html("⚡ Boosted") if obj.is_boosted else "—"
    boost_icon.short_description = "Boost"
