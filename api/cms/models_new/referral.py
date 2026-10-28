# api/cms/models_new/referral.py
"""
Referral System — CMS owns this entirely.
CPAlead gives 5% of every referral's earnings.
Rule: এক কাজের জন্য একটাই মালিক — CMS manages referral, nobody else.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import F


class ReferralCode(models.Model):
    """Each user gets one unique referral code."""
    user        = models.OneToOneField(settings.AUTH_USER_MODEL,
                                       on_delete=models.CASCADE,
                                       related_name='cms_referral_code')
    code        = models.CharField(max_length=20, unique=True, db_index=True)
    is_active   = models.BooleanField(default=True)
    total_referrals   = models.PositiveIntegerField(default=0)
    total_bonus_usd   = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_bonus_coins = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Referral Code"

    def __str__(self):
        return f"{self.user.username} → code:{self.code}"

    @classmethod
    def get_or_create_for_user(cls, user):
        try:
            return cls.objects.get(user=user)
        except cls.DoesNotExist:
            import hashlib, time
            raw = f"{user.id}_{user.username}_{time.time()}"
            code = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
            return cls.objects.create(user=user, code=code)


class ReferralRelationship(models.Model):
    """Tracks who referred whom."""
    referrer    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    related_name='cms_referrals_made')
    referred    = models.OneToOneField(settings.AUTH_USER_MODEL,
                                       on_delete=models.CASCADE,
                                       related_name='referred_by_rel')
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.SET_NULL,
                                      null=True, related_name='relationships')
    # Bonus tracking
    bonus_rate  = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.05'))  # 5%
    total_bonus_earned_usd  = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_bonus_earned_coins = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active   = models.BooleanField(default=True)
    joined_at   = models.DateTimeField(default=timezone.now)
    expires_at  = models.DateTimeField(null=True, blank=True,
                                       help_text="CPAlead referral active for 6 months")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Referral Relationship"
        indexes = [
            models.Index(fields=['referrer', 'is_active']),
            models.Index(fields=['referred']),
        ]

    def __str__(self):
        return f"{self.referrer.username} → referred {self.referred.username}"

    def is_still_active(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class ReferralEarning(models.Model):
    """Log of every referral bonus earned."""
    EARNING_SOURCES = [
        ('offer_complete', 'Referred user completed offer'),
        ('banner_click',   'Referred user clicked banner'),
        ('content_read',   'Referred user read content'),
        ('manual',         'Manual admin bonus'),
    ]
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    referrer      = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.CASCADE,
                                      related_name='referral_earnings')
    referred      = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.CASCADE,
                                      related_name='referral_earnings_generated')
    relationship  = models.ForeignKey(ReferralRelationship, on_delete=models.CASCADE,
                                      related_name='earnings')
    source        = models.CharField(max_length=30, choices=EARNING_SOURCES,
                                     default='offer_complete')
    original_amount_usd  = models.DecimalField(max_digits=10, decimal_places=4)
    bonus_rate    = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.05'))
    bonus_usd     = models.DecimalField(max_digits=10, decimal_places=4)
    bonus_coins   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lead_id       = models.CharField(max_length=200, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Referral Earning"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referrer', 'created_at']),
            models.Index(fields=['lead_id']),
        ]

    def __str__(self):
        return f"{self.referrer.username} earned ${self.bonus_usd} from {self.referred.username}"
