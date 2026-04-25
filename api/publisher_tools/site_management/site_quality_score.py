# api/publisher_tools/site_management/site_quality_score.py
"""Site Quality Score — Automated quality scoring system."""
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


QUALITY_DIMENSIONS = {
    'viewability':   0.30,
    'content':       0.25,
    'traffic':       0.25,
    'technical':     0.10,
    'compliance':    0.10,
}


def calculate_composite_score(scores: dict) -> int:
    """Weighted composite quality score।"""
    total = sum(scores.get(dim, 0) * weight for dim, weight in QUALITY_DIMENSIONS.items())
    return max(0, min(100, round(total)))


class SiteQualityScore(TimeStampedModel):
    """Detailed site quality score breakdown।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitequalityscore_tenant', db_index=True)
    site                = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='quality_scores', db_index=True)
    date                = models.DateField(db_index=True)
    # Dimension scores
    viewability_score   = models.IntegerField(default=0)
    content_score       = models.IntegerField(default=0)
    traffic_score       = models.IntegerField(default=0)
    technical_score     = models.IntegerField(default=0)
    compliance_score    = models.IntegerField(default=0)
    # Composite
    overall_score       = models.IntegerField(default=0, db_index=True)
    prev_day_score      = models.IntegerField(default=0)
    score_change        = models.IntegerField(default=0)
    score_trend         = models.CharField(max_length=10, choices=[('up','Up'),('down','Down'),('flat','Flat')], default='flat')
    # Flags
    has_malware         = models.BooleanField(default=False)
    has_adult_content   = models.BooleanField(default=False)
    has_policy_violation= models.BooleanField(default=False)
    # Viewability detail
    viewability_rate    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    avg_time_in_view    = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    # Traffic detail
    ivt_rate            = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    bot_rate            = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    # Technical detail
    page_speed_score    = models.IntegerField(null=True, blank=True)
    lcp_ms              = models.IntegerField(null=True, blank=True)
    cls_score           = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    # Alerts
    alerts              = models.JSONField(default=list, blank=True)
    has_alerts          = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'publisher_tools_site_quality_scores'
        verbose_name = _('Site Quality Score')
        unique_together = [['site', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['site', 'date'], name='idx_site_date_1649'),
            models.Index(fields=['overall_score'], name='idx_overall_score_1650'),
            models.Index(fields=['has_alerts'], name='idx_has_alerts_1651'),
        ]

    def __str__(self):
        return f"{self.site.domain} — {self.date} — Score: {self.overall_score}"

    def recalculate(self):
        scores = {
            'viewability': self.viewability_score,
            'content':     self.content_score,
            'traffic':     self.traffic_score,
            'technical':   self.technical_score,
            'compliance':  self.compliance_score,
        }
        self.overall_score = calculate_composite_score(scores)
        prev = SiteQualityScore.objects.filter(site=self.site, date=self.date - timedelta(days=1)).first()
        if prev:
            self.prev_day_score = prev.overall_score
            self.score_change = self.overall_score - prev.overall_score
            self.score_trend = 'up' if self.score_change > 0 else 'down' if self.score_change < 0 else 'flat'
        self.has_alerts = bool(self.alerts) or self.has_malware or self.has_adult_content
        self.save()
        # Update site
        self.site.quality_score = self.overall_score
        self.site.save(update_fields=['quality_score', 'updated_at'])
        return self.overall_score
