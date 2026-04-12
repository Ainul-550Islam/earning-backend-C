# api/publisher_tools/site_management/site_audience.py
"""Site Audience — Demographics, interests, device breakdown。"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteAudienceSnapshot(TimeStampedModel):
    """Monthly audience snapshot।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_audiencesnap_tenant', db_index=True)
    site = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='audience_snapshots', db_index=True)
    month         = models.DateField()
    # Age
    age_13_17_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_18_24_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_25_34_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_35_44_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_45_54_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_55_plus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    # Gender
    male_pct      = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    female_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    other_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    # Devices
    mobile_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    desktop_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tablet_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    # Geo
    top_countries = models.JSONField(default=list, blank=True)
    primary_country = models.CharField(max_length=100, blank=True)
    # Interests
    top_interests = models.JSONField(default=list, blank=True)
    # Engagement
    avg_session_minutes = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    return_visitor_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    data_source   = models.CharField(max_length=50, default='manual')
    is_estimated  = models.BooleanField(default=False)

    class Meta:
        db_table = 'publisher_tools_site_audience_snapshots'
        verbose_name = _('Audience Snapshot')
        unique_together = [['site', 'month']]
        ordering = ['-month']

    def __str__(self):
        return f"{self.site.domain} Audience — {self.month.strftime('%B %Y')}"
