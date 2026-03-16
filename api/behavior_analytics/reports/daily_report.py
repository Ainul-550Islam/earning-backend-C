# =============================================================================
# behavior_analytics/reports/daily_report.py
# =============================================================================
"""
Daily analytics report generator.

Generates a structured dict (suitable for JSON storage or email delivery)
summarising the previous day's user behaviour:
  - Session counts and status breakdown
  - Device-type distribution
  - Click counts and top elements
  - Stay-time statistics
  - Engagement score distribution by tier
  - Top / bottom engagement users

All DB queries use the manager/queryset API; no raw SQL.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """
    Generate a daily analytics summary report.

    Usage::

        from behavior_analytics.reports.daily_report import DailyReportGenerator
        report = DailyReportGenerator().generate(target_date=date(2024, 3, 15))
    """

    def generate(self, target_date: date | None = None) -> dict[str, Any]:
        """
        Build and return the report dict for `target_date`.
        Defaults to yesterday if not specified.
        """
        if target_date is None:
            target_date = timezone.localdate() - timedelta(days=1)

        logger.info("daily_report.start date=%s", target_date)

        report: dict[str, Any] = {
            "report_type":  "daily",
            "date":         str(target_date),
            "generated_at": timezone.now().isoformat(),
        }

        try:
            report["sessions"]    = self._session_stats(target_date)
            report["clicks"]      = self._click_stats(target_date)
            report["stay_times"]  = self._stay_time_stats(target_date)
            report["engagement"]  = self._engagement_stats(target_date)
            report["row_count"]   = (
                report["sessions"].get("total", 0)
                + report["clicks"].get("total", 0)
            )
        except Exception:
            logger.exception("daily_report.generation_error date=%s", target_date)
            report["error"] = True

        logger.info("daily_report.complete date=%s", target_date)
        return report

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    @staticmethod
    def _session_stats(target_date: date) -> dict[str, Any]:
        from ..models import UserPath

        start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        end = start + timedelta(days=1)

        qs = UserPath.objects.filter(created_at__range=(start, end))

        status_breakdown = dict(
            qs.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )
        device_breakdown = dict(
            qs.values("device_type")
            .annotate(count=Count("id"))
            .values_list("device_type", "count")
        )

        return {
            "total":            qs.count(),
            "status_breakdown": status_breakdown,
            "device_breakdown": device_breakdown,
            "unique_users":     qs.values("user").distinct().count(),
        }

    @staticmethod
    def _click_stats(target_date: date) -> dict[str, Any]:
        from ..models import ClickMetric

        start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        end = start + timedelta(days=1)

        qs = ClickMetric.objects.filter(clicked_at__range=(start, end))

        category_breakdown = dict(
            qs.values("category")
            .annotate(count=Count("id"))
            .values_list("category", "count")
        )
        top_elements = list(
            qs.values("element_selector")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return {
            "total":              qs.count(),
            "category_breakdown": category_breakdown,
            "top_elements":       top_elements,
        }

    @staticmethod
    def _stay_time_stats(target_date: date) -> dict[str, Any]:
        from ..models import StayTime

        start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        end = start + timedelta(days=1)

        agg = (
            StayTime.objects.filter(created_at__range=(start, end))
            .aggregate(
                avg_duration=Avg("duration_seconds"),
                max_duration=Max("duration_seconds"),
                min_duration=Min("duration_seconds"),
                total_duration=Sum("duration_seconds"),
                count=Count("id"),
            )
        )
        return {
            "total_records":    agg["count"] or 0,
            "avg_duration_sec": round(float(agg["avg_duration"] or 0), 2),
            "max_duration_sec": agg["max_duration"] or 0,
            "min_duration_sec": agg["min_duration"] or 0,
            "total_sec":        agg["total_duration"] or 0,
        }

    @staticmethod
    def _engagement_stats(target_date: date) -> dict[str, Any]:
        from ..models import EngagementScore

        qs = EngagementScore.objects.filter(date=target_date)

        agg = qs.aggregate(
            avg_score=Avg("score"),
            max_score=Max("score"),
            min_score=Min("score"),
            count=Count("id"),
        )
        tier_breakdown = dict(
            qs.values("tier")
            .annotate(count=Count("id"))
            .values_list("tier", "count")
        )

        return {
            "total_scores":     agg["count"] or 0,
            "avg_score":        round(float(agg["avg_score"] or 0), 2),
            "max_score":        float(agg["max_score"] or 0),
            "min_score":        float(agg["min_score"] or 0),
            "tier_breakdown":   tier_breakdown,
        }
