"""
DATABASE_MODELS/ad_impression_model.py
========================================
Manager / QuerySet for ImpressionLog.
High-volume table — all queries must use index-covered fields.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import (
    Avg, BigIntegerField, Count, DecimalField,
    ExpressionWrapper, F, Q, Sum, Value,
)
from django.utils import timezone


class ImpressionLogQuerySet(models.QuerySet):

    def viewable(self):
        return self.filter(is_viewable=True, is_bot=False)

    def by_country(self, country: str):
        return self.filter(country=country.upper())

    def by_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def in_date_range(self, start: date, end: date):
        return self.filter(logged_at__date__gte=start, logged_at__date__lte=end)

    def today(self):
        return self.filter(logged_at__date=timezone.now().date())

    def last_n_days(self, n: int = 7):
        cutoff = timezone.now() - timedelta(days=n)
        return self.filter(logged_at__gte=cutoff)

    def revenue_aggregate(self):
        """Aggregate revenue and eCPM stats."""
        return self.aggregate(
            total_impressions=Count('id'),
            total_revenue=Sum('revenue'),
            avg_ecpm=Avg('ecpm'),
        )

    def hourly_counts(self):
        """Group by hour for time-series charts."""
        from django.db.models.functions import TruncHour
        return (
            self.annotate(hour=TruncHour('logged_at'))
                .values('hour')
                .annotate(count=Count('id'), revenue=Sum('revenue'))
                .order_by('hour')
        )

    def by_device(self):
        return (
            self.values('device_type')
                .annotate(count=Count('id'), revenue=Sum('revenue'))
                .order_by('-count')
        )


class ImpressionLogManager(models.Manager):
    def get_queryset(self):
        return ImpressionLogQuerySet(self.model, using=self._db)

    def viewable_today(self):
        return self.get_queryset().viewable().today()

    def network_revenue(self, network_id, start: date, end: date):
        return (
            self.get_queryset()
                .by_network(network_id)
                .in_date_range(start, end)
                .revenue_aggregate()
        )
