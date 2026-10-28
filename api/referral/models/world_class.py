# api/referral/models/world_class.py
# World-class features not in any basic system:
# Viral coefficient, streak bonus, surge bonus,
# affiliate portal, commission tiers, city rates,
# credit wallet, multi-level rewards
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


# ── 1. Viral Coefficient Tracking ─────────────────────────────────────────────

class ViralCoefficient(models.Model):
    """
    Track viral growth: K-factor = (invites sent × conversion rate).
    K > 1 = viral growth. Dropbox had K=0.5, PayPal had K=1.7.
    Updated daily via Celery task.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_viral_tenant',
    )
    date = models.DateField(db_index=True)

    # Raw numbers
    total_referrers       = models.IntegerField(default=0)
    total_invites_sent    = models.IntegerField(default=0)   # email + share
    total_conversions     = models.IntegerField(default=0)
    avg_invites_per_user  = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    conversion_rate_pct   = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # K-factor = avg_invites × (conversion_rate / 100)
    k_factor              = models.DecimalField(max_digits=6, decimal_places=4, default=0)

    # Trend
    k_factor_7d_avg       = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    is_viral              = models.BooleanField(default=False)  # k_factor >= 1.0

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-date']
        unique_together = ['tenant', 'date']

    def __str__(self):
        return f"ViralK({self.date}: K={self.k_factor})"

    @property
    def growth_status(self) -> str:
        if self.k_factor >= 1.0: return 'viral'
        if self.k_factor >= 0.5: return 'healthy'
        return 'weak'


# ── 2. Streak Bonus ────────────────────────────────────────────────────────────

class ReferralStreakBonus(models.Model):
    """
    Bonus for consistent referral activity.
    Example: Get 3 referrals in 7 days = 10% bonus multiplier for next 7 days.
    Uber Eats uses streak bonuses for drivers. Apply same to referrers.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_streak_tenant',
    )
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')

    # Streak requirements
    streak_days          = models.IntegerField(default=7, help_text='Days window for streak')
    min_referrals_needed = models.IntegerField(default=3, help_text='Referrals in streak_days')

    # Reward
    bonus_multiplier     = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.1'),
        help_text='1.1 = 10% bonus on all commissions during active streak',
    )
    bonus_duration_days  = models.IntegerField(default=7, help_text='How long bonus lasts')
    bonus_cash_amount    = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='One-time cash bonus on streak achievement',
    )

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Streak({self.name}: {self.min_referrals_needed}/{self.streak_days}d)"


