"""
DATABASE_MODELS/ad_revenue_model.py
=====================================
Manager / QuerySet for RevenueDailySummary + AdPerformanceDaily.
Fast aggregation helpers for billing and dashboards.
"""

from __future__ import annotations
from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.utils import timezone


class RevenueDailySummaryQuerySet(models.QuerySet):

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def in_date_range(self, start: date, end: date):
        return self.filter(date__gte=start, date__lte=end)

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def for_campaign(self, campaign_id):
        return self.filter(campaign_id=campaign_id)

    def by_country(self, country: str):
        return self.filter(country=country.upper())

    def total_aggregates(self) -> dict:
        return self.aggregate(
            total_revenue=Sum('total_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            avg_ecpm=Avg('ecpm'),
            avg_ctr=Avg('ctr'),
            avg_fill_rate=Avg('fill_rate'),
        )

    def top_countries(self, limit: int = 10):
        return (
            self.values('country')
                .annotate(revenue=Sum('total_revenue'), impressions=Sum('impressions'))
                .order_by('-revenue')[:limit]
        )

    def daily_trend(self):
        return (
            self.values('date')
                .annotate(
                    revenue=Sum('total_revenue'),
                    impressions=Sum('impressions'),
                    ecpm=Avg('ecpm'),
                )
                .order_by('date')
        )

    def network_breakdown(self):
        return (
            self.values('ad_network__display_name', 'ad_network__network_type')
                .annotate(
                    total_revenue=Sum('total_revenue'),
                    total_impressions=Sum('impressions'),
                    avg_ecpm=Avg('ecpm'),
                )
                .order_by('-total_revenue')
        )

    def this_month(self):
        today = timezone.now().date()
        return self.filter(date__year=today.year, date__month=today.month)

    def last_n_days(self, n: int = 30):
        cutoff = timezone.now().date() - timezone.timedelta(days=n)
        return self.filter(date__gte=cutoff)


class RevenueDailySummaryManager(models.Manager):
    def get_queryset(self):
        return RevenueDailySummaryQuerySet(self.model, using=self._db)

    def mtd_for_tenant(self, tenant) -> dict:
        """Month-to-date revenue for a tenant."""
        return self.get_queryset().for_tenant(tenant).this_month().total_aggregates()

    def last_30d(self, tenant=None) -> dict:
        qs = self.get_queryset().last_n_days(30)
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs.total_aggregates()

    def upsert_summary(self, tenant, ad_network, campaign, date_val, country,
                       impressions=0, clicks=0, conversions=0,
                       revenue_cpm=Decimal('0'), revenue_cpc=Decimal('0'),
                       revenue_cpa=Decimal('0'), revenue_cpi=Decimal('0')) -> 'RevenueDailySummary':
        """Atomic upsert of a daily summary row."""
        total = revenue_cpm + revenue_cpc + revenue_cpa + revenue_cpi
        ecpm = (total / impressions * 1000).quantize(Decimal('0.0001')) if impressions else Decimal('0.0000')
        ctr  = (Decimal(clicks) / Decimal(impressions) * 100).quantize(Decimal('0.0001')) if impressions else Decimal('0.0000')

        obj, _ = self.model.objects.update_or_create(
            tenant=tenant,
            ad_network=ad_network,
            campaign=campaign,
            date=date_val,
            country=country or '',
            defaults=dict(
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                revenue_cpm=revenue_cpm,
                revenue_cpc=revenue_cpc,
                revenue_cpa=revenue_cpa,
                revenue_cpi=revenue_cpi,
                total_revenue=total,
                ecpm=ecpm,
                ctr=ctr,
            ),
        )
        return obj
