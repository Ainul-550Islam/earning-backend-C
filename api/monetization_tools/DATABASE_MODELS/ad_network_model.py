"""
DATABASE_MODELS/ad_network_model.py
=====================================
QuerySet + Manager for AdNetwork and AdNetworkDailyStat.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date

from django.db import models
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum


class AdNetworkQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def bidding(self):
        return self.filter(is_active=True, is_bidding=True)

    def waterfall_only(self):
        return self.filter(is_active=True, is_bidding=False)

    def by_type(self, network_type: str):
        return self.filter(network_type=network_type)

    def for_country(self, country_code: str):
        """Networks that serve the given country."""
        return self.filter(
            Q(countries_served=[]) |
            Q(countries_served__contains=[country_code.upper()])
        )

    def ordered_by_priority(self):
        return self.active().order_by('priority')

    def above_floor(self, ecpm: Decimal):
        return self.filter(floor_ecpm__lte=ecpm)

    def with_rev_share_calc(self):
        """Annotate publisher net revenue share per impression."""
        return self.annotate(
            net_rev_share=ExpressionWrapper(
                F('revenue_share') * Decimal('100'),
                output_field=DecimalField(max_digits=5, decimal_places=2),
            )
        )

    def revenue_summary(self, start: date = None, end: date = None):
        from ..models import RevenueDailySummary
        qs = RevenueDailySummary.objects.filter(
            ad_network__in=self.values_list('id', flat=True)
        )
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.values('ad_network__display_name').annotate(
            total_revenue=Sum('total_revenue'),
            total_impressions=Sum('impressions'),
            avg_ecpm=Avg('ecpm'),
        ).order_by('-total_revenue')


class AdNetworkManager(models.Manager):
    def get_queryset(self):
        return AdNetworkQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_waterfall(self, country: str = None, ecpm: Decimal = None):
        """
        Return waterfall-ordered networks for mediation.
        Optional: filter by country and floor eCPM.
        """
        qs = self.get_queryset().ordered_by_priority()
        if country:
            qs = qs.for_country(country)
        if ecpm is not None:
            qs = qs.above_floor(ecpm)
        return qs


class AdNetworkDailyStatQuerySet(models.QuerySet):

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def in_date_range(self, start: date, end: date):
        return self.filter(date__gte=start, date__lte=end)

    def high_discrepancy(self, threshold_pct: Decimal = Decimal('5.00')):
        """Networks with discrepancy above threshold — needs investigation."""
        from django.db.models.functions import Abs
        return self.annotate(
            abs_disc=ExpressionWrapper(
                F('discrepancy_pct') * F('discrepancy_pct'),
                output_field=DecimalField(max_digits=7, decimal_places=4),
            )
        ).filter(discrepancy_pct__gte=threshold_pct)

    def revenue_aggregate(self):
        return self.aggregate(
            total_reported=Sum('reported_revenue'),
            avg_ecpm=Avg('reported_ecpm'),
            total_impressions=Sum('reported_impressions'),
        )


class AdNetworkDailyStatManager(models.Manager):
    def get_queryset(self):
        return AdNetworkDailyStatQuerySet(self.model, using=self._db)

    def reconciliation_report(self, start: date, end: date):
        """Revenue reconciliation: our numbers vs network-reported numbers."""
        from ..models import RevenueDailySummary
        from django.db.models import F as FF
        stats = (
            self.get_queryset()
                .in_date_range(start, end)
                .values('ad_network__display_name', 'date')
                .annotate(
                    reported=Sum('reported_revenue'),
                    discrepancy=Avg('discrepancy_pct'),
                )
                .order_by('date', 'ad_network__display_name')
        )
        return list(stats)
