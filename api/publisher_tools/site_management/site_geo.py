# api/publisher_tools/site_management/site_geo.py
"""Site Geo — Geographic distribution and targeting data."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteGeoData(TimeStampedModel):
    """Site geo distribution data — daily。"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitegeo_tenant', db_index=True)
    site          = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='geo_data', db_index=True)
    date          = models.DateField(db_index=True)
    country_code  = models.CharField(max_length=5, db_index=True)
    country_name  = models.CharField(max_length=100, blank=True)
    region        = models.CharField(max_length=100, blank=True)
    city          = models.CharField(max_length=100, blank=True)
    pageviews     = models.BigIntegerField(default=0)
    sessions      = models.BigIntegerField(default=0)
    impressions   = models.BigIntegerField(default=0)
    revenue       = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0.000000'))
    ecpm          = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    traffic_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'publisher_tools_site_geo_data'
        verbose_name = _('Site Geo Data')
        ordering = ['-date', '-revenue']
        indexes = [
            models.Index(fields=['site', 'date'], name='idx_site_date_1647'),
            models.Index(fields=['site', 'country_code'], name='idx_site_country_code_1648'),
        ]

    def __str__(self):
        return f"{self.site.domain} — {self.country_code} — {self.date}"


class SiteGeoTargetingRule(TimeStampedModel):
    """Site-specific geo targeting rules."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitegeo_rule_tenant', db_index=True)
    site           = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='geo_rules')
    rule_type      = models.CharField(max_length=10, choices=[('allow','Allow'),('block','Block')], default='allow')
    country_codes  = models.JSONField(default=list)
    applies_to_ads = models.BooleanField(default=True)
    applies_to_content = models.BooleanField(default=False)
    is_active      = models.BooleanField(default=True)
    reason         = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_site_geo_rules'
        verbose_name = _('Geo Targeting Rule')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.site.domain} — {self.rule_type} {self.country_codes}"
