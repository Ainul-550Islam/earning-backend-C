# api/referral/models/core.py
# Core referral models — fixed + enhanced
# ReferralSettings: hardcoded bonus removed, linked to ReferralCampaign
# ReferralLink: keep existing
# ReferralEarning: keep existing
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class ReferralSettings(models.Model):
    """
    Admin panel থেকে referral commission rates change করা যাবে।
    Fix: hardcoded bonus removed → linked to active ReferralCampaign
    Level 1/2/3 commission rates configurable।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # Signup bonuses — these are fallback defaults when no campaign is active
    direct_signup_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=20,
        help_text="Fallback: নতুন user যে bonus পাবে (campaign না থাকলে)")
    referrer_signup_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="Fallback: যে refer করেছে সে যে bonus পাবে (campaign না থাকলে)")

    # Commission rates — 3 levels
    level1_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Level 1 commission % (direct referral)"
    )
    level2_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=5,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text="Level 2 commission % (referral এর referral)"
    )
    level3_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Level 3 commission %"
    )

    # Active campaign link — যদি campaign থাকে তাহলে campaign এর rate/bonus use করো
    active_campaign = models.ForeignKey(
        'referral.ReferralCampaign',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='settings_linked',
        help_text="Active campaign থাকলে campaign এর bonus/multiplier apply হবে"
    )

    # Backward compatibility property
    @property
    def lifetime_commission_rate(self):
        return self.level1_commission_rate

    # Team bonus
    team_bonus_enabled = models.BooleanField(default=False)
    team_bonus_min_referrals = models.IntegerField(default=10)
    team_bonus_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=1, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    max_referral_depth = models.IntegerField(default=3)

    # Min withdrawal before commission is paid
    min_payout_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=100,
        help_text="Minimum amount before commission payout"
    )

    # Commission hold period (days)
    commission_hold_days = models.IntegerField(
        default=7,
        help_text="Commission কত দিন hold থাকবে release হওয়ার আগে"
    )

    # Self-referral protection
    allow_self_referral = models.BooleanField(default=False)

    # Cookie/tracking duration
    referral_cookie_days = models.IntegerField(default=30)

    class Meta:
        verbose_name_plural = "Referral Settings"
        app_label = 'referral'

    def __str__(self):
        return (
            f"Referral Settings "
            f"(L1:{self.level1_commission_rate}% "
            f"L2:{self.level2_commission_rate}% "
            f"L3:{self.level3_commission_rate}%)"
        )

    def get_rate_for_level(self, level: int) -> Decimal:
        """Level অনুযায়ী commission rate দাও — campaign multiplier apply করো।"""
        base_rates = {
            1: self.level1_commission_rate,
            2: self.level2_commission_rate,
            3: self.level3_commission_rate,
        }
        base = base_rates.get(level, Decimal('0'))

        # Active campaign এ multiplier থাকলে apply করো
        if self.active_campaign_id:
            try:
                campaign = self.active_campaign
                if campaign and campaign.is_currently_active():
                    base = base * campaign.bonus_multiplier
            except Exception:
                pass

        return base

    def get_effective_signup_bonus(self, bonus_type: str = 'referrer') -> Decimal:
        """
        Active campaign থাকলে campaign bonus দেখো।
        bonus_type: 'referrer' বা 'direct'
        """
        if self.active_campaign_id:
            try:
                campaign = self.active_campaign
                if campaign and campaign.is_currently_active():
                    if bonus_type == 'referrer':
                        return self.referrer_signup_bonus * campaign.bonus_multiplier
                    return self.direct_signup_bonus * campaign.bonus_multiplier
            except Exception:
                pass

        if bonus_type == 'referrer':
            return self.referrer_signup_bonus
        return self.direct_signup_bonus


class ReferralLink(models.Model):
    """
    User এর shareable referral link।
    Custom alias support + click tracking।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_link'
    )

    # Auto-generated short code (6-8 chars)
    code = models.CharField(max_length=20, unique=True, db_index=True)

    # Custom vanity alias (e.g. /ref/john)
    custom_alias = models.SlugField(
        max_length=50, unique=True, null=True, blank=True,
        help_text="Custom readable alias for link"
    )

    # UTM parameters for tracking
    utm_source = models.CharField(max_length=100, blank=True, default='')
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=100, blank=True, default='')

    # Stats
    total_clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    total_signups = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"ReferralLink({self.user.username}: {self.code})"

    def get_full_url(self, base_url: str = '') -> str:
        alias = self.custom_alias or self.code
        if base_url:
            return f"{base_url.rstrip('/')}/ref/{alias}"
        return f"/ref/{alias}"

    def record_click(self, is_unique: bool = False):
        self.total_clicks += 1
        if is_unique:
            self.unique_clicks += 1
        self.save(update_fields=['total_clicks', 'unique_clicks'])

    @property
    def conversion_rate(self) -> float:
        if self.total_clicks == 0:
            return 0.0
        return round((self.total_signups / self.total_clicks) * 100, 2)


class ReferralEarning(models.Model):
    """
    প্রতিটি commission এর log।
    পুরনো model এর সাথে compatible, level field add করা হয়েছে।
    source_type, source_id, wallet_transaction_id included।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referral = models.ForeignKey(
        'referral.Referral', on_delete=models.CASCADE,
        null=True, blank=True)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referralearning_referrer')
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referralearning_referred_user')

    # Commission details
    level = models.IntegerField(default=1, help_text="1, 2, or 3")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    source_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="referred_user এর মূল earning যার উপর commission হিসাব হয়েছে")

    # Source tracking
    source_type = models.CharField(
        max_length=50, default='task',
        help_text="task, offer, bonus, withdrawal, etc.")
    source_id = models.CharField(max_length=100, null=True, blank=True)

    # Backward compat — পুরনো field রাখা হয়েছে
    source_task = models.ForeignKey(
        'tasks.MasterTask',
        on_delete=models.SET_NULL,
        null=True, blank=True)

    # Wallet transaction reference
    wallet_transaction_id = models.CharField(
        max_length=100, null=True, blank=True)

    # Commission status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('held', 'Held'),
        ('released', 'Released'),
        ('clawed_back', 'Clawed Back'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='released')

    # Campaign multiplier snapshot
    campaign_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=1,
        help_text="Campaign multiplier যা apply হয়েছিল")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        app_label = 'referral'
        indexes = [
            models.Index(fields=['referrer', '-created_at']),
            models.Index(fields=['level']),
            models.Index(fields=['status']),
            models.Index(fields=['referred_user', '-created_at']),
        ]

    def __str__(self):
        return (
            f"L{self.level} Commission: "
            f"{self.referrer.username} ৳{self.amount} "
            f"[{self.status}]"
        )