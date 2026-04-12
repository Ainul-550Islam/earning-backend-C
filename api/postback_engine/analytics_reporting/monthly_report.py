"""
analytics_reporting/monthly_report.py
───────────────────────────────────────
Monthly performance report.
Runs on the 1st of each month at 06:00 UTC.
Aggregates 30 days of NetworkPerformance records into a monthly summary.
Includes: revenue, conversions, CR%, fraud rate, top networks, top offers.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Max
from django.utils import timezone
from ..models import NetworkPerformance, Conversion, ClickLog
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class MonthlyReport:

    def generate(self, year: int = None, month: int = None) -> dict:
        """
        Generate monthly report.
        Defaults to the previous calendar month.
        """
        now = timezone.now()
        if not year or not month:
            first_of_this_month = now.date().replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            year = last_month_end.year
            month = last_month_end.month

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Aggregate from NetworkPerformance daily records
        qs = NetworkPerformance.objects.filter(
            date__gte=month_start,
            date__lte=month_end,
        )
        totals = qs.aggregate(
            total_clicks=Sum("total_clicks"),
            total_conversions=Sum("approved_conversions"),
            total_revenue=Sum("total_payout_usd"),
            total_points=Sum("total_points_awarded"),
            total_fraud_clicks=Sum("fraud_clicks"),
            avg_cr=Avg("conversion_rate"),
            avg_fraud_rate=Avg("fraud_rate"),
            peak_day_conversions=Max("approved_conversions"),
        )

        # Per-network breakdown
        network_breakdown = list(
            qs.values("network__name", "network__network_key")
            .annotate(
                conversions=Sum("approved_conversions"),
                revenue=Sum("total_payout_usd"),
                avg_cr=Avg("conversion_rate"),
            )
            .order_by("-conversions")
        )

        # Top offers this month
        m_start_dt = timezone.make_aware(timezone.datetime(year, month, 1))
        m_end_dt = timezone.make_aware(timezone.datetime(month_end.year, month_end.month, month_end.day, 23, 59, 59))
        top_offers = list(
            Conversion.objects.filter(
                converted_at__gte=m_start_dt,
                converted_at__lte=m_end_dt,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .values("offer_id")
            .annotate(conversions=Count("id"), revenue=Sum("actual_payout"))
            .order_by("-revenue")[:10]
        )

        report = {
            "period": {
                "year": year,
                "month": month,
                "month_name": month_start.strftime("%B %Y"),
                "start": str(month_start),
                "end": str(month_end),
            },
            "totals": {
                "clicks":            totals["total_clicks"] or 0,
                "conversions":       totals["total_conversions"] or 0,
                "revenue_usd":       float(totals["total_revenue"] or 0),
                "points":            totals["total_points"] or 0,
                "fraud_clicks":      totals["total_fraud_clicks"] or 0,
                "avg_cr_pct":        round(float(totals["avg_cr"] or 0), 2),
                "avg_fraud_rate_pct":round(float(totals["avg_fraud_rate"] or 0), 2),
                "peak_day_conversions": totals["peak_day_conversions"] or 0,
            },
            "network_breakdown": [
                {
                    "network": r["network__name"],
                    "network_key": r["network__network_key"],
                    "conversions": r["conversions"] or 0,
                    "revenue_usd": float(r["revenue"] or 0),
                    "avg_cr_pct": round(float(r["avg_cr"] or 0), 2),
                }
                for r in network_breakdown
            ],
            "top_offers": [
                {
                    "offer_id": r["offer_id"],
                    "conversions": r["conversions"],
                    "revenue_usd": float(r["revenue"] or 0),
                }
                for r in top_offers
            ],
        }

        logger.info(
            "MonthlyReport %s: conversions=%d revenue=$%.2f",
            month_start.strftime("%B %Y"),
            report["totals"]["conversions"],
            report["totals"]["revenue_usd"],
        )
        self._notify(report)
        return report

    def _notify(self, report: dict) -> None:
        """Send monthly report notification."""
        try:
            from django.conf import settings
            slack_url = getattr(settings, "SLACK_WEBHOOK_URL", "")
            if not slack_url:
                pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
                slack_url = pe_settings.get("SLACK_WEBHOOK_URL", "")
            if slack_url:
                import requests
                t = report["totals"]
                msg = (
                    f"📊 *Monthly Report — {report['period']['month_name']}*\n"
                    f"💰 Revenue: *${t['revenue_usd']:,.2f}*\n"
                    f"✅ Conversions: *{t['conversions']:,}*\n"
                    f"🖱️ Clicks: *{t['clicks']:,}*\n"
                    f"📈 CR: *{t['avg_cr_pct']}%*\n"
                    f"⚠️ Fraud Rate: *{t['avg_fraud_rate_pct']}%*"
                )
                requests.post(slack_url, json={"text": msg}, timeout=5)
        except Exception as exc:
            logger.debug("MonthlyReport._notify failed (non-fatal): %s", exc)


monthly_report = MonthlyReport()
