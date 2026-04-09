# api/djoyalty/models/engagement.py
from django.db import models
from ..choices import BADGE_TRIGGER_CHOICES, CHALLENGE_STATUS_CHOICES, CHALLENGE_TYPE_CHOICES
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import ActiveStreakManager, LongStreakManager, ActiveChallengeManager, CompletedChallengeParticipantManager


class DailyStreak(models.Model):
    """Customer daily login/purchase streak।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_dailystreak_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='daily_streak',
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    started_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveStreakManager()
    long_streaks = LongStreakManager()

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('tenant', 'customer')]

    def __str__(self):
        return f'{self.customer} streak={self.current_streak} days'


class StreakReward(models.Model):
    """Streak milestone reward log।"""

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='streak_rewards',
    )
    streak = models.ForeignKey(
        'DailyStreak', on_delete=models.CASCADE,
        related_name='rewards',
    )
    milestone_days = models.PositiveIntegerField()
    points_awarded = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('customer', 'milestone_days')]

    def __str__(self):
        return f'{self.customer} — {self.milestone_days} day streak reward: +{self.points_awarded} pts'


class Badge(models.Model):
    """Badge definition।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_badge_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    icon = models.CharField(max_length=8, default='🏅')
    trigger = models.CharField(max_length=32, choices=BADGE_TRIGGER_CHOICES, db_index=True)
    threshold = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    points_reward = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    is_active = models.BooleanField(default=True)
    is_unique = models.BooleanField(default=True, help_text='Only awarded once per customer')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['name']

    def __str__(self):
        return f'{self.icon} {self.name}'


class UserBadge(models.Model):
    """Customer earned badge।"""

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='user_badges',
    )
    badge = models.ForeignKey(
        'Badge', on_delete=models.CASCADE,
        related_name='user_badges',
    )
    awarded_at = models.DateTimeField(auto_now_add=True)
    points_awarded = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('customer', 'badge')]

    def __str__(self):
        return f'{self.customer} earned {self.badge}'


class Challenge(models.Model):
    """Loyalty challenge।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_challenge_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    challenge_type = models.CharField(max_length=32, choices=CHALLENGE_TYPE_CHOICES)
    target_value = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    points_reward = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    status = models.CharField(max_length=16, choices=CHALLENGE_STATUS_CHOICES, default='upcoming', db_index=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active_challenges = ActiveChallengeManager()

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.name} [{self.status}]'


class ChallengeParticipant(models.Model):
    """Challenge participation record।"""

    challenge = models.ForeignKey(
        'Challenge', on_delete=models.CASCADE,
        related_name='participants',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='challenge_participations',
    )
    progress = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    status = models.CharField(max_length=16, choices=CHALLENGE_STATUS_CHOICES, default='active', db_index=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    points_awarded = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)

    objects = models.Manager()
    completed_participants = CompletedChallengeParticipantManager()

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('challenge', 'customer')]

    def __str__(self):
        return f'{self.customer} in {self.challenge} — {self.progress}/{self.challenge.target_value}'


class Milestone(models.Model):
    """Loyalty milestone definition।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_milestone_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    milestone_type = models.CharField(
        max_length=32,
        choices=[
            ('total_spend', 'Total Spend'),
            ('total_points', 'Total Points'),
            ('transaction_count', 'Transaction Count'),
            ('streak_days', 'Streak Days'),
        ],
    )
    threshold = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    points_reward = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.name} @ {self.threshold}'


class UserMilestone(models.Model):
    """Customer reached milestone।"""

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='user_milestones',
    )
    milestone = models.ForeignKey(
        'Milestone', on_delete=models.CASCADE,
        related_name='user_milestones',
    )
    reached_at = models.DateTimeField(auto_now_add=True)
    points_awarded = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('customer', 'milestone')]

    def __str__(self):
        return f'{self.customer} reached {self.milestone}'
