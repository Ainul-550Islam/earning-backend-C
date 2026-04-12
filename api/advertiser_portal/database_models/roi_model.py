"""ROI models."""
from django.db import models
from ..models import AdvertiserPortalBaseModel


class ROICalculation(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='roi_calculations')
    campaign = models.ForeignKey('advertiser_portal.Campaign', on_delete=models.CASCADE, related_name='roi_calculations')
    period_start = models.DateField()
    period_end = models.DateField()
    total_spend = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    roi_percent = models.FloatField(default=0.0)
    roas = models.FloatField(default=0.0)
    class Meta:
        ordering = ['-period_end']
    def __str__(self):
        return f"ROI {self.campaign_id} {self.roi_percent:.1f}%"


class ROIMetric(AdvertiserPortalBaseModel):
    roi_calculation = models.ForeignKey(ROICalculation, on_delete=models.CASCADE, related_name='metrics')
    metric_name = models.CharField(max_length=100)
    metric_value = models.FloatField()
    def __str__(self):
        return f"{self.metric_name}: {self.metric_value}"


class ROIBenchmark(AdvertiserPortalBaseModel):
    industry = models.CharField(max_length=100, db_index=True)
    avg_roi_percent = models.FloatField()
    avg_roas = models.FloatField()
    period = models.CharField(max_length=20)
    def __str__(self):
        return f"Benchmark {self.industry} {self.period}"
