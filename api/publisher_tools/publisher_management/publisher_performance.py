# api/publisher_tools/publisher_management/publisher_performance.py
"""Publisher Performance — KPI tracking, targets, leaderboard।"""
from decimal import Decimal
from datetime import date, timedelta
from django.db import models
from django.db.models import Sum, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel


class PublisherPerformanceTarget(TimeStampedModel):
    """Publisher-এর monthly performance targets।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_perftarget_tenant', db_index=True)
    publisher              = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='performance_targets')
    year                   = models.IntegerField()
    month                  = models.IntegerField()
    target_revenue         = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    target_impressions     = models.BigIntegerField(default=0)
    target_ecpm            = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'))
    target_fill_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    target_sites           = models.IntegerField(default=0)
    target_apps            = models.IntegerField(default=0)
    bonus_threshold        = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), help_text=_("Revenue needed for performance bonus"))
    bonus_amount           = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    is_bonus_achieved      = models.BooleanField(default=False)
    set_by                 = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'publisher_tools_performance_targets'
        verbose_name = _('Performance Target')
        unique_together = [['publisher', 'year', 'month']]
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.publisher.publisher_id} — Target {self.year}-{self.month:02d}: ${self.target_revenue}"

    def get_actual_performance(self):
        from api.publisher_tools.models import PublisherEarning
        from calendar import monthrange
        last_day = monthrange(self.year, self.month)[1]
        start = date(self.year, self.month, 1)
        end   = date(self.year, self.month, last_day)
        agg = PublisherEarning.objects.filter(
            publisher=self.publisher, date__range=[start, end],
        ).aggregate(revenue=Sum('publisher_revenue'), impressions=Sum('impressions'), ecpm=Avg('ecpm'), fill_rate=Avg('fill_rate'))
        return {
            'revenue':     float(agg.get('revenue') or 0),
            'impressions': agg.get('impressions') or 0,
            'ecpm':        float(agg.get('ecpm') or 0),
            'fill_rate':   float(agg.get('fill_rate') or 0),
        }

    def get_achievement_pct(self):
        actual = self.get_actual_performance()
        if float(self.target_revenue) > 0:
            return round(actual['revenue'] / float(self.target_revenue) * 100, 2)
        return 0.0


class PublisherPerformanceSnapshot(TimeStampedModel):
    """Monthly performance snapshot — historical record।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_perfsnap_tenant', db_index=True)
    publisher          = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='performance_snapshots', db_index=True)
    year               = models.IntegerField()
    month              = models.IntegerField()
    gross_revenue      = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    publisher_revenue  = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    total_impressions  = models.BigIntegerField(default=0)
    total_clicks       = models.BigIntegerField(default=0)
    avg_ecpm           = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    avg_fill_rate      = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    avg_ctr            = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    active_sites       = models.IntegerField(default=0)
    active_apps        = models.IntegerField(default=0)
    active_ad_units    = models.IntegerField(default=0)
    ivt_deduction      = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    ivt_events         = models.IntegerField(default=0)
    quality_score_avg  = models.IntegerField(default=0)
    rank_by_revenue    = models.IntegerField(null=True, blank=True, verbose_name=_("Rank by Revenue (this month)"))
    top_country        = models.CharField(max_length=100, blank=True)
    top_ad_unit        = models.CharField(max_length=50, blank=True)
    growth_pct         = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Revenue Growth vs Previous Month (%)"))
    created_at_date    = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'publisher_tools_performance_snapshots'
        verbose_name = _('Performance Snapshot')
        unique_together = [['publisher', 'year', 'month']]
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['publisher', 'year', 'month'], name='idx_publisher_year_month_1627'),
            models.Index(fields=['rank_by_revenue'], name='idx_rank_by_revenue_1628'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.year}-{self.month:02d} — ${self.publisher_revenue}"


class PublisherLeaderboard(TimeStampedModel):
    """Monthly publisher leaderboard।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_leaderboard_tenant', db_index=True)
    year   = models.IntegerField()
    month  = models.IntegerField()
    entries = models.JSONField(default=list, blank=True, help_text=_("[{'rank': 1, 'publisher_id': 'PUB001', 'revenue': 5000.00}, ...]"))
    total_publishers = models.IntegerField(default=0)
    is_published     = models.BooleanField(default=False)
    published_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_leaderboards'
        verbose_name = _('Publisher Leaderboard')
        unique_together = [['year', 'month']]
        ordering = ['-year', '-month']

    def __str__(self):
        return f"Leaderboard {self.year}-{self.month:02d} — {self.total_publishers} publishers"
