from django.db import models
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink, SmartLinkVersion
from ..choices import ABTestStatus, DeviceType


class SmartLinkStat(models.Model):
    """
    Hourly aggregated stats per SmartLink.
    Updated every hour by stat_rollup_tasks.py Celery task.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='hourly_stats',
        db_index=True,
    )
    hour = models.DateTimeField(db_index=True, help_text=_('Truncated to hour (YYYY-MM-DD HH:00:00).'))
    country = models.CharField(max_length=2, blank=True, db_index=True)
    device_type = models.CharField(max_length=10, choices=DeviceType.choices, blank=True)

    # Click metrics
    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    bot_clicks = models.PositiveIntegerField(default=0)
    fraud_clicks = models.PositiveIntegerField(default=0)

    # Conversion metrics
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    # Calculated metrics
    epc = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        help_text=_('Earnings per click = revenue / clicks')
    )
    conversion_rate = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        help_text=_('CR = conversions / clicks')
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_smartlink_stat'
        verbose_name = _('SmartLink Hourly Stat')
        unique_together = [('smartlink', 'hour', 'country', 'device_type')]
        indexes = [
            models.Index(fields=['smartlink', 'hour'], name='stat_sl_hour_idx'),
            models.Index(fields=['hour', 'country'], name='stat_hour_country_idx'),
        ]

    def __str__(self):
        return f"Stat: {self.smartlink.slug} {self.hour} | {self.country}/{self.device_type} clicks={self.clicks}"

    def recalculate(self):
        """Recalculate derived metrics from raw counts."""
        self.epc = round(float(self.revenue) / self.clicks, 4) if self.clicks else 0
        self.conversion_rate = round(self.conversions / self.clicks, 4) if self.clicks else 0
        self.save(update_fields=['epc', 'conversion_rate', 'updated_at'])


class SmartLinkDailyStat(models.Model):
    """
    Daily rollup stats per SmartLink.
    Aggregated from SmartLinkStat by stat_rollup_tasks.
    Optimized for dashboard queries.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='daily_stats',
        db_index=True,
    )
    date = models.DateField(db_index=True)

    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    bot_clicks = models.PositiveIntegerField(default=0)
    fraud_clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)

    # Top geo/device for this day
    top_country = models.CharField(max_length=2, blank=True)
    top_device = models.CharField(max_length=10, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_smartlink_daily_stat'
        verbose_name = _('SmartLink Daily Stat')
        unique_together = [('smartlink', 'date')]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'smartlink'], name='daily_date_sl_idx'),
        ]

    def __str__(self):
        return f"Daily: {self.smartlink.slug} {self.date} clicks={self.clicks} rev={self.revenue}"


class OfferPerformanceStat(models.Model):
    """
    Per-offer EPC, conversion rate, and revenue within a SmartLink pool.
    Used to drive EPC-optimized rotation.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='offer_performance_stats',
    )
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.CASCADE,
        related_name='smartlink_performance_stats',
    )
    date = models.DateField(db_index=True)
    country = models.CharField(max_length=2, blank=True)
    device_type = models.CharField(max_length=10, blank=True)

    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_offer_performance_stat'
        verbose_name = _('Offer Performance Stat')
        unique_together = [('smartlink', 'offer', 'date', 'country', 'device_type')]
        indexes = [
            models.Index(fields=['offer', 'date'], name='opstat_offer_date_idx'),
        ]

    def __str__(self):
        return f"OfferStat: {self.smartlink.slug}/Offer#{self.offer_id} {self.date} EPC={self.epc}"


class GeoPerformanceStat(models.Model):
    """
    Per-country EPC and conversion rate for a SmartLink.
    Used for geo-targeted EPC optimization.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='geo_performance_stats',
    )
    country = models.CharField(max_length=2, db_index=True)
    date = models.DateField(db_index=True)

    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_geo_performance_stat'
        verbose_name = _('Geo Performance Stat')
        unique_together = [('smartlink', 'country', 'date')]
        indexes = [
            models.Index(fields=['country', 'date', 'epc'], name='geo_country_date_epc_idx'),
        ]

    def __str__(self):
        return f"GeoStat: {self.smartlink.slug} {self.country} {self.date} EPC={self.epc}"


class DevicePerformanceStat(models.Model):
    """
    Per-device-type performance metrics for a SmartLink.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='device_performance_stats',
    )
    device_type = models.CharField(max_length=10, choices=DeviceType.choices, db_index=True)
    date = models.DateField(db_index=True)

    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_device_performance_stat'
        verbose_name = _('Device Performance Stat')
        unique_together = [('smartlink', 'device_type', 'date')]

    def __str__(self):
        return f"DeviceStat: {self.smartlink.slug} {self.device_type} {self.date} EPC={self.epc}"


class ABTestResult(models.Model):
    """
    A/B test winner determination, confidence level, and uplift.
    Generated by ab_test_tasks.py when statistical significance is reached.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='ab_test_results',
    )
    status = models.CharField(
        max_length=15,
        choices=ABTestStatus.choices,
        default=ABTestStatus.RUNNING,
        db_index=True,
    )
    winner_version = models.ForeignKey(
        SmartLinkVersion, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_tests',
    )
    control_version = models.ForeignKey(
        SmartLinkVersion, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='control_tests',
    )
    confidence_level = models.FloatField(
        default=0.0,
        help_text=_('Statistical confidence (0.0 - 1.0). Significant at 0.95+.')
    )
    uplift_percent = models.FloatField(
        default=0.0,
        help_text=_('Percentage improvement of winner vs control.')
    )
    control_cr = models.FloatField(default=0.0)
    winner_cr = models.FloatField(default=0.0)
    control_clicks = models.PositiveIntegerField(default=0)
    winner_clicks = models.PositiveIntegerField(default=0)
    p_value = models.FloatField(default=1.0, help_text=_('Statistical p-value. Significant at < 0.05.'))
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    auto_applied = models.BooleanField(
        default=False,
        help_text=_('Winner was automatically applied to SmartLink rotation.')
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_ab_test_result'
        verbose_name = _('A/B Test Result')
        ordering = ['-created_at']

    def __str__(self):
        winner = self.winner_version.name if self.winner_version else 'TBD'
        return f"A/B Result: {self.smartlink.slug} | winner={winner} conf={self.confidence_level:.2f}"

    @property
    def is_significant(self):
        return self.confidence_level >= 0.95 and self.p_value < 0.05
