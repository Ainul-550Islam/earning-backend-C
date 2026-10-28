# api/referral/models_legacy.py
# Legacy models from old models.py — Referral, ReferralChain, ReferralLeaderboard only.
# NOTE: ReferralSettings and ReferralEarning are now in models/core.py
# These are kept here because migrations 0001-0004 reference them.
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Referral(models.Model):
    """
    Direct referral relationship (Level 1).
    পুরনো model সংরক্ষিত — backward compatible।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referral_referral_tenant',
        db_index=True,
    )
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referrer',
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referred_user',
    )
    level = models.IntegerField(default=1)
    signup_bonus_given = models.BooleanField(default=False)
    total_commission_earned = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
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
    beneficiary = ancestor who earns commission
    earner = descendant whose activity triggers commission
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referral_referralchain_tenant',
        db_index=True,
    )
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_chain_beneficiary',
    )
    earner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_chain_earner',
    )
    level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text="1=direct, 2=grandchild, 3=great-grandchild",
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


class ReferralLeaderboard(models.Model):
    """Weekly/Monthly top referrers snapshot।"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referral_referralleaderboard_tenant',
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
        related_name='referral_leaderboard',
    )
    period = models.CharField(
        max_length=10, choices=PERIOD_CHOICES, null=True, blank=True,
    )
    rank = models.IntegerField()
    total_referrals = models.IntegerField(default=0)
    active_referrals = models.IntegerField(default=0)
    total_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, null=True, blank=True,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['user', 'period', 'period_start']
        ordering = ['rank']

    def __str__(self):
        return f"Leaderboard({self.user.username} rank={self.rank} [{self.period}])"