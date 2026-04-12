from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink
from ..choices import CapPeriod, RotationMethod
from ..validators import validate_weight, validate_cap_value


class OfferPool(models.Model):
    """
    Pool of offers assigned to a SmartLink.
    The rotation engine picks offers from this pool.
    """
    smartlink = models.OneToOneField(
        SmartLink, on_delete=models.CASCADE,
        related_name='offer_pool',
    )
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    min_epc_threshold = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        help_text=_('Minimum EPC required for an offer to be included in rotation.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_offer_pool'
        verbose_name = _('Offer Pool')

    def __str__(self):
        return f"Pool: {self.smartlink.slug} ({self.entries.filter(is_active=True).count()} offers)"

    def get_active_entries(self):
        return self.entries.filter(is_active=True).select_related('offer').order_by('-priority', '-weight')


class OfferPoolEntry(models.Model):
    """
    Single offer entry in an offer pool.
    Contains weight, priority, and cap configuration.
    """
    pool = models.ForeignKey(
        OfferPool, on_delete=models.CASCADE,
        related_name='entries',
    )
    # FK to your Offer model — adjust app label as needed
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.CASCADE,
        related_name='pool_entries',
    )
    weight = models.PositiveSmallIntegerField(
        default=100,
        validators=[validate_weight],
        help_text=_('Rotation weight (1-1000). Higher = more traffic.')
    )
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Priority order. Higher = evaluated first in priority mode.')
    )
    cap_per_day = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[validate_cap_value],
        help_text=_('Max clicks per day for this offer in this pool.')
    )
    cap_per_month = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # EPC override — if set, overrides calculated EPC for routing
    epc_override = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_offer_pool_entry'
        verbose_name = _('Offer Pool Entry')
        unique_together = [('pool', 'offer')]
        ordering = ['-priority', '-weight']

    def __str__(self):
        return f"{self.pool.smartlink.slug} ← Offer#{self.offer_id} (w:{self.weight})"


class OfferCapTracker(models.Model):
    """
    Daily/monthly cap tracking per offer per pool.
    Reset daily at midnight UTC via Celery task.
    """
    pool_entry = models.ForeignKey(
        OfferPoolEntry, on_delete=models.CASCADE,
        related_name='cap_trackers',
    )
    period = models.CharField(max_length=10, choices=CapPeriod.choices, default=CapPeriod.DAILY)
    period_date = models.DateField(
        db_index=True,
        help_text=_('The date this tracker applies to (YYYY-MM-DD for daily).')
    )
    clicks_count = models.PositiveIntegerField(default=0)
    cap_limit = models.PositiveIntegerField(
        help_text=_('Snapshot of cap at time of creation.')
    )
    is_capped = models.BooleanField(default=False, db_index=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_offer_cap_tracker'
        verbose_name = _('Offer Cap Tracker')
        unique_together = [('pool_entry', 'period', 'period_date')]
        indexes = [
            models.Index(fields=['period_date', 'is_capped'], name='cap_date_capped_idx'),
        ]

    def __str__(self):
        return f"Cap: offer#{self.pool_entry.offer_id} {self.period} {self.period_date}: {self.clicks_count}/{self.cap_limit}"

    def increment(self) -> bool:
        """
        Increment click count. Returns True if cap reached after increment.
        Thread-safe via F() expression.
        """
        from django.db.models import F
        OfferCapTracker.objects.filter(pk=self.pk).update(
            clicks_count=F('clicks_count') + 1
        )
        self.refresh_from_db()
        if self.clicks_count >= self.cap_limit:
            OfferCapTracker.objects.filter(pk=self.pk).update(is_capped=True)
            self.is_capped = True
            return True
        return False


class OfferBlacklist(models.Model):
    """Exclude specific offers per publisher (publisher-level blacklist)."""
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='blacklisted_offers',
    )
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.CASCADE,
        related_name='blacklisted_from_smartlinks',
    )
    reason = models.TextField(blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='offer_blacklist_entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_offer_blacklist'
        verbose_name = _('Offer Blacklist')
        unique_together = [('smartlink', 'offer')]

    def __str__(self):
        return f"Blacklist: {self.smartlink.slug} ✗ Offer#{self.offer_id}"


class OfferRotationLog(models.Model):
    """
    Audit log: which offer was selected for each redirect, and why.
    Used for rotation transparency and debugging.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='rotation_logs',
    )
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.SET_NULL, null=True,
        related_name='rotation_logs',
    )
    selected_reason = models.CharField(max_length=30, help_text=_('e.g. weighted_random, epc_optimized'))
    offer_weight = models.PositiveSmallIntegerField(null=True, blank=True)
    offer_epc = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    device_type = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sl_offer_rotation_log'
        verbose_name = _('Offer Rotation Log')
        ordering = ['-created_at']

    def __str__(self):
        return f"Rotation: {self.smartlink.slug} → Offer#{self.offer_id} ({self.selected_reason})"


class OfferScoreCache(models.Model):
    """
    Cached EPC score per offer per geo+device.
    Updated every 30 minutes by Celery task.
    Used by EPC optimizer for fast routing decisions.
    """
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.CASCADE,
        related_name='score_caches',
    )
    country = models.CharField(max_length=2, db_index=True)
    device_type = models.CharField(max_length=10, choices=[
        ('mobile', 'Mobile'), ('tablet', 'Tablet'),
        ('desktop', 'Desktop'), ('unknown', 'Unknown'),
    ])
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    total_clicks = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    score = models.FloatField(default=0.0, db_index=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_offer_score_cache'
        verbose_name = _('Offer Score Cache')
        unique_together = [('offer', 'country', 'device_type')]
        indexes = [
            models.Index(fields=['country', 'device_type', 'score'], name='score_geo_device_idx'),
        ]

    def __str__(self):
        return f"Score: Offer#{self.offer_id} {self.country}/{self.device_type} EPC:{self.epc}"
