# api/payment_gateways/tracking/models.py
# World-class S2S / Postback tracking system
# Supports: Click tracking, Impression tracking, Conversion tracking, Postback firing

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from core.models import TimeStampedModel


def generate_click_id():
    return uuid.uuid4().hex  # 32-char unique click ID


# ── Click ─────────────────────────────────────────────────────────────────────
class Click(TimeStampedModel):
    """
    Every click on an offer link is recorded here.
    The click_id flows through the entire funnel:
        Publisher link → Advertiser site → Postback → Conversion
    """
    click_id        = models.CharField(max_length=64, unique=True, default=generate_click_id,
                       db_index=True)
    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='clicks', null=True, blank=True)
    campaign        = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='clicks', null=True, blank=True)
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='tracking_clicks')
    advertiser      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='tracking_advertiser_clicks')

    # Traffic data
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    referer         = models.URLField(max_length=1000, blank=True)
    country_code    = models.CharField(max_length=2, blank=True)   # ISO 3166-1 alpha-2
    region          = models.CharField(max_length=100, blank=True)
    city            = models.CharField(max_length=100, blank=True)

    # Device data
    device_type     = models.CharField(max_length=20, blank=True,
                       choices=(('desktop','Desktop'),('mobile','Mobile'),('tablet','Tablet'),('other','Other')))
    os_name         = models.CharField(max_length=50, blank=True)   # iOS, Android, Windows
    os_version      = models.CharField(max_length=20, blank=True)
    browser         = models.CharField(max_length=50, blank=True)
    is_bot          = models.BooleanField(default=False)

    # Publisher tracking params
    sub1            = models.CharField(max_length=255, blank=True, db_index=True)  # Publisher sub-id 1
    sub2            = models.CharField(max_length=255, blank=True)
    sub3            = models.CharField(max_length=255, blank=True)
    sub4            = models.CharField(max_length=255, blank=True)
    sub5            = models.CharField(max_length=255, blank=True)
    traffic_id      = models.CharField(max_length=255, blank=True, db_index=True)

    # Conversion status
    is_converted    = models.BooleanField(default=False, db_index=True)
    converted_at    = models.DateTimeField(null=True, blank=True)

    # Payout (set on conversion)
    payout          = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))
    cost            = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'),
                       help_text='Advertiser cost')
    currency        = models.CharField(max_length=5, default='USD')

    # Flags
    is_duplicate    = models.BooleanField(default=False)
    is_fraud        = models.BooleanField(default=False)
    fraud_reason    = models.TextField(blank=True)

    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Click'
        verbose_name_plural = 'Clicks'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['click_id']),
            models.Index(fields=['publisher', 'created_at']),
            models.Index(fields=['offer', 'is_converted']),
            models.Index(fields=['country_code', 'device_type']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f'Click {self.click_id[:8]}... offer={self.offer_id}'

    @property
    def is_valid(self):
        return not self.is_bot and not self.is_fraud and not self.is_duplicate


# ── Impression ────────────────────────────────────────────────────────────────
class Impression(TimeStampedModel):
    """
    Ad impression — recorded when an offer is displayed to a visitor.
    Used to calculate CTR (click-through rate).
    """
    impression_id   = models.CharField(max_length=64, unique=True, default=generate_click_id)
    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='impressions')
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='impressions')
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    country_code    = models.CharField(max_length=2, blank=True)
    device_type     = models.CharField(max_length=20, blank=True)
    is_bot          = models.BooleanField(default=False)

    class Meta:
        verbose_name  = 'Impression'
        ordering      = ['-created_at']
        indexes       = [models.Index(fields=['offer', 'created_at'])]

    def __str__(self):
        return f'Impression {self.impression_id[:8]}...'


