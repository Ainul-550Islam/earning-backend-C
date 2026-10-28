# api/cms/models_new/rtb.py
"""
RTB (Real-Time Bidding) Publisher Config — CPAlead 100%.
CPAlead's RTB marketplace: publisher-side config only.
CMS manages: publisher's RTB preferences, floor prices, ad slots, bid history.
Rule: এক কাজের জন্য একটাই মালিক — CMS owns publisher RTB config.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class RTBConfig(models.Model):
    """
    Publisher's RTB configuration.
    CPAlead RTB: advertisers bid in real-time for publisher's traffic.
    Publisher sets floor prices and ad slot preferences.
    """
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name          = models.CharField(max_length=200, default='Main RTB Config')
    publisher_id  = models.CharField(max_length=100, blank=True,
                                     help_text="CPAlead Publisher ID")
    is_active     = models.BooleanField(default=True, db_index=True)

    # Floor prices (minimum bid accepted)
    floor_price_cpc_usd   = models.DecimalField(max_digits=6, decimal_places=4, default=0,
                                                  help_text="Min $CPC bid accepted")
    floor_price_cpa_usd   = models.DecimalField(max_digits=6, decimal_places=4, default=0,
                                                  help_text="Min $CPA bid accepted")
    floor_price_cpi_usd   = models.DecimalField(max_digits=6, decimal_places=4, default=0,
                                                  help_text="Min $CPI bid accepted")

    # Targeting preferences
    preferred_countries   = models.JSONField(default=list, blank=True,
                                              help_text="ISO codes of preferred countries")
    preferred_categories  = models.JSONField(default=list, blank=True,
                                              help_text="games, finance, dating, crypto, etc.")
    blocked_categories    = models.JSONField(default=list, blank=True)
    preferred_devices     = models.JSONField(default=list, blank=True,
                                              help_text="desktop, mobile, tablet")

    # Auction settings
    auction_timeout_ms    = models.PositiveIntegerField(default=200,
                                                         help_text="Max ms to wait for bids")
    max_ads_per_page      = models.PositiveIntegerField(default=3)
    enable_header_bidding = models.BooleanField(default=False)

    # Stats
    total_impressions     = models.PositiveIntegerField(default=0)
    total_clicks          = models.PositiveIntegerField(default=0)
    total_revenue_usd     = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    avg_ecpm              = models.DecimalField(max_digits=8, decimal_places=4, default=0,
                                                help_text="Effective CPM")

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "RTB Config"

    def __str__(self):
        return f"{self.name} (floor: ${self.floor_price_cpc_usd} CPC)"

    @classmethod
    def get_active(cls):
        from django.core.cache import cache
        cached = cache.get('rtb_config_active')
        if cached is None:
            try:
                cached = cls.objects.filter(is_active=True).first()
            except Exception:
                cached = None
            cache.set('rtb_config_active', cached, 300)
        return cached


class RTBAdSlot(models.Model):
    """An ad placement slot on the publisher's site for RTB."""
    SLOT_TYPES = [
        ('banner_728x90',  'Leaderboard Banner 728x90'),
        ('banner_300x250', 'Medium Rectangle 300x250'),
        ('banner_160x600', 'Wide Skyscraper 160x600'),
        ('interstitial',   'Interstitial / Full Screen'),
        ('native',         'Native Ad'),
        ('video_pre',      'Video Pre-roll'),
        ('pop_under',      'Pop Under'),
        ('in_content',     'In-Content Ad'),
    ]
    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    rtb_config   = models.ForeignKey(RTBConfig, on_delete=models.CASCADE,
                                      related_name='ad_slots')
    name         = models.CharField(max_length=100)
    slot_type    = models.CharField(max_length=30, choices=SLOT_TYPES, db_index=True)
    page_location = models.CharField(max_length=200, blank=True,
                                      help_text="e.g. homepage_top, blog_sidebar")
    floor_price_usd = models.DecimalField(max_digits=6, decimal_places=4, default=0,
                                           help_text="Override global floor for this slot")
    is_active    = models.BooleanField(default=True)
    # Stats
    impressions  = models.PositiveIntegerField(default=0)
    clicks       = models.PositiveIntegerField(default=0)
    revenue_usd  = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "RTB Ad Slot"
        ordering = ['-revenue_usd']

    def __str__(self):
        return f"{self.name} ({self.slot_type})"

    @property
    def ctr(self) -> float:
        if not self.impressions:
            return 0.0
        return round(self.clicks / self.impressions * 100, 3)

    @property
    def ecpm(self) -> float:
        if not self.impressions:
            return 0.0
        return round(float(self.revenue_usd) / self.impressions * 1000, 4)


class RTBBidLog(models.Model):
    """Log of RTB bid requests and winning bids for analytics."""
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ad_slot       = models.ForeignKey(RTBAdSlot, on_delete=models.CASCADE,
                                       related_name='bid_logs')
    bid_request_id = models.CharField(max_length=200, db_index=True)
    winning_bid_usd = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    num_bidders   = models.PositiveSmallIntegerField(default=0)
    floor_price   = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    ad_category   = models.CharField(max_length=100, blank=True)
    user_country  = models.CharField(max_length=5, blank=True)
    device_type   = models.CharField(max_length=20, blank=True)
    was_filled    = models.BooleanField(default=False)
    response_ms   = models.PositiveIntegerField(default=0,
                                                 help_text="Auction response time in ms")
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = "RTB Bid Log"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_slot', 'created_at']),
            models.Index(fields=['was_filled', 'created_at']),
            models.Index(fields=['user_country', 'created_at']),
        ]

    def __str__(self):
        filled = "✓" if self.was_filled else "✗"
        return f"{filled} Bid {self.bid_request_id[:12]} ${self.winning_bid_usd or 0}"
