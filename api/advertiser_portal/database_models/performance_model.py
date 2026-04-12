"""Performance metric models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class PerformanceMetric(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='performance_metrics')
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.SET_NULL, null=True, blank=True, related_name='performance_metrics')
    date = models.DateField(db_index=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    spend = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    ctr = models.FloatField(default=0.0)
    cpa = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    roas = models.FloatField(default=0.0)
    class Meta:
        ordering = ['-date']
    def __str__(self):
        return f"Perf {self.advertiser_id} {self.date}"


class PerformanceScore(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='performance_scores')
    score = models.FloatField(default=0.0)
    score_components = models.JSONField(default=dict)
    scored_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['-scored_at']
    def __str__(self):
        return f"Score {self.advertiser_id}: {self.score:.1f}"


class PerformanceAlert(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='performance_alerts')
    alert_type = models.CharField(max_length=50)
    metric_name = models.CharField(max_length=50)
    threshold_value = models.FloatField()
    current_value = models.FloatField()
    is_resolved = models.BooleanField(default=False)
    fired_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['-fired_at']
    def __str__(self):
        return f"PerfAlert {self.alert_type}"
