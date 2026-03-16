# =============================================================================
# behavior_analytics/reports/weekly_analytics.py
# =============================================================================
"""
Weekly analytics report generator.

Aggregates a full ISO week (Monday–Sunday) of behaviour data:
  - Day-by-day session trend
  - Weekly engagement score averages per tier
  - Most active users (engagement leaders)
  - Worst-performing users (low engagement, optional for re-engagement campaigns)
  - Click category trends
  - Path depth distribution
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """
    Generate a weekly analytics report for the ISO week starting on `week_start`.

    Usage::

        from behavior_analytics.reports.weekly_analytics import WeeklyReportGenerator
        report = WeeklyReportGenerator().generate(week_start=date(2024, 3, 11))
    """

    def generate(self, week_start: date | None = None) -> dict[str, Any]:
        """
        Build and return the weekly report dict.

        `week_start` should be a Monday.  If omitted, defaults to the Monday
        of the previous ISO week.
        """
        if week_start is None:
            today      = timezone.localdate()
            week_start = today - timedelta(days=today.weekday() + 7)

        week_end = week_start + timedelta(days=6)
        logger.info("weekly_report.start week_start=%s week_end=%s", week_start, week_end)

        report: dict[str, Any] = {
            "report_type":  "weekly",
            "week_start":   str(week_start),
            "week_end":     str(week_end),
            "generated_at": timezone.now().isoformat(),
        }

        try:
            report["daily_trend"]       = self._daily_trend(week_start, week_end)
            report["engagement_summary"] = self._engagement_summary(week_start, week_end)
            report["top_users"]          = self._top_users(week_start, week_end, limit=10)
            report["click_trends"]       = self._click_trends(week_start, week_end)
            report["path_depth_dist"]    = self._path_depth_distribution(week_start, week_end)
        except Exception:
            logger.exception(
                "weekly_report.generation_error week_start=%s", week_start
            )
            report["error"] = True

        logger.info("weekly_report.complete week_start=%s", week_start)
        return report

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    @staticmethod
    def _daily_trend(start: date, end: date) -> list[dict[str, Any]]:
        """Session counts grouped by day for the week."""
        from ..models import UserPath
        from django.db.models.functions import TruncDate

        rows = (
            UserPath.objects.filter(created_at__date__range=(start, end))
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                sessions=Count("id"),
                unique_users=Count("user", distinct=True),
            )
            .order_by("day")
        )
        return [
            {
                "date":         str(r["day"]),
                "sessions":     r["sessions"],
                "unique_users": r["unique_users"],
            }
            for r in rows
        ]

    @staticmethod
    def _engagement_summary(start: date, end: date) -> dict[str, Any]:
        from ..models import EngagementScore

        qs = EngagementScore.objects.filter(date__range=(start, end))

        overall = qs.aggregate(
            avg_score=Avg("score"),
            max_score=Max("score"),
            min_score=Min("score"),
            total_records=Count("id"),
        )
        tier_breakdown = dict(
            qs.values("tier")
            .annotate(count=Count("id"))
            .values_list("tier", "count")
        )
        return {
            "avg_score":     round(float(overall["avg_score"] or 0), 2),
            "max_score":     float(overall["max_score"] or 0),
            "min_score":     float(overall["min_score"] or 0),
            "total_records": overall["total_records"] or 0,
            "tier_breakdown": tier_breakdown,
        }

    @staticmethod
    def _top_users(start: date, end: date, limit: int = 10) -> list[dict]:
        from ..models import EngagementScore

        rows = (
            EngagementScore.objects.filter(date__range=(start, end))
            .values("user__id", "user__email")
            .annotate(avg_score=Avg("score"))
            .order_by("-avg_score")[:limit]
        )
        return [
            {
                "user_id":  str(r["user__id"]),
                "email":    r["user__email"],
                "avg_score": round(float(r["avg_score"]), 2),
            }
            for r in rows
        ]

    @staticmethod
    def _click_trends(start: date, end: date) -> list[dict]:
        from ..models import ClickMetric
        from django.db.models.functions import TruncDate

        rows = (
            ClickMetric.objects.filter(clicked_at__date__range=(start, end))
            .annotate(day=TruncDate("clicked_at"))
            .values("day", "category")
            .annotate(count=Count("id"))
            .order_by("day", "category")
        )
        return [
            {
                "date":     str(r["day"]),
                "category": r["category"],
                "count":    r["count"],
            }
            for r in rows
        ]

    @staticmethod
    def _path_depth_distribution(start: date, end: date) -> dict[str, int]:
        """
        Bucket paths by depth (number of unique pages):
          1       → "bounce"
          2–3     → "shallow"
          4–7     → "medium"
          8–15    → "deep"
          16+     → "very_deep"
        """
        from ..models import UserPath

        paths = UserPath.objects.filter(
            created_at__date__range=(start, end)
        ).only("nodes")

        dist = {"bounce": 0, "shallow": 0, "medium": 0, "deep": 0, "very_deep": 0}
        for path in paths.iterator(chunk_size=500):
            depth = path.depth
            if depth <= 1:
                dist["bounce"]    += 1
            elif depth <= 3:
                dist["shallow"]   += 1
            elif depth <= 7:
                dist["medium"]    += 1
            elif depth <= 15:
                dist["deep"]      += 1
            else:
                dist["very_deep"] += 1
        return dist
