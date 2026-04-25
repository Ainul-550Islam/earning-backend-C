# api/payment_gateways/referral/models.py
# Referral/Affiliate program — like CPAlead's referral program

import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel


class ReferralProgram(TimeStampedModel):
    """Global referral program configuration."""
    is_active            = models.BooleanField(default=True)
    commission_percent   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10'),
                           help_text='% of referred user earnings paid to referrer')
    commission_months    = models.IntegerField(default=6, help_text='Months commission is paid (CPAlead = 6)')
    minimum_payout       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10'))
    cookie_duration_days = models.IntegerField(default=30)
    description          = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Referral Program'

    def __str__(self):
        return f'Referral Program ({self.commission_percent}% for {self.commission_months} months)'


class ReferralLink(TimeStampedModel):
    """Each user gets a unique referral link/code."""
    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='referral_link')
    code       = models.CharField(max_length=20, unique=True, default='')
    total_clicks    = models.IntegerField(default=0)
    total_signups   = models.IntegerField(default=0)
    total_earned    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_active       = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Referral Link'

    def __str__(self):
        return f'{self.user.username} — code: {self.code}'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self) -> str:
        return uuid.uuid4().hex[:10].upper()

    @property
    def full_url(self) -> str:
        base = getattr(settings, 'SITE_URL', 'https://yourdomain.com')
        return f'{base}/register/?ref={self.code}'


class Referral(TimeStampedModel):
    """Records when a user signs up via referral."""
    referrer      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='referrals_made')
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                          related_name='referred_by')
    referral_link = models.ForeignKey(ReferralLink, on_delete=models.SET_NULL, null=True)
    is_active     = models.BooleanField(default=True, help_text='Commission still being paid')
    commission_start = models.DateField(auto_now_add=True)
    commission_end   = models.DateField(null=True, blank=True,
                                         help_text='When commission period ends')
    total_commission_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    class Meta:
        verbose_name = 'Referral'

    def __str__(self):
        return f'{self.referrer.username} referred {self.referred_user.username}'


class ReferralCommission(TimeStampedModel):
    """Individual commission payment to referrer."""
    STATUS = (('pending','Pending'),('paid','Paid'),('cancelled','Cancelled'))

    referral       = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name='commissions')
    referrer       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                        related_name='referral_commissions')
    referred_user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                        related_name='generated_commissions')
    original_amount = models.DecimalField(max_digits=10, decimal_places=2,
                      help_text='Referred user transaction amount')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2,
                        help_text='Commission paid to referrer')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    status         = models.CharField(max_length=15, choices=STATUS, default='pending')
    paid_at        = models.DateTimeField(null=True, blank=True)
    transaction_ref = models.CharField(max_length=100, blank=True,
                      help_text='Original transaction that triggered this commission')

    class Meta:
        verbose_name = 'Referral Commission'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['referrer','status'])]

    def __str__(self):
        return f'{self.referrer.username} +{self.commission_amount} from {self.referred_user.username}'
