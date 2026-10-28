# api/djoyalty/admin/badge_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.engagement import Badge, UserBadge, DailyStreak, Challenge, ChallengeParticipant, Milestone, UserMilestone


class UserBadgeInline(admin.TabularInline):
    model = UserBadge
    extra = 0
    readonly_fields = ['customer', 'points_awarded', 'earned_at']
    can_delete = False


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ['icon_display', 'name', 'rarity', 'trigger', 'threshold', 'points_reward', 'is_active', 'is_unique']
    list_filter = ['rarity', 'trigger', 'is_active', 'is_unique']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [UserBadgeInline]
    fieldsets = [
        ('Badge Info', {'fields': ['name', 'description', 'icon', 'rarity', 'is_active', 'is_unique']}),
        ('Trigger Config', {'fields': ['trigger', 'threshold', 'points_reward']}),
        ('Display', {'fields': ['sort_order']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def icon_display(self, obj):
        return format_html('<span style="font-size:1.5em;">{}</span>', obj.icon)
    icon_display.short_description = 'Icon'


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ['customer', 'badge', 'points_awarded', 'is_pinned', 'earned_at']
    list_filter = ['badge__rarity', 'is_pinned', 'earned_at']
    search_fields = ['customer__code', 'badge__name']
    readonly_fields = ['customer', 'badge', 'points_awarded', 'earned_at', 'created_at']


class ChallengeParticipantInline(admin.TabularInline):
    model = ChallengeParticipant
    extra = 0
    readonly_fields = ['customer', 'progress', 'status', 'completed_at', 'points_awarded']
    can_delete = False


@admin.register(DailyStreak)
class DailyStreakAdmin(admin.ModelAdmin):
    list_display = ['customer', 'current_streak', 'longest_streak', 'last_activity_date', 'is_active']
    list_filter = ['is_active']
    search_fields = ['customer__code']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-current_streak']


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['name', 'challenge_type', 'target_value', 'points_reward', 'status', 'start_date', 'end_date']
    list_filter = ['status', 'challenge_type']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ChallengeParticipantInline]
    fieldsets = [
        ('Challenge Info', {'fields': ['name', 'description', 'challenge_type', 'status']}),
        ('Targets', {'fields': ['target_action', 'target_value', 'target_count']}),
        ('Rewards', {'fields': ['points_reward', 'bonus_points', 'badge_reward']}),
        ('Schedule', {'fields': ['start_date', 'end_date', 'max_participants']}),
        ('Content', {'fields': ['image', 'terms']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'milestone_type', 'threshold', 'points_reward', 'is_repeatable', 'is_active']
    list_filter = ['milestone_type', 'is_active', 'is_repeatable']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']


@admin.register(UserMilestone)
class UserMilestoneAdmin(admin.ModelAdmin):
    list_display = ['customer', 'milestone', 'points_awarded', 'times_achieved', 'achieved_at']
    list_filter = ['milestone__milestone_type', 'achieved_at']
    search_fields = ['customer__code', 'milestone__name']
    readonly_fields = ['customer', 'milestone', 'points_awarded', 'achieved_at', 'created_at']