class UserStreakTracker(models.Model):
    """Tracks each user's current referral streak."""
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_streaktracker_tenant',
    )
    user                    = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referral_streak',
    )
    current_streak_days     = models.IntegerField(default=0)
    longest_streak_days     = models.IntegerField(default=0)
    last_referral_date      = models.DateField(null=True, blank=True)
    total_streak_bonuses    = models.IntegerField(default=0)
    active_multiplier       = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    multiplier_expires_at   = models.DateTimeField(null=True, blank=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Streak({self.user.username}: {self.current_streak_days}d)"

    @property
    def is_on_streak(self) -> bool:
        if not self.last_referral_date:
            return False
        from django.utils import timezone
        from datetime import timedelta
        yesterday = timezone.now().date() - timedelta(days=1)
        return self.last_referral_date >= yesterday

    @property
    def has_active_multiplier(self) -> bool:
        from django.utils import timezone
        if not self.multiplier_expires_at:
            return False
        return timezone.now() < self.multiplier_expires_at


# ── 3. Surge Bonus (Time-Based) ────────────────────────────────────────────────

class ReferralSurgeBonus(models.Model):
    """
    Time-based surge bonus — like Uber surge pricing, but for referrals.
    Examples:
    - Weekend bonus: 2x commission Fri-Sun
    - Happy hour: 1.5x commission 6-9 PM
    - New user surge: 3x on first 100 referrals of a campaign
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_surge_tenant',
    )
    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True, default='')

    SURGE_TYPE = [
        ('time_window', 'Specific Time Window'),
        ('day_of_week', 'Day of Week'),
        ('first_n', 'First N Referrals'),
        ('count_based', 'When total referrals hit N'),
    ]
    surge_type      = models.CharField(max_length=15, choices=SURGE_TYPE, default='time_window')

    # Time window
    start_hour      = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(23)])
    end_hour        = models.IntegerField(default=23, validators=[MinValueValidator(0), MaxValueValidator(23)])
    days_of_week    = models.CharField(
        max_length=20, default='0,1,2,3,4,5,6',
        help_text='Comma-separated: 0=Mon, 6=Sun',
    )

    # Count-based
    trigger_count   = models.IntegerField(default=0, help_text='For first_n / count_based type')

    # Reward
    multiplier      = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.0'))
    is_active       = models.BooleanField(default=True)
    starts_at       = models.DateTimeField(null=True, blank=True)
    ends_at         = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        return f"Surge({self.name}: {self.multiplier}x)"

    def is_currently_active(self) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if not self.is_active:
            return False
        if self.surge_type == 'day_of_week':
            active_days = [int(d) for d in self.days_of_week.split(',')]
            return now.weekday() in active_days
        if self.surge_type == 'time_window':
            return self.start_hour <= now.hour <= self.end_hour
        return True


# ── 4. Commission Tiers (Per-User Progression) ────────────────────────────────

class CommissionTierProgression(models.Model):
    """
    PartnerStack-style tier progression.
    User starts at Bronze, progresses to Silver/Gold/Platinum based on performance.
    Higher tier = higher commission rates automatically.

    Bronze:   0-9 active referrals  = default rates
    Silver:   10-49 active referrals = +2% on all levels
    Gold:     50-99 active referrals = +5% on all levels
    Platinum: 100+ active referrals  = +10% on all levels
    """
    TIER = [
        ('bronze', 'Bronze'), ('silver', 'Silver'),
        ('gold', 'Gold'), ('platinum', 'Platinum'),
        ('custom', 'Custom'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_commtier_tenant',
    )
    name                    = models.CharField(max_length=100)
    tier_level              = models.CharField(max_length=10, choices=TIER, default='bronze')
    min_active_referrals    = models.IntegerField(default=0)
    min_total_commission    = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Bonus on top of base rates
    level1_bonus_pct        = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    level2_bonus_pct        = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    level3_bonus_pct        = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # UI
    color_code              = models.CharField(max_length=7, default='#CD7F32')
    icon                    = models.CharField(max_length=50, blank=True, default='🥉')
    badge_image_url         = models.URLField(blank=True, default='')
    perks_description       = models.TextField(blank=True, default='')

    is_active               = models.BooleanField(default=True)
    display_order           = models.IntegerField(default=0)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['display_order', 'min_active_referrals']

    def __str__(self):
        return f"Tier({self.name}: {self.level1_bonus_pct}% L1 bonus)"


class UserCommissionTier(models.Model):
    """Tracks each user's current commission tier."""
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_usertier_tenant',
    )
    user                    = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referral_commission_tier',
    )
    current_tier            = models.ForeignKey(
        CommissionTierProgression, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users',
    )
    tier_achieved_at        = models.DateTimeField(null=True, blank=True)
    total_active_referrals  = models.IntegerField(default=0)
    total_commission_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Effective rates (base + tier bonus)
    effective_l1_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    effective_l2_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    effective_l3_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=2)

    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        tier_name = self.current_tier.name if self.current_tier else 'Bronze'
        return f"UserTier({self.user.username}: {tier_name})"

    def recalculate_rates(self) -> None:
        """Recalculate effective rates based on current tier + base settings."""
        from api.referral.models import ReferralSettings
        settings = ReferralSettings.objects.first()
        base_l1 = settings.level1_commission_rate if settings else Decimal('10')
        base_l2 = settings.level2_commission_rate if settings else Decimal('5')
        base_l3 = settings.level3_commission_rate if settings else Decimal('2')

        if self.current_tier:
            self.effective_l1_rate = base_l1 + self.current_tier.level1_bonus_pct
            self.effective_l2_rate = base_l2 + self.current_tier.level2_bonus_pct
            self.effective_l3_rate = base_l3 + self.current_tier.level3_bonus_pct
        else:
            self.effective_l1_rate = base_l1
            self.effective_l2_rate = base_l2
            self.effective_l3_rate = base_l3
        self.save(update_fields=['effective_l1_rate', 'effective_l2_rate', 'effective_l3_rate'])


