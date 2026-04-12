"""
analytics_reporting/hourly_report.py
──────────────────────────────────────
Hourly report generation. Runs every hour via Celery beat.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone
from ..models import AdNetworkConfig, HourlyStat, ClickLog, Conversion, PostbackRawLog
from ..enums import ConversionStatus, PostbackStatus

logger = logging.getLogger(__name__)


class HourlyReport:

    def generate(self, for_datetime=None) -> list:
        """
        Generate hourly stats for all active networks.
        Returns list of created/updated HourlyStat records.
        """
        now = for_datetime or timezone.now()
        date = now.date()
        hour = now.hour
        hour_start = timezone.datetime(now.year, now.month, now.day, hour, tzinfo=timezone.utc)
        hour_end = hour_start + timedelta(hours=1)

        results = []
        for network in AdNetworkConfig.objects.active().select_related("tenant"):
            clicks = ClickLog.objects.filter(
                network=network, clicked_at__gte=hour_start, clicked_at__lt=hour_end
            ).count()
            convs_qs = Conversion.objects.filter(
                network=network, converted_at__gte=hour_start, converted_at__lt=hour_end,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            convs = convs_qs.count()
            payout_agg = convs_qs.aggregate(rev=Sum("actual_payout"), pts=Sum("points_awarded"))
            fraud = ClickLog.objects.filter(
                network=network, clicked_at__gte=hour_start, clicked_at__lt=hour_end,
                is_fraud=True,
            ).count()
            rejected = PostbackRawLog.objects.filter(
                network=network, received_at__gte=hour_start, received_at__lt=hour_end,
                status=PostbackStatus.REJECTED,
            ).count()

            stat, _ = HourlyStat.objects.update_or_create(
                network=network, date=date, hour=hour,
                defaults={
                    "tenant": network.tenant,
                    "clicks": clicks,
                    "conversions": convs,
                    "fraud": fraud,
                    "rejected": rejected,
                    "payout_usd": payout_agg["rev"] or Decimal("0"),
                    "points_awarded": payout_agg["pts"] or 0,
                    "conversion_rate": round((convs / clicks * 100) if clicks > 0 else 0, 4),
                    "fraud_rate": round((fraud / clicks * 100) if clicks > 0 else 0, 4),
                },
            )
            results.append(stat)
            logger.debug("HourlyReport: %s %02d:00 → clicks=%d convs=%d", network.network_key, hour, clicks, convs)

        return results


hourly_report = HourlyReport()
