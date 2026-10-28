# api/cms/models_new/leaderboard.py
"""
Leaderboard + Earning Streak — CMS owns this.
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class LeaderboardPeriod(models.Model):
    PERIOD_TYPES = [
        ('daily',   'Daily'),
        ('weekly',  'Weekly'),
        ('monthly', 'Monthly'),
        ('alltime', 'All Time'),
    ]
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPES, db_index=True)
    start_date  = models.DateField()
    end_date    = models.DateField(null=True, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Leaderboard Period"
        unique_together = [['period_type', 'start_date']]

    def __str__(self):
        return f"{self.period_type}: {self.start_date}"

    @classmethod
    def get_active(cls, period_type='weekly'):
        return cls.objects.filter(period_type=period_type, is_active=True).first()


class LeaderboardEntry(models.Model):
    CATEGORIES = [
        ('earnings',  'Total Earnings'),
        ('offers',    'Offers Completed'),
        ('referrals', 'Referrals'),
        ('coins',     'Coins Earned'),
    ]
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    period      = models.ForeignKey(LeaderboardPeriod, on_delete=models.CASCADE,
                                    related_name='entries')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    related_name='cms_leaderboard_entries')
    category    = models.CharField(max_length=20, choices=CATEGORIES,
                                   default='earnings', db_index=True)
    rank        = models.PositiveIntegerField(default=0, db_index=True)
    score       = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    score_usd   = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    score_coins = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    offers_count = models.PositiveIntegerField(default=0)
    is_rewarded = models.BooleanField(default=False)
    updated_at  = models.DateTimeField(auto_now=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Leaderboard Entry"
        unique_together = [['period', 'user', 'category']]
        ordering = ['rank']
        indexes = [
            models.Index(fields=['period', 'category', 'rank']),
            models.Index(fields=['user', 'period']),
        ]

    def __str__(self):
        return f"#{self.rank} {self.user.username} — {self.score} ({self.category})"


class EarningStreak(models.Model):
    """Daily earning streak tracker. Bonus multiplier for consecutive days."""
    user            = models.OneToOneField(settings.AUTH_USER_MODEL,
                                           on_delete=models.CASCADE,
                                           related_name='earning_streak')
    current_streak  = models.PositiveIntegerField(default=0)
    longest_streak  = models.PositiveIntegerField(default=0)
    last_earn_date  = models.DateField(null=True, blank=True)
    streak_bonus_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.0'))
    total_streak_days = models.PositiveIntegerField(default=0)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Earning Streak"

    def __str__(self):
        return f"{self.user.username}: {self.current_streak} day streak"

    def update_streak(self) -> int:
        """Call when user earns. Returns current streak count."""
        today = timezone.now().date()
        yesterday = today - __import__('datetime').timedelta(days=1)

        if self.last_earn_date == today:
            return self.current_streak  # Already counted today

        if self.last_earn_date == yesterday:
            self.current_streak += 1  # Consecutive day
        else:
            self.current_streak = 1   # Streak broken or new

        self.last_earn_date = today
        self.total_streak_days += 1
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

        # Multiplier: up to 2x at 30 day streak
        self.streak_bonus_multiplier = min(
            Decimal('2.0'),
            Decimal('1.0') + Decimal(str(self.current_streak)) * Decimal('0.033')
        )
        self.save(update_fields=['current_streak', 'longest_streak', 'last_earn_date',
                                  'total_streak_days', 'streak_bonus_multiplier', 'updated_at'])
        return self.current_streak

    def is_active_today(self) -> bool:
        return self.last_earn_date == timezone.now().date()


class StreakMilestone(models.Model):
    """Bonus rewards at streak milestones (7 days, 14, 30, etc.)."""
    streak_days   = models.PositiveIntegerField(unique=True)
    bonus_coins   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_usd     = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    title         = models.CharField(max_length=100)
    description   = models.TextField(blank=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Streak Milestone"
        ordering = ['streak_days']

    def __str__(self):
        return f"{self.streak_days}-day milestone: +{self.bonus_coins} coins"
