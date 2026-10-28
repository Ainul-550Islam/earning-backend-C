# api/referral/models/analytics.py
# Analytics and reporting models
# ReferralInsight, ReferralConversionRate, TopReferrer, ReferralLTV
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class ReferralInsight(models.Model):
    """
    Daily aggregated referral insights।
    Celery task দিয়ে প্রতিদিন calculate করা হয়।
    Admin dashboard analytics এ use হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    date = models.DateField(db_index=True)

    # Referral volume
    new_referrals = models.IntegerField(
        default=0,
        help_text="নতুন referrals created on this date"
    )

    # By level
    new_referrals_l1 = models.IntegerField(default=0)
    new_referrals_l2 = models.IntegerField(default=0)
    new_referrals_l3 = models.IntegerField(default=0)

    # Commission
    commission_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    commission_l1 = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    commission_l2 = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    commission_l3 = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Conversion
    total_clicks = models.IntegerField(default=0)
    total_signups = models.IntegerField(default=0)
    conversion_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Signup conversion rate %"
    )

    # Fraud
    flagged_referrals = models.IntegerField(default=0)
    blocked_referrals = models.IntegerField(default=0)
    fraud_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Fraud rate as % of total referrals"
    )

    # Active referrers
    active_referrers = models.IntegerField(
        default=0,
        help_text="Unique referrers who had activity"
    )

    # Milestone bonuses paid
    milestone_bonuses_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Campaign performance
    campaign_commissions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Commission paid through active campaigns"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-date']
        unique_together = ['tenant', 'date']
        indexes = [
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return (
            f"Insight({self.date}: "
            f"{self.new_referrals} refs, "
            f"৳{self.commission_paid})"
        )


class ReferralConversionRate(models.Model):
    """
    Per-code conversion rate tracking।
    প্রতিটি referral code এর performance।
    Celery task দিয়ে daily update হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    code = models.ForeignKey(
        'referral.ReferralCode',
        on_delete=models.CASCADE,
        related_name='conversion_rates'
    )

    date = models.DateField()

    # Traffic
    clicks = models.IntegerField(default=0)
    unique_clicks = models.IntegerField(default=0)

    # Conversions
    signups = models.IntegerField(default=0)
    offers_completed = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)

    # Revenue
    commission_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Rates
    click_to_signup_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Signup conversion %"
    )
    signup_to_offer_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Offer completion rate after signup %"
    )
    conversion_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Overall conversion % (clicks → active users)"
    )

    # Source breakdown
    source_breakdown = models.JSONField(
        default=dict,
        help_text="Clicks/signups by source/UTM"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['code', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['code', '-date']),
        ]

    def __str__(self):
        return (
            f"ConversionRate("
            f"code={self.code.code} "
            f"date={self.date}: "
            f"{self.conversion_pct}%)"
        )

    def calculate_rates(self):
        """Rates recalculate করো।"""
        self.click_to_signup_pct = (
            round((self.signups / self.clicks) * 100, 2)
            if self.clicks > 0 else 0
        )
        self.signup_to_offer_pct = (
            round((self.offers_completed / self.signups) * 100, 2)
            if self.signups > 0 else 0
        )
        # Overall: click → (signup + completed offer)
        active = self.offers_completed or self.signups
        self.conversion_pct = (
            round((active / self.clicks) * 100, 2)
            if self.clicks > 0 else 0
        )
        self.save(update_fields=[
            'click_to_signup_pct', 'signup_to_offer_pct', 'conversion_pct'
        ])


