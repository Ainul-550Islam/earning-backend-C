"""Spend tracking models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class SpendRecord(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='spend_records')
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.CASCADE, related_name='spend_records')
    date = models.DateField(db_index=True)
    spend_amount = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default='USD')
    class Meta:
        ordering = ['-date']
    def __str__(self):
        return f"Spend {self.campaign_id} {self.date}"


class SpendAlert(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='spend_alerts')
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.SET_NULL, null=True, blank=True, related_name='spend_alerts')
    alert_type = models.CharField(max_length=50)
    threshold_amount = models.DecimalField(max_digits=14, decimal_places=2)
    current_spend = models.DecimalField(max_digits=14, decimal_places=2)
    is_resolved = models.BooleanField(default=False)
    fired_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['-fired_at']
    def __str__(self):
        return f"SpendAlert {self.alert_type}"


class SpendForecast(AdvertiserPortalBaseModel):
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.CASCADE, related_name='spend_forecasts')
    forecast_date = models.DateField()
    projected_spend = models.DecimalField(max_digits=14, decimal_places=2)
    confidence_score = models.FloatField(default=0.0)
    class Meta:
        ordering = ['-forecast_date']
    def __str__(self):
        return f"Forecast {self.campaign_id} {self.forecast_date}"
