# engagement/admin/seasonal_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.seasonal_event import SeasonalEvent, EventMission, UserEventProgress, UserEventCurrency, EventShopItem
from ..models.scratch_card import ScratchCardTemplate, ScratchCardPrize, ScratchCardResult, LoginCalendar, LoginCalendarDay
from ..models.auction import Auction, AuctionBid, AuctionWatchlist
from .mixins import TenantFilterMixin, UserLinkMixin


# ── Seasonal Events ────────────────────────────────────────────────────────────

@admin.register(SeasonalEvent)
class SeasonalEventAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["icon_display", "name", "status_badge", "coin_multiplier",
                     "xp_multiplier", "currency_name", "starts_at", "ends_at"]
    list_filter   = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["-starts_at"]
    readonly_fields = ["created_at", "updated_at"]

    def icon_display(self, obj):
        return format_html('<span style="font-size:20px;">{}</span>', obj.icon or "🎉")
    icon_display.short_description = ""

    def status_badge(self, obj):
        now = timezone.now()
        if not obj.is_active:
            color, label = "#888", "Inactive"
        elif now < obj.starts_at:
            color, label = "#FF9800", "Upcoming"
        elif now > obj.ends_at:
            color, label = "#607D8B", "Ended"
        else:
            color, label = "#4CAF50", "LIVE"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:8px;">{}</span>',
            color, label,
        )
    status_badge.short_description = "Status"

    def currency_name(self, obj):
        return format_html("{} {}", obj.event_currency_icon, obj.event_currency_name)
    currency_name.short_description = "Currency"


@admin.register(EventMission)
class EventMissionAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["title", "event_name", "action", "target",
                     "coin_reward", "xp_reward", "event_currency_reward", "order"]
    list_filter   = ["event", "action"]
    search_fields = ["title", "slug"]
    ordering      = ["event", "order"]
    readonly_fields = ["created_at", "updated_at"]

    def event_name(self, obj):
        return obj.event.name
    event_name.short_description = "Event"


@admin.register(UserEventProgress)
class UserEventProgressAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "event_name", "mission_title", "progress_bar",
                     "times_completed", "reward_claimed"]
    list_filter   = ["event", "reward_claimed"]
    search_fields = ["user__username"]
    readonly_fields = ["last_completed_at", "created_at", "updated_at"]

    def event_name(self, obj):
        return obj.event.name
    event_name.short_description = "Event"

    def mission_title(self, obj):
        return obj.mission.title
    mission_title.short_description = "Mission"

    def progress_bar(self, obj):
        pct   = obj.pct
        color = "#4CAF50" if pct >= 100 else "#2196F3"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:80px;display:inline-block;">'
            '<div style="background:{};width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}/{}',
            color, pct, obj.progress, obj.mission.target,
        )
    progress_bar.short_description = "Progress"


# ── Scratch Cards ──────────────────────────────────────────────────────────────

@admin.register(ScratchCardTemplate)
class ScratchCardTemplateAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["icon_display", "name", "max_per_day", "price_coins", "prizes_count", "is_active"]
    list_filter   = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]

    def icon_display(self, obj):
        return format_html('<span style="font-size:20px;">{}</span>', obj.icon or "🎰")
    icon_display.short_description = ""

    def prizes_count(self, obj):
        return obj.prizes.count()
    prizes_count.short_description = "Prizes"


@admin.register(ScratchCardPrize)
class ScratchCardPrizeAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["template", "label", "coins_display", "xp", "item_slug", "weight_badge"]
    list_filter   = ["template"]
    ordering      = ["-weight"]
    readonly_fields = ["created_at", "updated_at"]

    def coins_display(self, obj):
        if obj.coins > 0:
            return format_html('<span style="color:#D4AF37;">💰 {}</span>', obj.coins)
        return "—"
    coins_display.short_description = "Coins"

    def weight_badge(self, obj):
        color = "#4CAF50" if obj.weight >= 20 else "#FF9800"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.weight,
        )
    weight_badge.short_description = "Weight"


@admin.register(ScratchCardResult)
class ScratchCardResultAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "template", "prize_label", "coins_won_display", "xp_won", "scratched_at"]
    list_filter   = ["template"]
    search_fields = ["user__username"]
    ordering      = ["-scratched_at"]
    readonly_fields = ["scratched_at", "created_at", "updated_at"]

    def prize_label(self, obj):
        return obj.prize.label
    prize_label.short_description = "Prize"

    def coins_won_display(self, obj):
        if obj.coins_won > 0:
            return format_html('<span style="color:#D4AF37;">💰 {}</span>', obj.coins_won)
        return "—"
    coins_won_display.short_description = "Coins"


# ── Login Calendar ────────────────────────────────────────────────────────────

@admin.register(LoginCalendar)
class LoginCalendarAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display = ["year", "month", "is_active", "days_configured"]
    list_filter  = ["is_active", "year"]
    readonly_fields = ["created_at", "updated_at"]

    def days_configured(self, obj):
        return obj.days.count()
    days_configured.short_description = "Days"


@admin.register(LoginCalendarDay)
class LoginCalendarDayAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["calendar", "day_number", "coins", "xp", "item_slug", "is_milestone"]
    list_filter   = ["calendar", "is_milestone"]
    ordering      = ["calendar", "day_number"]
    readonly_fields = ["created_at", "updated_at"]


# ── Auction House ──────────────────────────────────────────────────────────────

@admin.register(Auction)
class AuctionAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["title", "status_badge", "current_bid_display",
                     "total_bids", "winner_name", "ends_at"]
    list_filter   = ["status"]
    search_fields = ["title"]
    ordering      = ["-ends_at"]
    readonly_fields = ["current_bid", "total_bids", "winner", "created_at", "updated_at"]

    def status_badge(self, obj):
        colors = {
            "upcoming": "#FF9800", "active": "#4CAF50",
            "ended": "#607D8B", "cancelled": "#F44336",
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status.upper(),
        )
    status_badge.short_description = "Status"

    def current_bid_display(self, obj):
        if obj.current_bid > 0:
            return format_html('<span style="color:#D4AF37;font-weight:600;">💰 {}</span>', obj.current_bid)
        return format_html('<span style="color:#888;">Starting: {}</span>', obj.starting_bid)
    current_bid_display.short_description = "Current Bid"

    def winner_name(self, obj):
        if obj.winner:
            return format_html('<span style="color:#4CAF50;">🏆 {}</span>', obj.winner.username)
        return "—"
    winner_name.short_description = "Winner"

    actions = ["close_auctions_action"]

    def close_auctions_action(self, request, queryset):
        from ..services.auction_service import AuctionService
        count = 0
        for auction in queryset.filter(status="active"):
            AuctionService.close_auction(auction.pk)
            count += 1
        self.message_user(request, f"Closed {count} auctions.")
    close_auctions_action.short_description = "Close selected auctions"


@admin.register(AuctionBid)
class AuctionBidAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "auction_title", "amount_display",
                     "is_winning", "coins_returned", "created_at"]
    list_filter   = ["is_winning", "coins_returned"]
    search_fields = ["user__username", "auction__title"]
    ordering      = ["-amount", "-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    def auction_title(self, obj):
        return obj.auction.title[:40]
    auction_title.short_description = "Auction"

    def amount_display(self, obj):
        color = "#4CAF50" if obj.is_winning else "#888"
        return format_html('<span style="color:{};font-weight:600;">💰 {}</span>', color, obj.amount)
    amount_display.short_description = "Bid"
