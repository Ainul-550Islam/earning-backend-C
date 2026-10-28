# api/djoyalty/admin/gamification_admin.py
"""
Django admin registrations for all gamification models.
AUDIT FIX (v4): SpinWheel, ScratchCard, Lottery, LeaderboardSeason,
QuizReward were all unregistered — configurable only via shell.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from ..models.gamification import (
    SpinWheelConfig, SpinWheelSlice, SpinWheelResult,
    ScratchCard,
    LotteryDraw, LotteryTicket,
    LeaderboardSeason,
    QuizReward, CustomerQuizAttempt,
)


# ── Spin Wheel ────────────────────────────────────────────────────────────────

class SpinWheelSliceInline(admin.TabularInline):
    model = SpinWheelSlice
    extra  = 2
    fields = ['label', 'prize_type', 'points_value', 'voucher_discount',
              'multiplier_value', 'multiplier_hours', 'probability', 'color', 'sort_order']


@admin.register(SpinWheelConfig)
class SpinWheelConfigAdmin(admin.ModelAdmin):
    list_display   = ['name', 'trigger', 'spins_per_day', 'is_active',
                      'valid_from', 'valid_until', 'total_probability_display']
    list_filter    = ['is_active', 'trigger', 'tenant']
    search_fields  = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines        = [SpinWheelSliceInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'name', 'description', 'trigger', 'image'),
        }),
        ('Rules', {
            'fields': ('spins_per_day', 'min_spend_to_unlock'),
        }),
        ('Scheduling', {
            'fields': ('is_active', 'valid_from', 'valid_until'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def total_probability_display(self, obj):
        total = sum(s.probability for s in obj.slices.all())
        colour = 'green' if total == 100 else 'red'
        return format_html('<b style="color:{};">{}</b>', colour, f'{total}%')
    total_probability_display.short_description = 'Total Prob.'


@admin.register(SpinWheelResult)
class SpinWheelResultAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'wheel', 'slice_won', 'points_awarded',
                     'prize_claimed', 'spun_at']
    list_filter   = ['prize_claimed', 'wheel']
    search_fields = ['customer__code', 'wheel__name']
    readonly_fields = ['customer', 'wheel', 'slice_won', 'points_awarded',
                       'spun_at', 'claimed_at', 'created_at']
    date_hierarchy = 'spun_at'


# ── Scratch Card ──────────────────────────────────────────────────────────────

@admin.register(ScratchCard)
class ScratchCardAdmin(admin.ModelAdmin):
    list_display  = ['code', 'customer', 'status', 'prize_type',
                     'points_value', 'expires_at', 'scratched_at']
    list_filter   = ['status', 'prize_type', 'tenant']
    search_fields = ['code', 'customer__code']
    readonly_fields = ['code', 'customer', 'scratched_at', 'claimed_at', 'created_at']
    date_hierarchy = 'created_at'
    actions        = ['mark_expired']

    def mark_expired(self, request, queryset):
        updated = queryset.filter(status='unscratched').update(status='expired')
        self.message_user(request, f'{updated} cards marked as expired.')
    mark_expired.short_description = 'Mark selected unscratched cards as expired'


# ── Lottery ───────────────────────────────────────────────────────────────────

class LotteryTicketInline(admin.TabularInline):
    model       = LotteryTicket
    extra       = 0
    readonly_fields = ['customer', 'ticket_number', 'points_spent', 'is_winner', 'purchased_at']
    can_delete  = False
    max_num     = 50
    show_change_link = True


@admin.register(LotteryDraw)
class LotteryDrawAdmin(admin.ModelAdmin):
    list_display  = ['name', 'status', 'ticket_cost_points', 'total_tickets_sold',
                     'draw_date', 'winner']
    list_filter   = ['status', 'tenant']
    search_fields = ['name']
    readonly_fields = ['total_tickets_sold', 'created_at', 'updated_at']
    inlines        = [LotteryTicketInline]
    fieldsets = (
        ('Lottery Info', {
            'fields': ('tenant', 'name', 'description', 'image'),
        }),
        ('Ticket Config', {
            'fields': ('ticket_cost_points', 'max_tickets_per_customer'),
        }),
        ('Prize', {
            'fields': ('prize_description', 'prize_points_value', 'winner'),
        }),
        ('Scheduling', {
            'fields': ('status', 'start_date', 'draw_date'),
        }),
        ('Stats', {
            'fields': ('total_tickets_sold',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['set_open', 'set_closed']

    def set_open(self, request, queryset):
        queryset.update(status='open')
        self.message_user(request, 'Selected lotteries set to OPEN.')
    set_open.short_description = 'Set selected lotteries to Open'

    def set_closed(self, request, queryset):
        queryset.update(status='closed')
        self.message_user(request, 'Selected lotteries set to CLOSED.')
    set_closed.short_description = 'Set selected lotteries to Closed'


@admin.register(LotteryTicket)
class LotteryTicketAdmin(admin.ModelAdmin):
    list_display  = ['ticket_number', 'customer', 'lottery', 'points_spent',
                     'is_winner', 'purchased_at']
    list_filter   = ['is_winner', 'lottery']
    search_fields = ['ticket_number', 'customer__code', 'lottery__name']
    readonly_fields = ['ticket_number', 'customer', 'lottery', 'points_spent',
                       'purchased_at']


# ── Leaderboard Season ────────────────────────────────────────────────────────

# class LeaderboardEntryInline(admin.TabularInline):  # LeaderboardEntry model not available
#     model       = LeaderboardEntry
#     extra       = 0
#     readonly_fields = ['customer', 'rank', 'score', 'last_updated']
#     can_delete  = False
#     max_num     = 20
#     ordering    = ['rank']


@admin.register(LeaderboardSeason)
class LeaderboardSeasonAdmin(admin.ModelAdmin):
    list_display  = ['name', 'season_type', 'metric', 'status',
                     'start_date', 'end_date', 'prizes_distributed']
    list_filter   = ['status', 'season_type', 'metric', 'tenant']
    search_fields = ['name']
    readonly_fields = ['prizes_distributed', 'created_at']
    inlines        = []  # LeaderboardEntryInline not available
    fieldsets = (
        ('Season Info', {
            'fields': ('tenant', 'name', 'description', 'season_type', 'metric'),
        }),
        ('Scheduling', {
            'fields': ('status', 'start_date', 'end_date'),
        }),
        ('Prizes', {
            'fields': ('first_prize_points', 'second_prize_points', 'third_prize_points',
                       'participation_prize_points', 'prizes_distributed'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    actions = ['activate_season', 'close_season', 'distribute_prizes']

    def activate_season(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, 'Selected seasons activated.')
    activate_season.short_description = 'Activate selected seasons'

    def close_season(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, 'Selected seasons closed.')
    close_season.short_description = 'Close selected seasons'

    def distribute_prizes(self, request, queryset):
        try:
            from ..services.engagement.LeaderboardService import LeaderboardService
            count = 0
            for season in queryset.filter(status='completed', prizes_distributed=False):
                LeaderboardService.distribute_prizes(season=season)
                count += 1
            self.message_user(request, f'Prizes distributed for {count} season(s).')
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='error')
    distribute_prizes.short_description = 'Distribute prizes for selected seasons'


# @admin.register(LeaderboardEntry)  # Model not available
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display  = ['rank', 'customer', 'season', 'score', 'last_updated']
    list_filter   = ['season', 'tenant']
    search_fields = ['customer__code', 'season__name']
    readonly_fields = ['customer', 'season', 'rank', 'score', 'last_updated']
    ordering       = ['rank']


# ── Quiz ──────────────────────────────────────────────────────────────────────

class CustomerQuizAttemptInline(admin.TabularInline):
    model       = CustomerQuizAttempt
    extra       = 0
    readonly_fields = ['customer', 'score', 'passed', 'points_awarded',
                       'attempt_number', 'started_at', 'completed_at']
    can_delete  = False
    max_num     = 10


@admin.register(QuizReward)
class QuizRewardAdmin(admin.ModelAdmin):
    list_display  = ['title', 'points_reward', 'pass_score', 'max_attempts',
                     'time_limit_minutes', 'is_active', 'valid_from', 'valid_until']
    list_filter   = ['is_active', 'tenant']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']
    inlines        = [CustomerQuizAttemptInline]
    fieldsets = (
        ('Quiz Info', {
            'fields': ('tenant', 'title', 'description'),
        }),
        ('Rules', {
            'fields': ('points_reward', 'pass_score', 'max_attempts', 'time_limit_minutes'),
        }),
        ('Scheduling', {
            'fields': ('is_active', 'valid_from', 'valid_until'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )


@admin.register(CustomerQuizAttempt)
class CustomerQuizAttemptAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'quiz', 'score', 'passed', 'points_awarded',
                     'attempt_number', 'started_at']
    list_filter   = ['passed', 'quiz']
    search_fields = ['customer__code', 'quiz__title']
    readonly_fields = list_display + ['completed_at']
    date_hierarchy = 'started_at'
