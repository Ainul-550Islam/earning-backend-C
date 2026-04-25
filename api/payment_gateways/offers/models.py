# api/payment_gateways/offers/models.py
# World-class CPA/CPI/CPC/CPL Offer & Campaign System

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.models import TimeStampedModel


# ── Offer ─────────────────────────────────────────────────────────────────────
class Offer(TimeStampedModel):
    """
    A monetization offer that publishers promote.
    Advertisers create offers; publishers drive traffic.

    Types:
        CPA — Cost Per Action (user completes action)
        CPI — Cost Per Install (user installs app)
        CPC — Cost Per Click (user clicks ad)
        CPL — Cost Per Lead (user submits form)
        CPS — Cost Per Sale (user makes purchase)
    """

    OFFER_TYPES = (
        ('cpa', 'CPA — Cost Per Action'),
        ('cpi', 'CPI — Cost Per Install'),
        ('cpc', 'CPC — Cost Per Click'),
        ('cpl', 'CPL — Cost Per Lead'),
        ('cps', 'CPS — Cost Per Sale'),
    )

    STATUS_CHOICES = (
        ('draft',    'Draft'),
        ('pending',  'Pending review'),
        ('active',   'Active'),
        ('paused',   'Paused'),
        ('expired',  'Expired'),
        ('rejected', 'Rejected'),
    )

    PAYOUT_MODELS = (
        ('fixed',      'Fixed payout per conversion'),
        ('revshare',   'Revenue share %'),
        ('tiered',     'Tiered (volume-based)'),
    )

    PREVIEW_TYPES = (
        ('url',     'URL / Website'),
        ('app_ios', 'iOS App'),
        ('app_and', 'Android App'),
        ('video',   'Video'),
        ('file',    'File / Download'),
    )

    # ── Basic info ────────────────────────────────────────────────────────────
    name            = models.CharField(max_length=200, db_index=True)
    slug            = models.SlugField(max_length=220, unique=True, blank=True)
    description     = models.TextField(blank=True)
    short_desc      = models.CharField(max_length=500, blank=True)
    offer_type      = models.CharField(max_length=5, choices=OFFER_TYPES, default='cpa')
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    preview_type    = models.CharField(max_length=10, choices=PREVIEW_TYPES, default='url')

    # ── Parties ───────────────────────────────────────────────────────────────
    advertiser      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='advertiser_offers')
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='created_offers')

    # ── URLs ──────────────────────────────────────────────────────────────────
    destination_url      = models.URLField(max_length=2000,
                            help_text='Where user is sent (with {click_id} macro support)')
    tracking_url         = models.URLField(max_length=2000, blank=True,
                            help_text='Intermediate tracking URL if using 3rd party tracker')
    preview_url          = models.URLField(max_length=2000, blank=True,
                            help_text='Preview URL for affiliate review')
    postback_url         = models.URLField(max_length=2000, blank=True,
                            help_text='Advertiser postback URL for S2S tracking')
    publisher_postback_url = models.URLField(max_length=2000, blank=True,
                            help_text='URL fired to publisher on conversion')

    # ── Financial ─────────────────────────────────────────────────────────────
    payout_model         = models.CharField(max_length=10, choices=PAYOUT_MODELS, default='fixed')
    publisher_payout     = models.DecimalField(max_digits=10, decimal_places=4,
                            validators=[MinValueValidator(Decimal('0.0001'))],
                            help_text='Amount paid to publisher per conversion')
    advertiser_cost      = models.DecimalField(max_digits=10, decimal_places=4,
                            help_text='Amount charged to advertiser per conversion')
    revenue_share_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'),
                            help_text='For revshare model: % of advertiser cost to publisher')
    currency             = models.CharField(max_length=5, default='USD')

    # For CPS (pay on sale): % of sale amount
    cps_payout_pct       = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ── Targeting ─────────────────────────────────────────────────────────────
    target_countries     = models.JSONField(default=list, blank=True,
                            help_text='["US","GB","CA"] — empty = worldwide')
    blocked_countries    = models.JSONField(default=list, blank=True)
    target_devices       = models.JSONField(default=list, blank=True,
                            help_text='["mobile","desktop","tablet"] — empty = all')
    target_os            = models.JSONField(default=list, blank=True,
                            help_text='["iOS","Android","Windows"] — empty = all')
    target_carriers      = models.JSONField(default=list, blank=True)

    # ── App info (for CPI) ────────────────────────────────────────────────────
    app_name             = models.CharField(max_length=200, blank=True)
    app_store_url        = models.URLField(max_length=2000, blank=True)
    app_id               = models.CharField(max_length=200, blank=True)
    app_platform         = models.CharField(max_length=10, blank=True,
                            choices=(('ios','iOS'),('android','Android'),('both','Both')))
    app_icon_url         = models.URLField(max_length=500, blank=True)

    # ── Limits & schedule ─────────────────────────────────────────────────────
    daily_cap            = models.IntegerField(null=True, blank=True,
                            help_text='Max conversions per day (null = unlimited)')
    monthly_cap          = models.IntegerField(null=True, blank=True)
    total_cap            = models.IntegerField(null=True, blank=True)
    daily_budget         = models.DecimalField(max_digits=12, decimal_places=2,
                            null=True, blank=True)
    total_budget         = models.DecimalField(max_digits=12, decimal_places=2,
                            null=True, blank=True)
    start_date           = models.DateTimeField(null=True, blank=True)
    end_date             = models.DateTimeField(null=True, blank=True)

    # ── Access control ────────────────────────────────────────────────────────
    is_public            = models.BooleanField(default=True,
                            help_text='Visible to all publishers')
    requires_approval    = models.BooleanField(default=False,
                            help_text='Publishers must apply to run this offer')
    allowed_publishers   = models.ManyToManyField(settings.AUTH_USER_MODEL,
                            related_name='allowed_offers', blank=True)
    blocked_publishers   = models.ManyToManyField(settings.AUTH_USER_MODEL,
                            related_name='blocked_from_offers', blank=True)

    # ── Creative assets ───────────────────────────────────────────────────────
    thumbnail            = models.ImageField(upload_to='offers/thumbnails/', null=True, blank=True)
    banner_url           = models.URLField(max_length=500, blank=True)
    category             = models.CharField(max_length=100, blank=True,
                            choices=(
                                ('gaming','Gaming'),('finance','Finance'),
                                ('dating','Dating'),('health','Health'),
                                ('shopping','Shopping'),('mobile','Mobile Apps'),
                                ('sweepstakes','Sweepstakes'),('crypto','Crypto'),
                                ('other','Other'),
                            ))

    # ── Metrics (updated by background task) ─────────────────────────────────
    total_clicks         = models.BigIntegerField(default=0)
    total_conversions    = models.BigIntegerField(default=0)
    total_revenue        = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0'))
    conversion_rate      = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    epc                  = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'),
                            help_text='Earnings per click')

    metadata             = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Offer'
        verbose_name_plural = 'Offers'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'offer_type']),
            models.Index(fields=['advertiser', 'status']),
            models.Index(fields=['category', 'status']),
        ]

    def __str__(self):
        return f'[{self.offer_type.upper()}] {self.name} — ${self.publisher_payout}'

    def save(self, *args, **kwargs):
        if not self.slug:
            import re
            base = re.sub(r'[^\w\s-]', '', self.name.lower())
            self.slug = re.sub(r'[-\s]+', '-', base)[:200] + f'-{uuid.uuid4().hex[:6]}'
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        if self.status != 'active':
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    @property
    def payout_display(self):
        if self.offer_type == 'cpc':
            return f'${self.publisher_payout:.4f} per click'
        return f'${self.publisher_payout:.2f} per conversion'

    def can_publisher_run(self, publisher) -> tuple:
        """Returns (allowed: bool, reason: str)"""
        if not self.is_active:
            return False, 'Offer is not active'
        if publisher in self.blocked_publishers.all():
            return False, 'You are blocked from this offer'
        if not self.is_public and publisher not in self.allowed_publishers.all():
            return False, 'This offer requires approval'
        return True, ''


