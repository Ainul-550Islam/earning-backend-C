# offerwall/models.py
"""
Offerwall app models.

FIX (audit): The original model had only one field (title='').
This expands it into a production-ready Offer model aligned with the
CPAlead offerwall system, plus OfferClick and OfferConversion models.

The existing Offer model field (title) is kept — all new fields are additive.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Offer(models.Model):
    """
    A CPAlead-sourced or internally-managed offerwall offer.
    Can be fetched from CPAlead API or created manually by admin.
    """
    SOURCE_CPALEAD  = 'cpalead'
    SOURCE_INTERNAL = 'internal'
    SOURCE_PARTNER  = 'partner'
    SOURCE_CHOICES = [
        (SOURCE_CPALEAD,  'CPAlead'),
        (SOURCE_INTERNAL, 'Internal'),
        (SOURCE_PARTNER,  'Partner Network'),
    ]

    STATUS_ACTIVE   = 'active'
    STATUS_PAUSED   = 'paused'
    STATUS_EXPIRED  = 'expired'
    STATUS_DRAFT    = 'draft'
    STATUS_CHOICES = [
        (STATUS_ACTIVE,  'Active'),
        (STATUS_PAUSED,  'Paused'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_DRAFT,   'Draft'),
    ]

    DEVICE_ALL     = 'all'
    DEVICE_MOBILE  = 'mobile'
    DEVICE_DESKTOP = 'desktop'
    DEVICE_CHOICES = [
        (DEVICE_ALL,     'All Devices'),
        (DEVICE_MOBILE,  'Mobile Only'),
        (DEVICE_DESKTOP, 'Desktop Only'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Original field preserved
    title       = models.CharField(max_length=255, default='')
    description = models.TextField(blank=True, default='')
    source      = models.CharField(max_length=20, choices=SOURCE_CHOICES,
                                   default=SOURCE_CPALEAD)
    external_id = models.CharField(max_length=100, blank=True, db_index=True,
                                   help_text='CPAlead offer ID or partner reference')

    # ── Payout ────────────────────────────────────────────────────────────────
    payout_usd      = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    virtual_payout  = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                          help_text='Coins/virtual currency awarded')
    revenue_share   = models.DecimalField(max_digits=5, decimal_places=4, default=0,
                                          help_text='0.0 – 1.0 (our share)')

    # ── Status ────────────────────────────────────────────────────────────────
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                   default=STATUS_DRAFT, db_index=True)
    is_featured = models.BooleanField(default=False)

    # ── Targeting ─────────────────────────────────────────────────────────────
    target_device   = models.CharField(max_length=20, choices=DEVICE_CHOICES,
                                       default=DEVICE_ALL)
    target_countries = models.JSONField(default=list, blank=True,
                                        help_text='ISO-2 country codes; empty = all')
    min_user_level  = models.PositiveSmallIntegerField(default=0)

    # ── Media ─────────────────────────────────────────────────────────────────
    image_url   = models.URLField(blank=True, default='')
    click_url   = models.URLField(blank=True, default='')

    # ── Analytics (denormalised for speed) ───────────────────────────────────
    total_clicks      = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    total_paid_usd    = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    expires_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['-is_featured', '-payout_usd']
        indexes = [
            models.Index(fields=['status', 'source']),
            models.Index(fields=['target_device', 'status']),
        ]

    def __str__(self):
        return f"{self.title} (${self.payout_usd})"

    @property
    def conversion_rate(self) -> float:
        if self.total_clicks == 0:
            return 0.0
        return round(self.total_conversions / self.total_clicks * 100, 2)

    @property
    def is_active(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class OfferClick(models.Model):
    """Tracks each click on an offerwall offer."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer       = models.ForeignKey(Offer, on_delete=models.CASCADE,
                                    related_name='clicks')
    user        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='offer_clicks')
    ip_address  = models.GenericIPAddressField(blank=True, null=True)
    user_agent  = models.TextField(blank=True, default='')
    country     = models.CharField(max_length=2, blank=True, default='')
    device_type = models.CharField(max_length=20, blank=True, default='')
    subid       = models.CharField(max_length=255, blank=True, default='',
                                   db_index=True)
    clicked_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['offer', 'clicked_at']),
            models.Index(fields=['user', 'clicked_at']),
        ]

    def __str__(self):
        return f"Click on {self.offer.title} by user={self.user_id}"


class OfferConversion(models.Model):
    """
    Tracks a completed offer conversion — linked to OfferClick for attribution.
    Mirrors ConversionLog in cms/ but scoped to the offerwall app.
    """
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer       = models.ForeignKey(Offer, on_delete=models.CASCADE,
                                    related_name='conversions')
    click       = models.ForeignKey(OfferClick, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='conversions')
    user        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='offer_conversions')

    lead_id     = models.CharField(max_length=255, unique=True, db_index=True)
    payout_usd  = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    virtual_awarded = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                   default=STATUS_PENDING, db_index=True)
    fraud_score = models.PositiveSmallIntegerField(default=0)
    fraud_reasons = models.JSONField(default=list)

    ip_address   = models.GenericIPAddressField(blank=True, null=True)
    postback_raw = models.JSONField(default=dict, blank=True)

    approved_at  = models.DateTimeField(null=True, blank=True)
    rejected_at  = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['-converted_at']
        indexes = [
            models.Index(fields=['status', 'converted_at']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"Conversion lead={self.lead_id} status={self.status}"
