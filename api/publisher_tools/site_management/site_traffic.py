# api/publisher_tools/site_management/site_traffic.py
"""Site Traffic — Traffic monitoring, anomaly detection."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteTrafficSnapshot(TimeStampedModel):
    """Hourly site traffic snapshot।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_trafficsnap_tenant', db_index=True)
    site             = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='traffic_snapshots', db_index=True)
    snapshot_hour    = models.DateTimeField(db_index=True)
    pageviews        = models.BigIntegerField(default=0)
    sessions         = models.BigIntegerField(default=0)
    users            = models.BigIntegerField(default=0)
    bot_percentage   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    vpn_percentage   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    mobile_pct       = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    top_country      = models.CharField(max_length=10, blank=True)
    is_anomaly       = models.BooleanField(default=False)
    anomaly_reason   = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'publisher_tools_site_traffic_snapshots'
        verbose_name = _('Traffic Snapshot')
        unique_together = [['site', 'snapshot_hour']]
        ordering = ['-snapshot_hour']
        indexes = [
            models.Index(fields=['site', 'snapshot_hour']),
            models.Index(fields=['is_anomaly']),
        ]

    def __str__(self):
        return f"{self.site.domain} — {self.snapshot_hour} — {self.pageviews:,} views"


class TrafficAnomaly(TimeStampedModel):
    """Traffic anomaly detection records."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_trafficanom_tenant', db_index=True)
    SEVERITY_CHOICES = [('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')]
    ANOMALY_TYPES = [
        ('traffic_spike', 'Traffic Spike'),
        ('bot_surge', 'Bot Traffic Surge'),
        ('click_flood', 'Click Flooding'),
        ('geo_anomaly', 'Geographic Anomaly'),
        ('time_anomaly', 'Time-based Anomaly'),
    ]
    site             = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='traffic_anomalies', db_index=True)
    anomaly_type     = models.CharField(max_length=20, choices=ANOMALY_TYPES, db_index=True)
    severity         = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium', db_index=True)
    detected_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    baseline_value   = models.FloatField(default=0)
    actual_value     = models.FloatField(default=0)
    deviation_pct    = models.FloatField(default=0)
    description      = models.TextField(blank=True)
    is_resolved      = models.BooleanField(default=False)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    action_taken     = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_traffic_anomalies'
        verbose_name = _('Traffic Anomaly')
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.site.domain} — {self.anomaly_type} [{self.severity}] @ {self.detected_at:%Y-%m-%d %H:%M}"
