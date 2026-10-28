# engagement/admin/leaderboard_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason
from .mixins import TenantFilterMixin, UserLinkMixin, RankBadgeMixin


@admin.register(LeaderboardSeason)
class LeaderboardSeasonAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["period", "start_date", "end_date", "is_active", "prize_pool"]
    list_filter   = ["period", "is_active"]
    ordering      = ["-start_date"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Leaderboard)
class LeaderboardAdmin(TenantFilterMixin, UserLinkMixin, RankBadgeMixin, admin.ModelAdmin):
    list_display  = [
        "rank_badge", "user_link", "coins_badge",
        "total_xp_earned", "date", "reward_distributed_icon",
    ]
    list_filter   = ["date", "reward_distributed"]
    search_fields = ["user__username"]
    date_hierarchy = "date"
    ordering      = ["date", "rank"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("User & Date", {
            "fields": ("user", "tenant", "date", "season"),
        }),
        ("Score", {
            "fields": ("rank", "total_coins_earned", "total_xp_earned"),
        }),
        ("Reward", {
            "fields": ("reward_distributed",),
        }),
        ("Meta", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def coins_badge(self, obj):
        return format_html(
            '<span style="color:#D4AF37;font-weight:600;">💰 {}</span>',
            obj.total_coins_earned,
        )
    coins_badge.short_description = "Coins"

    def reward_distributed_icon(self, obj):
        return format_html(
            '<span style="color:{};">{}</span>',
            "#4CAF50" if obj.reward_distributed else "#F44336",
            "✔ Rewarded" if obj.reward_distributed else "Pending",
        )
    reward_distributed_icon.short_description = "Reward"

    # Admin action: manually trigger reward distribution
    actions = ["distribute_rewards_action"]

    def distribute_rewards_action(self, request, queryset):
        from ..services.leaderboard_service import LeaderboardService
        dates = set(queryset.values_list("date", flat=True))
        total = 0
        for d in dates:
            total += LeaderboardService.distribute_rewards(d)
        self.message_user(request, f"Distributed rewards for {total} users across {len(dates)} dates.")
    distribute_rewards_action.short_description = "Distribute rewards for selected entries"


@admin.register(LeaderboardReward)
class LeaderboardRewardAdmin(TenantFilterMixin, RankBadgeMixin, admin.ModelAdmin):
    list_display  = ["rank_badge", "season_type", "reward_coins_badge", "reward_xp", "reward_badge"]
    list_filter   = ["season_type"]
    ordering      = ["season_type", "rank"]
    readonly_fields = ["created_at", "updated_at"]

    def reward_coins_badge(self, obj):
        return format_html(
            '<span style="color:#D4AF37;font-weight:600;">💰 {}</span>',
            obj.reward_coins,
        )
    reward_coins_badge.short_description = "Coins Reward"
