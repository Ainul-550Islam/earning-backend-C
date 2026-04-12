"""
DATABASE_MODELS/ad_conversion_model.py
========================================
Manager / QuerySet for ConversionLog.
"""

from __future__ import annotations
from datetime import date

from django.db import models
from django.db.models import Count, DecimalField, Q, Sum
from django.utils import timezone


class ConversionLogQuerySet(models.QuerySet):

    def verified(self):
        return self.filter(is_verified=True)

    def unverified(self):
        return self.filter(is_verified=False)

    def by_type(self, conversion_type: str):
        return self.filter(conversion_type=conversion_type)

    def in_date_range(self, start: date, end: date):
        return self.filter(converted_at__date__gte=start, converted_at__date__lte=end)

    def for_campaign(self, campaign_id):
        return self.filter(campaign_id=campaign_id)

    def summary_by_type(self):
        return (
            self.values('conversion_type')
                .annotate(
                    count=Count('id'),
                    total_payout=Sum('payout'),
                )
                .order_by('-count')
        )

    def funnel_stats(self, campaign_id):
        """Conversion funnel breakdown for a campaign."""
        from ..models import ClickLog, ImpressionLog
        impressions = ImpressionLog.objects.filter(
            ad_unit__campaign_id=campaign_id
        ).count()
        clicks = ClickLog.objects.filter(
            ad_unit__campaign_id=campaign_id, is_valid=True
        ).count()
        conversions = self.filter(campaign_id=campaign_id, is_verified=True).count()
        return {
            'impressions': impressions,
            'clicks':      clicks,
            'conversions': conversions,
            'ctr':  round(clicks / impressions * 100, 4) if impressions else 0,
            'cvr':  round(conversions / clicks * 100, 4) if clicks else 0,
        }


class ConversionLogManager(models.Manager):
    def get_queryset(self):
        return ConversionLogQuerySet(self.model, using=self._db)

    def verified(self):
        return self.get_queryset().verified()

    def pending_verification(self):
        return self.get_queryset().unverified()
