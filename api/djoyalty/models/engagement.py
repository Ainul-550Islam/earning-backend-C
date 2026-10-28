# api/djoyalty/models/engagement.py
"""
Djoyalty Engagement Models।
DailyStreak, StreakReward, Badge, UserBadge,
Challenge, ChallengeParticipant, Milestone, UserMilestone।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class DailyStreak(models.Model):
    """
    Customer এর daily activity streak।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='daily_streaks',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='daily_streaks',
    )

    current_streak = models.PositiveIntegerField(default=0, verbose_name='Current Streak (days)')
    longest_streak = models.PositiveIntegerField(default=0, verbose_name='Longest Streak (days)')
    last_activity_date = models.DateField(null=True, blank=True, verbose_name='Last Activity Date')
    freeze_count = models.PositiveIntegerField(default=0, verbose_name='Freeze Used Count')
    is_active = models.BooleanField(default=True, verbose_name='Streak Active')
    started_at = models.DateField(null=True, blank=True, verbose_name='Streak Started At')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Daily Streak'
        verbose_name_plural = 'Daily Streaks'
        unique_together = [('customer', 'tenant')]
        ordering = ['-current_streak']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['last_activity_date']),
        ]

    def __str__(self):
        return f'Streak({self.customer.code}: {self.current_streak} days)'


class StreakReward(models.Model):
    """
    Reward given for reaching a streak milestone।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='streak_rewards',
        verbose_name='Customer',
    )
    streak = models.ForeignKey(
        DailyStreak,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='rewards',
        verbose_name='Streak',
    )
    milestone_days = models.PositiveIntegerField(verbose_name='Milestone Days')
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    badge = models.ForeignKey(
        'djoyalty.Badge',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='streak_rewards',
    )
    multiplier_hours = models.PositiveIntegerField(default=0, verbose_name='Bonus Multiplier Hours')
    awarded_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Streak Reward'
        verbose_name_plural = 'Streak Rewards'
        unique_together = [('customer', 'milestone_days')]
        ordering = ['-awarded_at']
        # AUDIT FIX (4): (customer, awarded_at) for customer reward history.
        indexes = [
            models.Index(fields=['customer', 'awarded_at'],
                         name='streakrew_customer_time_idx'),
            models.Index(fields=['milestone_days'],
                         name='streakrew_milestone_idx'),
        ]

    def __str__(self):
        return f'StreakReward({self.customer.code}: {self.milestone_days} days -> {self.points_awarded} pts)'


class Badge(models.Model):
    """
    Achievement badge definition।
    """
    name = models.CharField(max_length=200, unique=True, verbose_name='Badge Name')
    description = models.TextField(null=True, blank=True)
    icon = models.CharField(max_length=200, default='🏅', verbose_name='Icon (emoji or URL)')
    rarity = models.CharField(
        max_length=20,
        choices=[
            ('common', 'Common'), ('rare', 'Rare'),
            ('epic', 'Epic'), ('legendary', 'Legendary'),
        ],
        default='common',
        verbose_name='Rarity',
    )
    trigger = models.CharField(
        max_length=50,
        choices=[
            ('transaction_count', 'Transaction Count'),
            ('total_points', 'Total Points Earned'),
            ('total_spend', 'Total Spend'),
            ('streak_days', 'Streak Days'),
            ('referral_count', 'Referral Count'),
            ('tier_achieved', 'Tier Achieved'),
            ('challenge_completed', 'Challenge Completed'),
            ('first_purchase', 'First Purchase'),
            ('manual', 'Manual Award'),
        ],
        verbose_name='Trigger',
    )
    threshold = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1'),
        verbose_name='Threshold Value',
    )
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Reward',
    )
    is_active = models.BooleanField(default=True)
    is_unique = models.BooleanField(
        default=True,
        verbose_name='Award Once Only',
        help_text='If True, customer earns this badge only once',
    )
    sort_order = models.PositiveIntegerField(default=0)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
        ordering = ['sort_order', 'name']
        # AUDIT FIX (4): (trigger, is_active) covers badge eligibility checks;
        # (rarity,) for UI filtering by rarity.
        indexes = [
            models.Index(fields=['trigger', 'is_active'],
                         name='badge_trigger_active_idx'),
            models.Index(fields=['rarity', 'is_active'],
                         name='badge_rarity_active_idx'),
        ]

    def __str__(self):
        return f'Badge({self.name} [{self.rarity}])'


class UserBadge(models.Model):
    """
    Customer এর earned badge record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='user_badges',
        verbose_name='Customer',
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='user_badges',
        verbose_name='Badge',
    )
    points_awarded = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Awarded',
    )
    earned_at = models.DateTimeField(default=timezone.now, verbose_name='Earned At')
    is_pinned = models.BooleanField(default=False, verbose_name='Pinned to Profile')
    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'User Badge'
        verbose_name_plural = 'User Badges'
        ordering = ['-earned_at']
        indexes = [
            models.Index(fields=['customer', 'badge']),
        ]

    def __str__(self):
        return f'UserBadge({self.customer.code}: {self.badge.name})'


