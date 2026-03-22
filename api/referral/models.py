
# referral/models.py
from django.db import models
from django.conf import settings

class ReferralSettings(models.Model):
    """Admin can change referral bonuses without code changes"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    direct_signup_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=20)
    referrer_signup_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    lifetime_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)  # Percentage
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Referral Settings"
    
    def __str__(self):
        return "Referral Settings"


class Referral(models.Model):
    """Track referral relationships"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referrer'
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referral_referred_user'
    )
    signup_bonus_given = models.BooleanField(default=False)
    total_commission_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['referrer', 'referred_user']


class ReferralEarning(models.Model):
    """Log each commission earned"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referralearning_referrer'
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_referralearning_referred_user'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    source_task = models.ForeignKey('api.EarningTask', on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']