# ── 5. Affiliate Portal ────────────────────────────────────────────────────────

class AffiliateProfile(models.Model):
    """
    Public-facing affiliate profile — like PartnerStack affiliate marketplace.
    Users can have a profile showcasing their referral performance.
    """
    STATUS = [
        ('pending', 'Pending Review'), ('active', 'Active'),
        ('suspended', 'Suspended'), ('rejected', 'Rejected'),
    ]
    TRAFFIC_TYPE = [
        ('social', 'Social Media'), ('content', 'Content/Blog'),
        ('email', 'Email List'), ('paid', 'Paid Traffic'),
        ('community', 'Community/Forum'), ('influencer', 'Influencer'),
        ('other', 'Other'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_affiliateprofile_tenant',
    )
    user                = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='affiliate_profile',
    )
    display_name        = models.CharField(max_length=200, blank=True)
    bio                 = models.TextField(max_length=1000, blank=True, default='')
    website_url         = models.URLField(blank=True, default='')
    traffic_type        = models.CharField(max_length=15, choices=TRAFFIC_TYPE, default='social')
    monthly_traffic     = models.IntegerField(default=0, help_text='Estimated monthly visitors')
    social_following    = models.IntegerField(default=0)

    # Portal stats (public)
    total_referrals     = models.IntegerField(default=0)
    success_rate_pct    = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    avg_ltv_generated   = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Status
    status              = models.CharField(max_length=10, choices=STATUS, default='pending')
    approved_at         = models.DateTimeField(null=True, blank=True)
    approved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_affiliates',
    )
    rejection_reason    = models.TextField(blank=True, default='')

    # Payout info
    payment_method      = models.CharField(
        max_length=20,
        choices=[('bkash', 'bKash'), ('nagad', 'Nagad'), ('bank', 'Bank'), ('paypal', 'PayPal'), ('crypto', 'Crypto')],
        blank=True, default='',
    )
    payment_account     = models.CharField(max_length=200, blank=True, default='')

    is_public           = models.BooleanField(default=False, help_text='Show in affiliate directory')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Affiliate({self.display_name or self.user.username}: {self.status})"


# ── 6. Referral Credit Wallet ──────────────────────────────────────────────────

class ReferralCreditBalance(models.Model):
    """
    Separate referral credit balance — like Airbnb Travel Credit.
    Users can accumulate referral credits and spend them.
    Different from main wallet — can have different rules/restrictions.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_creditbalance_tenant',
    )
    user                = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referral_credit_balance',
    )
    balance             = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_earned     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_spent      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance     = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Expiry (some credits expire if unused)
    credits_expire_days = models.IntegerField(default=0, help_text='0 = never expire')
    last_credit_at      = models.DateTimeField(null=True, blank=True)
    credits_expire_at   = models.DateTimeField(null=True, blank=True)

    updated_at          = models.DateTimeField(auto_now=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Credits({self.user.username}: {self.balance})"


class ReferralCreditTransaction(models.Model):
    """Credit ledger — every credit add/spend tracked."""
    TYPE = [
        ('earned_referral', 'Earned — Referral Signup'),
        ('earned_milestone', 'Earned — Milestone'),
        ('earned_contest', 'Earned — Contest Prize'),
        ('spent_withdrawal', 'Spent — Withdrawal'),
        ('spent_purchase', 'Spent — Purchase'),
        ('expired', 'Expired'),
        ('adjusted', 'Admin Adjustment'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_credittxn_tenant',
    )
    credit_balance      = models.ForeignKey(
        ReferralCreditBalance, on_delete=models.CASCADE,
        related_name='transactions',
    )
    transaction_type    = models.CharField(max_length=20, choices=TYPE)
    amount              = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after       = models.DecimalField(max_digits=12, decimal_places=2)
    description         = models.CharField(max_length=500, blank=True, default='')
    reference_id        = models.CharField(max_length=100, blank=True, default='')
    expires_at          = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        return f"Credit({self.credit_balance.user.username}: {'+' if self.amount > 0 else ''}{self.amount})"