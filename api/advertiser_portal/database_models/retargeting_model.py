"""Retargeting models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class RetargetingPixel(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='retargeting_pixels')
    name = models.CharField(max_length=200)
    pixel_id = models.CharField(max_length=64, unique=True, db_index=True)
    pixel_type = models.CharField(max_length=30, default='site_visit')
    pixel_code = models.TextField()
    is_active = models.BooleanField(default=True)
    fire_count = models.BigIntegerField(default=0)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Pixel {self.name}"


class AudienceSegment(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='audience_segments')
    name = models.CharField(max_length=200)
    segment_type = models.CharField(max_length=30, default='site_visitors')
    pixel = models.ForeignKey(RetargetingPixel, on_delete=models.SET_NULL, null=True, blank=True, related_name='audience_segments')
    lookback_days = models.IntegerField(default=30)
    estimated_size = models.BigIntegerField(default=0)
    rules = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Audience {self.name}"


class RetargetingCampaign(AdvertiserPortalBaseModel):
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.CASCADE, related_name='retargeting_configs')
    audience = models.ForeignKey(AudienceSegment, on_delete=models.CASCADE, related_name='retargeting_campaigns')
    bid_multiplier = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)
    class Meta:
        unique_together = [['campaign', 'audience']]
    def __str__(self):
        return f"Retargeting {self.campaign_id}"


class ConversionEvent(AdvertiserPortalBaseModel):
    pixel = models.ForeignKey(RetargetingPixel, on_delete=models.CASCADE, related_name='conversion_events')
    event_type = models.CharField(max_length=50)
    event_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fired_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-fired_at']
    def __str__(self):
        return f"ConvEvent {self.event_type}"
