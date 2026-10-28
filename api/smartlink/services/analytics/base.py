"""
SmartLink Analytics — Base Service
=====================================
Before this file: `cutoff = timezone.now().date() - datetime.timedelta(days=days)`
appeared **21 times** across 5 analytics service files.

Now every analytics service that needs a date window inherits
AnalyticsServiceBase and calls self.date_cutoff(days) or self.datetime_cutoff(days).

Shared aggregation field dict also extracted — was duplicated between
EPCCalculatorService and ConversionRateService.
"""
import datetime
import logging
from typing import Optional

from django.db import models
from django.utils import timezone

logger = logging.getLogger("smartlink.services.analytics")


class AnalyticsServiceBase:
    """
    Base class for all SmartLink analytics services.

    Provides:
        date_cutoff(days)     → datetime.date (for .date() field filters)
        datetime_cutoff(days) → datetime.datetime (for .created_at filters)
        click_qs(publisher_id, days, include_fraud, smartlink_slug)
            → annotated Click queryset, scoped and filtered consistently
        _agg_fields()         → standard annotation dict shared by EPC + CR services
    """

    # ── Window helpers ────────────────────────────────────────────────────────

    @staticmethod
    def date_cutoff(days: int) -> datetime.date:
        """
        Return the start date of a lookback window ending today.
        Previously inline in every analytics service:
            cutoff = timezone.now().date() - datetime.timedelta(days=days)
        """
        return timezone.now().date() - datetime.timedelta(days=days)

    @staticmethod
    def datetime_cutoff(days: int) -> datetime.datetime:
        """
        Return the start datetime of a lookback window ending now.
        For use with DateTimeField filters (created_at, updated_at).
        """
        return timezone.now() - datetime.timedelta(days=days)

    # ── Shared queryset builder ───────────────────────────────────────────────

    @staticmethod
    def click_qs(
        publisher_id:   int,
        days:           int,
        *,
        include_fraud:  bool = False,
        include_bot:    bool = False,
        smartlink_slug: Optional[str] = None,
    ) -> models.QuerySet:
        """
        Return a filtered Click queryset for analytics.

        Before: EPCCalculatorService, ConversionRateService, SmartLinkAnalyticsService,
        RevenueAttributionService, and ConversionFunnelService each re-built this
        queryset from scratch with the same logic.
        """
        from api.smartlink.models import Click

        cutoff = AnalyticsServiceBase.date_cutoff(days)
        qs = Click.objects.filter(
            smartlink__publisher_id=publisher_id,
            created_at__date__gte=cutoff,
        )
        if not include_fraud:
            qs = qs.filter(is_fraud=False)
        if not include_bot:
            qs = qs.filter(is_bot=False)
        if smartlink_slug:
            qs = qs.filter(smartlink__slug=smartlink_slug)
        return qs

    # ── Shared annotation dict ────────────────────────────────────────────────

    @staticmethod
    def _agg_fields() -> dict:
        """
        Standard annotation fields for EPC / conversion-rate aggregation.

        Was duplicated between EPCOptimizer and OfferScoreService:
            defaults={'epc': epc, 'conversion_rate': cr,
                      'total_clicks': clicks, 'total_conversions': conversions, ...}

        Now both services call AnalyticsServiceBase._agg_fields() to build
        the dict, then add their own extra keys if needed.
        """
        from django.db.models import Count, Sum, Q
        from django.db.models.functions import Coalesce
        return {
            "total_clicks":      Count("id"),
            "total_conversions": Count("id", filter=Q(is_converted=True)),
            "total_revenue":     Coalesce(Sum("payout"), 0),
        }

    # ── Score builder (was duplicated between EPCOptimizer + OfferScoreService)

    @staticmethod
    def build_score_defaults(
        epc:         float,
        cr:          float,
        clicks:      int,
        conversions: int,
        revenue:     float,
    ) -> dict:
        """
        Build the score update dict shared by EPCOptimizer.recalculate_scores()
        and OfferScoreService.update_score().

        Before: identical dict literal in both services:
            defaults = {
                'epc': epc, 'conversion_rate': cr,
                'total_clicks': clicks, 'total_conversions': conversions,
                'total_revenue': revenue,
            }
        """
        return {
            "epc":              epc,
            "conversion_rate":  cr,
            "total_clicks":     clicks,
            "total_conversions": conversions,
            "total_revenue":    revenue,
        }
