# api/referral/models.py — Complete Multi-Level Referral System
# পুরনো models.py replace করো
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class ReferralSettings(models.Model):
    """
    Admin panel থেকে referral commission rates change করা যাবে।
    পুরনো model রাখা হয়েছে + Level 2/3 rates add করা হয়েছে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # Signup bonuses (unchanged)
    direct_signup_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=20,
        help_text="নতুন user যে bonus পাবে")
    referrer_signup_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="যে refer করেছে সে যে bonus পাবে")

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

    # Backward compatibility
    @property
    def lifetime_commission_rate(self):
        return self.level1_commission_rate

    # Team bonus
    team_bonus_enabled = models.BooleanField(default=False)
    team_bonus_min_referrals = models.IntegerField(default=10)
    team_bonus_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    max_referral_depth = models.IntegerField(default=3)

    class Meta:
        verbose_name_plural = "Referral Settings"
        app_label = 'referral'

    def __str__(self):
        return f"Referral Settings (L1:{self.level1_commission_rate}% L2:{self.level2_commission_rate}% L3:{self.level3_commission_rate}%)"

    def get_rate_for_level(self, level: int) -> Decimal:
        rates = {
            1: self.level1_commission_rate,
            2: self.level2_commission_rate,
            3: self.level3_commission_rate,
        }
        return rates.get(level, Decimal('0'))


class Referral(models.Model):
    """
    Direct referral relationship।
    পুরনো model এর সব field রাখা হয়েছে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referrer')
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referred_user')

    # Level 1 relationship (direct)
    level = models.IntegerField(default=1)

    signup_bonus_given = models.BooleanField(default=False)
    total_commission_earned = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)

    # Fraud check
    registration_ip = models.GenericIPAddressField(null=True, blank=True)
    referrer_ip = models.GenericIPAddressField(null=True, blank=True)
    is_suspicious = models.BooleanField(default=False)
    suspicious_reason = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['referrer', 'referred_user']
        app_label = 'referral'
        indexes = [
            models.Index(fields=['referrer', 'created_at']),
        ]

    def __str__(self):
        return f"{self.referrer.username} → {self.referred_user.username}"


class ReferralChain(models.Model):
    """
    Multi-level chain tracking।
    Level 1: A refers B → A gets 10%
    Level 2: B refers C → A gets 5%, B gets 10%
    Level 3: C refers D → A gets 2%, B gets 5%, C gets 10%
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # যে earn করেছে (ancestor)
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_chain_beneficiary')
    # যে কাজ করে earn করেছে (descendant)
    earner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_chain_earner')

    level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text="1=direct, 2=grandchild, 3=great-grandchild"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['beneficiary', 'earner', 'level']
        app_label = 'referral'
        indexes = [
            models.Index(fields=['earner']),
            models.Index(fields=['beneficiary']),
        ]

    def __str__(self):
        return f"L{self.level}: {self.beneficiary.username} ← {self.earner.username}"


class ReferralEarning(models.Model):
    """
    প্রতিটি commission এর log।
    পুরনো model এর সাথে compatible, level field add করা হয়েছে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referral = models.ForeignKey(
        Referral, on_delete=models.CASCADE,
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
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="referred_user এর মূল earning যার উপর commission হিসাব হয়েছে")

    # Source tracking
    source_type = models.CharField(
        max_length=50, default='task',
        help_text="task, offer, bonus, etc.")
    source_id = models.CharField(max_length=100, null=True, blank=True)

    # পুরনো field (backward compat)
    source_task = models.ForeignKey(
        'tasks.MasterTask',
        on_delete=models.SET_NULL,
        null=True, blank=True)

    # Wallet transaction reference
    wallet_transaction_id = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        app_label = 'referral'
        indexes = [
            models.Index(fields=['referrer', '-created_at']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        return f"L{self.level} Commission: {self.referrer.username} ৳{self.amount}"


class ReferralLeaderboard(models.Model):
    """
    Weekly/Monthly top referrers।
    Celery task দিয়ে weekly snapshot নেওয়া হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    PERIOD_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('alltime', 'All Time'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_leaderboard')
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, null=True, blank=True)
    rank = models.IntegerField()
    total_referrals = models.IntegerField(default=0)
    active_referrals = models.IntegerField(default=0)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['user', 'period', 'period_start']
        ordering = ['rank']