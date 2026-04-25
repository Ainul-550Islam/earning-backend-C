# api/payment_gateways/blacklist/models.py
# Traffic source blacklisting — like CPAlead's traffic blacklist feature

from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class TrafficBlacklist(TimeStampedModel):
    """
    Advertiser can block traffic sources that are underperforming or fraudulent.
    Publisher can also block competing offers.
    """
    BLOCK_TYPES = (
        ('ip',        'IP Address'),
        ('ip_range',  'IP Range (CIDR)'),
        ('country',   'Country Code'),
        ('device',    'Device Type'),
        ('os',        'Operating System'),
        ('carrier',   'Mobile Carrier'),
        ('sub_id',    'Publisher Sub-ID'),
        ('publisher', 'Publisher Account'),
        ('source',    'Traffic Source Domain'),
    )

    CREATED_BY_TYPES = (
        ('advertiser', 'Advertiser'),
        ('admin',      'Admin'),
        ('auto',       'Auto-detected (fraud)'),
    )

    owner           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='blacklist_entries',
                       help_text='Advertiser who owns this blacklist entry')
    block_type      = models.CharField(max_length=15, choices=BLOCK_TYPES)
    value           = models.CharField(max_length=500, db_index=True,
                       help_text='The blocked value (IP, country code, sub_id, etc.)')
    reason          = models.TextField(blank=True)
    created_by_type = models.CharField(max_length=15, choices=CREATED_BY_TYPES, default='advertiser')
    is_active       = models.BooleanField(default=True)
    expires_at      = models.DateTimeField(null=True, blank=True,
                       help_text='Auto-expire this block (null = permanent)')
    block_count     = models.IntegerField(default=0, help_text='Times this rule has blocked traffic')

    # Scope (null = applies to all their offers)
    offer           = models.ForeignKey('offers.Offer', on_delete=models.CASCADE,
                       null=True, blank=True, related_name='blacklist_entries',
                       help_text='Specific offer to apply to (null = all offers)')

    class Meta:
        verbose_name        = 'Traffic Blacklist'
        verbose_name_plural = 'Traffic Blacklists'
        unique_together     = ['owner', 'block_type', 'value', 'offer']
        ordering            = ['-created_at']

    def __str__(self):
        return f'Block {self.block_type}:{self.value} by {self.owner.username}'


class OfferQualityScore(TimeStampedModel):
    """
    Quality scoring per publisher per offer.
    Used to auto-blacklist low quality traffic sources.
    """
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='quality_scores')
    offer           = models.ForeignKey('offers.Offer', on_delete=models.CASCADE,
                       related_name='quality_scores')

    # Volume
    total_clicks    = models.IntegerField(default=0)
    total_conversions= models.IntegerField(default=0)
    total_reversals = models.IntegerField(default=0)

    # Rates
    conversion_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    reversal_rate   = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    fraud_rate      = models.DecimalField(max_digits=7, decimal_places=4, default=0)

    # Score 0-100 (100 = perfect quality)
    quality_score   = models.IntegerField(default=100)
    is_blacklisted  = models.BooleanField(default=False)
    blacklisted_at  = models.DateTimeField(null=True, blank=True)
    blacklisted_reason = models.TextField(blank=True)

    last_updated    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name    = 'Offer Quality Score'
        unique_together = ['publisher', 'offer']
        ordering        = ['quality_score']

    def __str__(self):
        return f'{self.publisher.username} → {self.offer.name}: {self.quality_score}/100'
