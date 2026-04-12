from django.conf import settings
"""
SmartLink Schedule & Expiry System
World #1: Auto-activate/deactivate SmartLinks on schedule.
CPAlead has basic expiry. Ours supports full cron-style scheduling.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class SmartLinkSchedule(models.Model):
    """
    Schedule for automatic SmartLink activation/deactivation.
    Supports: one-time, daily, weekly, monthly schedules.
    """
    SCHEDULE_TYPES = [
        ('once',    'One Time'),
        ('daily',   'Daily (recurring)'),
        ('weekly',  'Weekly (recurring)'),
        ('monthly', 'Monthly (recurring)'),
    ]

    smartlink   = models.OneToOneField(
        'smartlink.SmartLink',
        on_delete=models.CASCADE,
        related_name='schedule',
    )
    is_enabled  = models.BooleanField(default=True)
    schedule_type = models.CharField(
        max_length=10, choices=SCHEDULE_TYPES, default='once'
    )

    # Activation window
    activate_at   = models.DateTimeField(
        null=True, blank=True,
        help_text=_('When to auto-activate this SmartLink.')
    )
    deactivate_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_('When to auto-deactivate this SmartLink.')
    )

    # For recurring: time-of-day window
    daily_start_hour = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('UTC hour to activate daily (0-23).')
    )
    daily_end_hour   = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('UTC hour to deactivate daily (0-23).')
    )

    # Cap-based auto-deactivation
    max_total_clicks  = models.PositiveBigIntegerField(
        null=True, blank=True,
        help_text=_('Auto-deactivate after this many total clicks.')
    )
    max_total_revenue = models.DecimalField(
        max_digits=12, decimal_places=4,
        null=True, blank=True,
        help_text=_('Auto-deactivate after this much total revenue.')
    )

    # Tracking
    last_activated_at   = models.DateTimeField(null=True, blank=True)
    last_deactivated_at = models.DateTimeField(null=True, blank=True)
    activation_count    = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sl_schedule'
        verbose_name = _('SmartLink Schedule')

    def __str__(self):
        return f"Schedule: [{self.smartlink.slug}] {self.schedule_type}"

    def should_be_active(self) -> bool:
        """Check if the SmartLink should currently be active based on schedule."""
        now = timezone.now()

        # Check total click cap
        if self.max_total_clicks:
            if self.smartlink.total_clicks >= self.max_total_clicks:
                return False

        # Check revenue cap
        if self.max_total_revenue:
            if self.smartlink.total_revenue >= self.max_total_revenue:
                return False

        # Check one-time schedule
        if self.schedule_type == 'once':
            if self.activate_at and now < self.activate_at:
                return False
            if self.deactivate_at and now > self.deactivate_at:
                return False
            return True

        # Check daily recurring
        if self.schedule_type == 'daily':
            if self.daily_start_hour is not None and self.daily_end_hour is not None:
                return self.daily_start_hour <= now.hour < self.daily_end_hour
            return True

        return True


class SmartLinkTemplate(models.Model):
    """
    Reusable SmartLink templates.
    Publisher can save a full config (targeting + pool + rotation) as a template
    and create new SmartLinks instantly from it.
    """
    publisher   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='smartlink_templates',
    )
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_public   = models.BooleanField(
        default=False,
        help_text=_('Public templates can be used by other publishers.')
    )
    config      = models.JSONField(
        default=dict,
        help_text=_(
            'Full SmartLink config JSON: targeting, rotation, fallback, etc.'
        )
    )
    use_count   = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sl_template'
        verbose_name = _('SmartLink Template')
        ordering     = ['-use_count', 'name']

    def __str__(self):
        return f"Template: {self.name} (used {self.use_count}×)"


class PublisherTier(models.Model):
    """
    Publisher quality tier system.
    Tiers unlock features and affect payout rates.
    Gold > Silver > Bronze > Standard > Under Review
    """
    TIER_CHOICES = [
        ('gold',         'Gold — Top Publisher'),
        ('silver',       'Silver — Trusted Publisher'),
        ('bronze',       'Bronze — Verified Publisher'),
        ('standard',     'Standard — New Publisher'),
        ('under_review', 'Under Review — Quality Issues'),
    ]

    publisher   = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='publisher_tier',
    )
    tier        = models.CharField(
        max_length=15, choices=TIER_CHOICES, default='standard',
        db_index=True,
    )

    # Benefits by tier
    max_smartlinks        = models.PositiveIntegerField(default=100)
    max_custom_domains    = models.PositiveIntegerField(default=1)
    api_rate_limit        = models.PositiveIntegerField(default=1000)  # per minute
    can_use_ml_rotation   = models.BooleanField(default=False)
    can_use_ab_testing    = models.BooleanField(default=False)
    can_use_pre_landers   = models.BooleanField(default=False)
    payout_bonus_percent  = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text=_('Bonus payout % on top of standard rate. Gold=5%, Silver=3%')
    )

    # Quality metrics snapshot
    last_quality_score    = models.FloatField(default=0.0)
    last_evaluated_at     = models.DateTimeField(null=True, blank=True)
    next_evaluation_at    = models.DateTimeField(null=True, blank=True)

    notes   = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sl_publisher_tier'
        verbose_name = _('Publisher Tier')

    def __str__(self):
        return f"{self.publisher.username} — {self.get_tier_display()}"

    @property
    def tier_emoji(self):
        return {'gold': '🥇', 'silver': '🥈', 'bronze': '🥉',
                'standard': '⚪', 'under_review': '🔴'}.get(self.tier, '⚪')