# ── Campaign ──────────────────────────────────────────────────────────────────
class Campaign(TimeStampedModel):
    """
    An advertiser's campaign grouping one or more offers.
    Campaigns track budget, targeting, and performance.
    """

    STATUS_CHOICES = (
        ('draft',   'Draft'),
        ('active',  'Active'),
        ('paused',  'Paused'),
        ('ended',   'Ended'),
        ('deleted', 'Deleted'),
    )

    name            = models.CharField(max_length=200)
    advertiser      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='campaigns')
    offers          = models.ManyToManyField(Offer, related_name='campaigns', blank=True)
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    description     = models.TextField(blank=True)

    # Budget
    total_budget    = models.DecimalField(max_digits=12, decimal_places=2,
                       null=True, blank=True, help_text='Total campaign budget')
    daily_budget    = models.DecimalField(max_digits=12, decimal_places=2,
                       null=True, blank=True)
    spent           = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    currency        = models.CharField(max_length=5, default='USD')

    # Schedule
    start_date      = models.DateTimeField(null=True, blank=True)
    end_date        = models.DateTimeField(null=True, blank=True)

    # Stats
    total_clicks    = models.BigIntegerField(default=0)
    total_conversions = models.BigIntegerField(default=0)
    total_revenue   = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0'))

    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Campaign'
        ordering     = ['-created_at']

    def __str__(self):
        return f'Campaign: {self.name} [{self.status}]'

    @property
    def budget_remaining(self):
        if self.total_budget:
            return self.total_budget - self.spent
        return None

    @property
    def is_over_budget(self):
        if self.total_budget:
            return self.spent >= self.total_budget
        return False


# ── Publisher Application ─────────────────────────────────────────────────────
class PublisherOfferApplication(TimeStampedModel):
    """Publisher applies to run a private offer."""

    STATUS = (
        ('pending',  'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    offer           = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='applications')
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='offer_applications')
    status          = models.CharField(max_length=10, choices=STATUS, default='pending')
    message         = models.TextField(blank=True, help_text='Publisher message to advertiser')
    admin_notes     = models.TextField(blank=True)
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='reviewed_applications')

    class Meta:
        unique_together = ['offer', 'publisher']
        verbose_name    = 'Publisher Application'
        ordering        = ['-created_at']

    def __str__(self):
        return f'{self.publisher.username} → {self.offer.name} [{self.status}]'


# ── Offer Creative ─────────────────────────────────────────────────────────────
class OfferCreative(TimeStampedModel):
    """Banner / creative assets for an offer."""

    SIZES = (
        ('728x90',  'Leaderboard (728×90)'),
        ('300x250', 'Medium Rectangle (300×250)'),
        ('160x600', 'Wide Skyscraper (160×600)'),
        ('320x50',  'Mobile Banner (320×50)'),
        ('300x600', 'Half Page (300×600)'),
        ('text',    'Text Ad'),
    )

    offer       = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='creatives')
    size        = models.CharField(max_length=20, choices=SIZES)
    image_url   = models.URLField(max_length=1000, blank=True)
    html_code   = models.TextField(blank=True)
    click_url   = models.URLField(max_length=2000, blank=True)
    alt_text    = models.CharField(max_length=200, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Offer Creative'

    def __str__(self):
        return f'{self.offer.name} — {self.size}'
