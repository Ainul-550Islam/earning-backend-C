"""
DATABASE_MODELS/ad_click_model.py
===================================
Manager / QuerySet for ClickLog.
"""

from __future__ import annotations
from datetime import date, timedelta

from django.db import models
from django.db.models import Count, DecimalField, Q, Sum
from django.utils import timezone


class ClickLogQuerySet(models.QuerySet):

    def valid(self):
        return self.filter(is_valid=True)

    def invalid(self):
        return self.filter(is_valid=False)

    def today(self):
        return self.filter(clicked_at__date=timezone.now().date())

    def last_n_days(self, n: int = 7):
        return self.filter(clicked_at__gte=timezone.now() - timedelta(days=n))

    def in_date_range(self, start: date, end: date):
        return self.filter(clicked_at__date__gte=start, clicked_at__date__lte=end)

    def by_country(self, country: str):
        return self.filter(country=country.upper())

    def revenue_aggregate(self):
        return self.aggregate(
            total_clicks=Count('id'),
            valid_clicks=Count('id', filter=Q(is_valid=True)),
            invalid_clicks=Count('id', filter=Q(is_valid=False)),
            total_revenue=Sum('revenue'),
        )

    def invalid_rate_by_hour(self):
        from django.db.models.functions import TruncHour
        return (
            self.annotate(hour=TruncHour('clicked_at'))
                .values('hour')
                .annotate(
                    total=Count('id'),
                    invalid=Count('id', filter=Q(is_valid=False)),
                )
                .order_by('hour')
        )


class ClickLogManager(models.Manager):
    def get_queryset(self):
        return ClickLogQuerySet(self.model, using=self._db)

    def valid_today(self):
        return self.get_queryset().valid().today()

    def suspicious_ips(self, threshold: int = 50):
        """IPs with high invalid-click counts — potential fraud sources."""
        return (
            self.get_queryset()
                .invalid()
                .values('ip_address')
                .annotate(count=Count('id'))
                .filter(count__gte=threshold)
                .order_by('-count')
        )
