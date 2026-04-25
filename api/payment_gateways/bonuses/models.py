# api/payment_gateways/bonuses/models.py
# Performance bonus & tier system — like MaxBounty's performance rewards

from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel


class PerformanceTier(TimeStampedModel):
    """Publisher performance tier configuration."""
    name            = models.CharField(max_length=50)  # Bronze, Silver, Gold, Elite
    min_monthly_earnings = models.DecimalField(max_digits=12, decimal_places=2)
    bonus_percent   = models.DecimalField(max_digits=5, decimal_places=2,
                       help_text='Extra % added to all payouts at this tier')
    min_payout_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))
    priority_support= models.BooleanField(default=False)
    exclusive_offers= models.BooleanField(default=False)
    custom_payout_negotiation = models.BooleanField(default=False)
    badge_color     = models.CharField(max_length=7, default='#C0C0C0')
    sort_order      = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Performance Tier'
        ordering     = ['sort_order']

    def __str__(self):
        return f'{self.name} (${self.min_monthly_earnings}+/mo, +{self.bonus_percent}%)'


class PublisherBonus(TimeStampedModel):
    """Bonus payment to a publisher for performance milestones."""
    TYPES = (
        ('monthly_performance', 'Monthly performance bonus'),
        ('tier_upgrade',        'Tier upgrade reward'),
        ('referral_milestone',  'Referral milestone'),
        ('first_conversion',    'First conversion bonus'),
        ('volume_milestone',    'Volume milestone'),
        ('manual',              'Manual admin bonus'),
    )
    STATUS = (('pending','Pending'),('paid','Paid'),('cancelled','Cancelled'))

    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='bonuses')
    bonus_type      = models.CharField(max_length=25, choices=TYPES)
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    currency        = models.CharField(max_length=5, default='USD')
    status          = models.CharField(max_length=10, choices=STATUS, default='pending')
    description     = models.TextField(blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)
    approved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='approved_bonuses')
    period          = models.CharField(max_length=20, blank=True,
                       help_text='e.g. 2025-01 for monthly bonus')

    class Meta:
        verbose_name = 'Publisher Bonus'
        ordering     = ['-created_at']

    def __str__(self):
        return f'{self.publisher.username} bonus {self.amount} [{self.status}]'