class Challenge(models.Model):
    """
    Loyalty challenge -- customers complete tasks to earn rewards।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='challenges',
    )
    name = models.CharField(max_length=200, verbose_name='Challenge Name')
    description = models.TextField(null=True, blank=True)
    challenge_type = models.CharField(
        max_length=30,
        choices=[
            ('individual', 'Individual'), ('team', 'Team'),
            ('spend', 'Spend'), ('transaction', 'Transaction Count'),
            ('leaderboard', 'Leaderboard'),
        ],
        default='individual',
        verbose_name='Challenge Type',
    )
    target_action = models.CharField(max_length=100, null=True, blank=True, verbose_name='Target Action')
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    target_count = models.PositiveIntegerField(default=0)
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Reward',
    )
    bonus_points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    badge_reward = models.ForeignKey(
        Badge,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='challenge_rewards',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'), ('active', 'Active'),
            ('ended', 'Ended'), ('paused', 'Paused'),
        ],
        default='draft',
    )
    start_date = models.DateTimeField(verbose_name='Start Date')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='End Date')
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    image = models.URLField(null=True, blank=True)
    terms = models.TextField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Challenge'
        verbose_name_plural = 'Challenges'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f'Challenge({self.name} [{self.status}])'


class ChallengeParticipant(models.Model):
    """
    Customer এর challenge participation record।
    """
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='Challenge',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='challenge_participations',
        verbose_name='Customer',
    )
    progress = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='active',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    joined_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Challenge Participant'
        verbose_name_plural = 'Challenge Participants'
        unique_together = [('challenge', 'customer')]
        indexes = [
            models.Index(fields=['challenge', 'status']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f'ChallengeParticipant({self.challenge.name}: {self.customer.code} [{self.status}])'


class Milestone(models.Model):
    """
    Loyalty milestone -- specific achievement threshold।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='milestones',
    )
    name = models.CharField(max_length=200, verbose_name='Milestone Name')
    description = models.TextField(null=True, blank=True)
    milestone_type = models.CharField(
        max_length=30,
        choices=[
            ('total_points', 'Total Points Earned'),
            ('total_spend', 'Total Spend'),
            ('transaction_count', 'Transaction Count'),
            ('referral_count', 'Referral Count'),
            ('streak_days', 'Streak Days'),
        ],
        verbose_name='Milestone Type',
    )
    threshold = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Threshold',
    )
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Reward',
    )
    reward_badge = models.ForeignKey(
        Badge,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='milestone_rewards',
    )
    is_repeatable = models.BooleanField(default=False, verbose_name='Repeatable Milestone')
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Milestone'
        verbose_name_plural = 'Milestones'
        ordering = ['milestone_type', 'threshold']
        # AUDIT FIX (4): (tenant, milestone_type) for type-based lookup;
        # (tenant, is_active) for active milestone listing.
        indexes = [
            models.Index(fields=['tenant', 'milestone_type'],
                         name='milestone_tenant_type_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='milestone_tenant_active_idx'),
        ]

    def __str__(self):
        return f'Milestone({self.name}: {self.milestone_type} >= {self.threshold})'


class UserMilestone(models.Model):
    """
    Customer এর achieved milestone record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='user_milestones',
        verbose_name='Customer',
    )
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name='user_milestones',
        verbose_name='Milestone',
    )
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    achieved_at = models.DateTimeField(default=timezone.now, verbose_name='Achieved At')
    times_achieved = models.PositiveIntegerField(default=1, verbose_name='Times Achieved')
    last_reward_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'User Milestone'
        verbose_name_plural = 'User Milestones'
        unique_together = [('customer', 'milestone')]
        ordering = ['-achieved_at']
        # AUDIT FIX (4): (customer, achieved_at) for achievement timeline.
        indexes = [
            models.Index(fields=['customer', 'achieved_at'],
                         name='milestone_customer_time_idx'),
        ]

    def __str__(self):
        return f'UserMilestone({self.customer.code}: {self.milestone.name})'