# ── Conversion ────────────────────────────────────────────────────────────────
class Conversion(TimeStampedModel):
    """
    A completed conversion — triggered by advertiser postback or server-side event.
    Links back to original click via click_id.
    """

    CONVERSION_TYPES = (
        ('install',  'App Install (CPI)'),
        ('lead',     'Lead submission (CPL)'),
        ('sale',     'Sale (CPS)'),
        ('click',    'Click (CPC)'),
        ('action',   'Action (CPA)'),
        ('signup',   'Sign up'),
        ('deposit',  'First deposit'),
        ('purchase', 'Purchase'),
    )

    STATUS_CHOICES = (
        ('pending',   'Pending verification'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('duplicate', 'Duplicate'),
        ('fraud',     'Fraud'),
        ('reversed',  'Reversed / Chargeback'),
    )

    conversion_id   = models.CharField(max_length=64, unique=True, default=generate_click_id,
                       db_index=True)
    click           = models.OneToOneField(Click, on_delete=models.SET_NULL, null=True, blank=True,
                       related_name='conversion')
    click_id_raw    = models.CharField(max_length=64, blank=True, db_index=True,
                       help_text='Raw click_id from postback (even if Click deleted)')

    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='conversions')
    campaign        = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='conversions', null=True, blank=True)
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='conversions')
    advertiser      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='advertiser_conversions')

    # Conversion details
    conversion_type = models.CharField(max_length=20, choices=CONVERSION_TYPES, default='action')
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # Financial
    payout          = models.DecimalField(max_digits=10, decimal_places=4,
                       help_text='Amount paid to publisher')
    cost            = models.DecimalField(max_digits=10, decimal_places=4,
                       help_text='Amount charged to advertiser')
    currency        = models.CharField(max_length=5, default='USD')
    revenue         = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'),
                       help_text='Platform revenue = cost - payout')

    # Advertiser-provided data
    advertiser_order_id = models.CharField(max_length=255, blank=True)
    sale_amount         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                          help_text='Actual sale amount from advertiser (for CPS)')

    # GEO / device (from original click)
    country_code    = models.CharField(max_length=2, blank=True)
    device_type     = models.CharField(max_length=20, blank=True)

    # Verification
    postback_received  = models.BooleanField(default=False)
    postback_ip        = models.GenericIPAddressField(null=True, blank=True)
    postback_received_at = models.DateTimeField(null=True, blank=True)
    approved_at        = models.DateTimeField(null=True, blank=True)
    approved_by        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                          null=True, blank=True, related_name='approved_conversions')
    rejection_reason   = models.TextField(blank=True)

    # Payout tracking
    publisher_paid     = models.BooleanField(default=False)
    publisher_paid_at  = models.DateTimeField(null=True, blank=True)

    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Conversion'
        verbose_name_plural = 'Conversions'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['click_id_raw']),
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['offer', 'status']),
            models.Index(fields=['status', 'publisher_paid']),
            models.Index(fields=['conversion_type']),
        ]

    def __str__(self):
        return f'Conversion {self.conversion_id[:8]}... {self.status} ${self.payout}'

    def save(self, *args, **kwargs):
        self.revenue = self.cost - self.payout
        super().save(*args, **kwargs)


# ── Postback Log ──────────────────────────────────────────────────────────────
class PostbackLog(TimeStampedModel):
    """
    Every postback (S2S callback) from advertiser is logged here for debugging.
    """
    STATUS = (('success','Success'),('failed','Failed'),('duplicate','Duplicate'),('invalid','Invalid'))

    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.SET_NULL,
                       null=True, related_name='postback_logs')
    click_id        = models.CharField(max_length=64, db_index=True)
    raw_url         = models.TextField(help_text='Full postback URL received')
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    status          = models.CharField(max_length=15, choices=STATUS, default='success')
    error_message   = models.TextField(blank=True)
    conversion      = models.ForeignKey(Conversion, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='postback_log')
    params          = models.JSONField(default=dict, blank=True,
                       help_text='Parsed URL parameters from postback')
    response_code   = models.IntegerField(default=200)

    class Meta:
        verbose_name  = 'Postback Log'
        ordering      = ['-created_at']
        indexes       = [models.Index(fields=['click_id']), models.Index(fields=['status'])]

    def __str__(self):
        return f'Postback {self.click_id[:8]}... [{self.status}]'


# ── Publisher Stats (daily aggregates) ───────────────────────────────────────
class PublisherDailyStats(models.Model):
    """
    Pre-aggregated daily stats per publisher per offer.
    Updated by Celery every hour. Used for fast dashboard queries.
    """
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='daily_stats')
    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='daily_stats', null=True, blank=True)
    date            = models.DateField(db_index=True)

    impressions     = models.IntegerField(default=0)
    clicks          = models.IntegerField(default=0)
    conversions     = models.IntegerField(default=0)
    revenue         = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    # Calculated
    ctr             = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'),
                       help_text='Click-through rate = clicks / impressions')
    cr              = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'),
                       help_text='Conversion rate = conversions / clicks')
    epc             = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'),
                       help_text='Earnings per click')

    class Meta:
        unique_together = ['publisher', 'offer', 'date']
        ordering        = ['-date']
        indexes         = [models.Index(fields=['publisher', 'date'])]

    def __str__(self):
        return f'{self.publisher_id} stats {self.date}'

    def recalculate(self):
        self.ctr = (self.clicks / self.impressions) if self.impressions else Decimal('0')
        self.cr  = (self.conversions / self.clicks)  if self.clicks     else Decimal('0')
        self.epc = (self.revenue / self.clicks)       if self.clicks     else Decimal('0')
        self.save()
