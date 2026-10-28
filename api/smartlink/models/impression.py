"""
SmartLink Impression Tracking
Records pre-click ad impressions (view events before the user clicks).
Used to calculate VTR (view-through rate) and impression-to-click ratio.

Model: ImpressionLog
Service: ImpressionTrackingService
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink


class ImpressionLog(models.Model):
    """
    Records a single ad impression (view event) for a SmartLink.

    An impression is fired when the SmartLink's tracking pixel is loaded
    in an ad creative — before the user actually clicks. Used for:
      - View-through attribution (VTA)
      - Impression-to-click ratio (CTR-equivalent for affiliate)
      - Reach metrics (unique impressions per campaign)
      - Ad network billing verification (CPM campaigns)
    """
    smartlink   = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='impressions',
        db_index=True,
    )
    offer_id    = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    country     = models.CharField(max_length=2, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    os_type     = models.CharField(max_length=30, blank=True)
    browser     = models.CharField(max_length=50, blank=True)
    referrer    = models.URLField(max_length=1000, blank=True)
    sub1        = models.CharField(max_length=255, blank=True)
    sub2        = models.CharField(max_length=255, blank=True)
    is_unique   = models.BooleanField(default=False, db_index=True)
    is_bot      = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sl_impression_log'
        verbose_name = _('Impression Log')
        indexes = [
            models.Index(fields=['smartlink', 'created_at']),
            models.Index(fields=['smartlink', 'country', 'device_type']),
        ]

    def __str__(self):
        return f"Impression: [{self.smartlink.slug}] {self.country} {self.device_type}"