class TopReferrer(models.Model):
    """
    Daily/weekly snapshot of top referrers।
    Leaderboard data।
    Celery task দিয়ে daily update হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    date = models.DateField()

    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('alltime', 'All Time'),
    ]
    period = models.CharField(
        max_length=10, choices=PERIOD_CHOICES, default='daily'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='top_referrer_snapshots'
    )

    rank = models.IntegerField()

    # Performance metrics
    referral_count = models.IntegerField(default=0)
    active_referral_count = models.IntegerField(default=0)
    commission_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Level breakdown
    l1_count = models.IntegerField(default=0)
    l2_count = models.IntegerField(default=0)
    l3_count = models.IntegerField(default=0)
    l1_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    l2_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    l3_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Rank change from previous period
    rank_change = models.IntegerField(
        default=0,
        help_text="Positive = improved, negative = dropped"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['rank']
        unique_together = ['date', 'period', 'user', 'tenant']
        indexes = [
            models.Index(fields=['date', 'period', 'rank']),
            models.Index(fields=['user', '-date']),
        ]

    def __str__(self):
        return (
            f"TopReferrer("
            f"{self.user.username}: "
            f"Rank #{self.rank} on {self.date} [{self.period}])"
        )


class ReferralLTV(models.Model):
    """
    Lifetime Value of a referred user।
    Tracks how much value a referred user has generated for the referrer।
    Weekly Celery task দিয়ে recalculate হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_ltv',
        help_text="The referred user whose LTV is being tracked"
    )

    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_users_ltv',
        help_text="The referrer who brought this user"
    )

    # Total value generated
    lifetime_value = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Total commission earned by referrer from this user"
    )

    # Total earnings by the referred user (base amount)
    total_user_earnings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Total amount earned by the referred user"
    )

    # Activity breakdown
    task_count = models.IntegerField(default=0)
    offer_count = models.IntegerField(default=0)
    deposit_count = models.IntegerField(default=0)
    withdrawal_count = models.IntegerField(default=0)

    # Engagement score (0-100)
    engagement_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Calculated engagement score"
    )

    # Retention
    days_active = models.IntegerField(
        default=0,
        help_text="Number of days user has been active"
    )
    consecutive_active_days = models.IntegerField(default=0)
    longest_streak_days = models.IntegerField(default=0)

    # Churn risk
    CHURN_RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('churned', 'Churned'),
    ]
    churn_risk = models.CharField(
        max_length=10, choices=CHURN_RISK_CHOICES, default='low'
    )

    # Category
    VALUE_CATEGORY_CHOICES = [
        ('high_value', 'High Value (top 10%)'),
        ('mid_value', 'Mid Value'),
        ('low_value', 'Low Value'),
        ('inactive', 'Inactive'),
    ]
    value_category = models.CharField(
        max_length=15, choices=VALUE_CATEGORY_CHOICES, default='low_value'
    )

    first_activity_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['user', 'referred_by']
        ordering = ['-lifetime_value']
        indexes = [
            models.Index(fields=['referred_by', '-lifetime_value']),
            models.Index(fields=['churn_risk']),
            models.Index(fields=['value_category']),
        ]

    def __str__(self):
        return (
            f"LTV("
            f"{self.user.username} referred by {self.referred_by.username}: "
            f"৳{self.lifetime_value} [{self.value_category}])"
        )

    def calculate_churn_risk(self) -> str:
        """Activity based churn risk calculate করো।"""
        from django.utils import timezone
        if not self.last_activity:
            return 'churned'
        days_since = (timezone.now() - self.last_activity).days
        if days_since > 60:
            return 'churned'
        elif days_since > 30:
            return 'high'
        elif days_since > 14:
            return 'medium'
        return 'low'

    def calculate_value_category(self, all_ltvs_qs=None) -> str:
        """LTV based value category calculate করো।"""
        if self.lifetime_value <= 0:
            return 'inactive'
        # Simple tier: can be replaced with percentile-based logic
        if self.lifetime_value >= 1000:
            return 'high_value'
        elif self.lifetime_value >= 100:
            return 'mid_value'
        return 'low_value'

    def recalculate(self):
        """All metrics recalculate করো।"""
        from .core import ReferralEarning
        from django.db.models import Sum, Count
        from django.utils import timezone

        earnings = ReferralEarning.objects.filter(
            referrer=self.referred_by,
            referred_user=self.user
        ).aggregate(
            total=Sum('amount'),
            source_total=Sum('source_amount'),
        )

        self.lifetime_value = earnings['total'] or Decimal('0')
        self.total_user_earnings = earnings['source_total'] or Decimal('0')

        # Activity
        task_earnings = ReferralEarning.objects.filter(
            referrer=self.referred_by,
            referred_user=self.user,
            source_type='task'
        ).count()
        offer_earnings = ReferralEarning.objects.filter(
            referrer=self.referred_by,
            referred_user=self.user,
            source_type='offer'
        ).count()

        self.task_count = task_earnings
        self.offer_count = offer_earnings

        # Last activity
        last = ReferralEarning.objects.filter(
            referrer=self.referred_by,
            referred_user=self.user
        ).order_by('-created_at').first()

        if last:
            self.last_activity = last.created_at

        self.churn_risk = self.calculate_churn_risk()
        self.value_category = self.calculate_value_category()
        self.save()