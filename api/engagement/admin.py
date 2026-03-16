# api/engagement/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import DailyCheckIn, SpinWheel, Leaderboard, LeaderboardReward

# ==================== DAILY CHECK-IN ADMIN ====================
@admin.register(DailyCheckIn)
class DailyCheckInAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'date_display', 'streak_badge',
        'bonus_badge', 'reward_claimed_icon'
    ]
    list_filter = ['date', 'bonus_claimed', 'reward_claimed']
    search_fields = ['user__username']
    date_hierarchy = 'date'
    
    def user_link(self, obj):
        url = f'/admin/users/user/{obj.user.id}/change/'
        return format_html('<a href="{}">👤 {}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def date_display(self, obj):
        return obj.date.strftime('%Y-%m-%d')
    date_display.short_description = 'Date'
    
    def streak_badge(self, obj):
        if obj.streak_count >= 7:
            color = '#FFD700'
            icon = '🔥'
        elif obj.streak_count >= 3:
            color = '#4CAF50'
            icon = '[STAR]'
        else:
            color = '#2196F3'
            icon = '📅'
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px;">{} {}</span>',
            color, icon, obj.streak_count
        )
    streak_badge.short_description = 'Streak'
    
    def bonus_badge(self, obj):
        if obj.bonus_claimed:
            return format_html('<span style="color: #4CAF50;">[OK] Bonus</span>')
        return format_html('<span style="color: #999;">-</span>')
    bonus_badge.short_description = 'Bonus'
    
    def reward_claimed_icon(self, obj):
        return '[OK]' if obj.reward_claimed else '[ERROR]'
    reward_claimed_icon.short_description = 'Claimed'


# ==================== SPIN WHEEL ADMIN ====================
@admin.register(SpinWheel)
class SpinWheelAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'spins_remaining_badge', 'last_spin_display',
        'total_spins', 'total_won'
    ]
    list_filter = ['last_spin']
    search_fields = ['user__username']
    
    def user_link(self, obj):
        url = f'/admin/users/user/{obj.user.id}/change/'
        return format_html('<a href="{}">👤 {}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def spins_remaining_badge(self, obj):
        if obj.spins_remaining > 10:
            color = '#4CAF50'
        elif obj.spins_remaining > 5:
            color = '#FF9800'
        else:
            color = '#F44336'
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px;">🎡 {}</span>',
            color, obj.spins_remaining
        )
    spins_remaining_badge.short_description = 'Spins Left'
    
    def last_spin_display(self, obj):
        if obj.last_spin:
            delta = timezone.now() - obj.last_spin
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m ago"
            return "just now"
        return "Never"
    last_spin_display.short_description = 'Last Spin'


@admin.register(LeaderboardReward)
class LeaderboardRewardAdmin(admin.ModelAdmin):
    list_display = ['rank_badge', 'reward_coins_badge']
    ordering = ['rank']
    
    def rank_badge(self, obj):
        if obj.rank == 1:
            color = '#FFD700'
            icon = '🥇'
        elif obj.rank == 2:
            color = '#C0C0C0'
            icon = '🥈'
        elif obj.rank == 3:
            color = '#CD7F32'
            icon = '🥉'
        else:
            color = '#2196F3'
            icon = '#️⃣'
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px;">{} Rank {}</span>',
            color, icon, obj.rank
        )
    rank_badge.short_description = 'Rank'
    
    def reward_coins_badge(self, obj):
        return format_html(
            '<span style="color: #FFD700; font-weight: bold;">[MONEY] {}</span>',
            obj.reward_coins
        )
    reward_coins_badge.short_description = 'Reward'


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = [
        'rank_badge', 'user_link', 'total_coins_badge',
        'date_display', 'view_actions'
    ]
    list_filter = ['date']
    search_fields = ['user__username']
    date_hierarchy = 'date'
    
    def rank_badge(self, obj):
        if obj.rank == 1:
            color = '#FFD700'
            icon = '🥇'
        elif obj.rank == 2:
            color = '#C0C0C0'
            icon = '🥈'
        elif obj.rank == 3:
            color = '#CD7F32'
            icon = '🥉'
        else:
            color = '#2196F3'
            icon = '#️⃣'
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px;">{} {}</span>',
            color, icon, obj.rank
        )
    rank_badge.short_description = 'Rank'
    
    def user_link(self, obj):
        url = f'/admin/users/user/{obj.user.id}/change/'
        return format_html('<a href="{}">👤 {}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def total_coins_badge(self, obj):
        return format_html(
            '<span style="color: #FFD700; font-weight: bold;">[MONEY] {}</span>',
            obj.total_coins_earned
        )
    total_coins_badge.short_description = 'Coins'
    
    def date_display(self, obj):
        return obj.date.strftime('%Y-%m-%d')
    date_display.short_description = 'Date'
    
    def view_actions(self, obj):
        return format_html(
            '<a href="{}" style="color: #2196F3;">👁️</a>',
            f'/admin/engagement/leaderboard/{obj.id}/change/'
        )
    view_actions.short_description = 'Actions'


# ==================== FORCE REGISTER ALL MODELS ====================
try:
    registered = 0
    
    if not admin.site.is_registered(DailyCheckIn):
        admin.site.register(DailyCheckIn, DailyCheckInAdmin)
        registered += 1
        print("[OK] Registered: DailyCheckIn")
    
    if not admin.site.is_registered(SpinWheel):
        admin.site.register(SpinWheel, SpinWheelAdmin)
        registered += 1
        print("[OK] Registered: SpinWheel")
    
    if not admin.site.is_registered(LeaderboardReward):
        # Already registered via decorator
        pass
    
    if not admin.site.is_registered(Leaderboard):
        # Already registered via decorator
        pass
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} engagement models registered!")
    else:
        print("[OK] All engagement models already registered")
        
except Exception as e:
    print(f"[ERROR] Error: {e}")


# Setup default rewards comment (keep as is)
"""
Run in Django shell:

from engagement.models import LeaderboardReward

rewards = [
    (1, 100),
    (2, 75),
    (3, 50),
    (4, 40),
    (5, 30),
    (6, 25),
    (7, 20),
    (8, 15),
    (9, 10),
    (10, 10),
]

for rank, coins in rewards:
    LeaderboardReward.objects.create(rank=rank, reward_coins=coins)
"""