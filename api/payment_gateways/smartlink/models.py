# api/payment_gateways/smartlink/models.py
# SmartLink — auto-routes traffic to best performing offer per GEO/device
# Like ClickDealer's SmartLink technology

import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel


def gen_smart_key():
    return uuid.uuid4().hex[:12].upper()


class SmartLink(TimeStampedModel):
    """
    A SmartLink automatically routes incoming traffic to the
    highest-converting / highest-paying offer for that visitor's profile.

    Publisher gets ONE link. System handles offer selection automatically.
    Perfect for social media, email, and bulk traffic sources.

    Algorithm:
        1. Detect country, device, OS from request
        2. Filter eligible active offers
        3. Score by: EPC × conversion_rate × bid_multiplier
        4. Route to winner (with A/B testing support)
    """

    STATUS = (('active','Active'),('paused','Paused'),('deleted','Deleted'))

    ROTATION_MODES = (
        ('epc_optimized',   'EPC Optimized — highest earnings per click'),
        ('round_robin',     'Round Robin — equal distribution'),
        ('weighted',        'Weighted — custom % per offer'),
        ('ab_test',         'A/B Test — split traffic for testing'),
        ('ctr_optimized',   'CTR Optimized — highest click-through rate'),
    )

    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='smart_links')
    name            = models.CharField(max_length=200)
    slug            = models.CharField(max_length=20, unique=True, default=gen_smart_key)
    status          = models.CharField(max_length=10, choices=STATUS, default='active')
    rotation_mode   = models.CharField(max_length=20, choices=ROTATION_MODES, default='epc_optimized')

    # Offer pool filters
    offer_types     = models.JSONField(default=list, blank=True,
                       help_text='["cpa","cpi"] — filter offer types. Empty = all')
    categories      = models.JSONField(default=list, blank=True,
                       help_text='["gaming","finance"] — filter categories')
    min_payout      = models.DecimalField(max_digits=10, decimal_places=4,
                       null=True, blank=True, help_text='Minimum offer payout')
    manual_offers   = models.ManyToManyField('offers.Offer', blank=True,
                       related_name='smart_links',
                       help_text='Specific offers to include (empty = auto-select all eligible)')

    # Targeting
    target_countries= models.JSONField(default=list, blank=True)
    target_devices  = models.JSONField(default=list, blank=True)

    # Fallback
    fallback_url    = models.URLField(max_length=2000, blank=True,
                       help_text='Redirect here if no matching offer found')

    # Stats
    total_clicks    = models.BigIntegerField(default=0)
    total_conversions= models.BigIntegerField(default=0)
    total_earnings  = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    epc             = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))

    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Smart Link'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['slug'])]

    def __str__(self):
        return f'SmartLink: {self.name} [{self.rotation_mode}]'

    @property
    def url(self) -> str:
        return f'https://yourdomain.com/go/{self.slug}/'


class SmartLinkRotation(TimeStampedModel):
    """A/B test or weighted rotation config per offer in a smart link."""
    smart_link  = models.ForeignKey(SmartLink, on_delete=models.CASCADE, related_name='rotations')
    offer       = models.ForeignKey('offers.Offer', on_delete=models.CASCADE)
    weight      = models.IntegerField(default=50, help_text='Weight % for weighted/ab_test mode')
    is_control  = models.BooleanField(default=False, help_text='Control group for A/B test')
    clicks      = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    earnings    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        unique_together = ['smart_link', 'offer']
        verbose_name    = 'Smart Link Rotation'
