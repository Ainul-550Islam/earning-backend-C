"""
analytics_reporting/daily_report.py
─────────────────────────────────────
Daily report generation. Runs at 00:05 UTC via Celery beat.
Computes and stores NetworkPerformance records for the previous day.
Also sends daily summary email/Slack to the ops team.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from django.utils import timezone
from ..models import AdNetworkConfig

logger = logging.getLogger(__name__)


class DailyReport:

    def generate(self, target_date: date = None) -> dict:
        """
        Compute daily NetworkPerformance for all networks.
        Returns summary dict.
        """
        target_date = target_date or (timezone.now() - timedelta(days=1)).date()
        from .network_performance import network_performance_report

        processed = 0
        total_revenue = 0.0
        total_conversions = 0

        for network in AdNetworkConfig.objects.all().select_related("tenant"):
            try:
                perf = network_performance_report.compute_for_date(target_date, network)
                total_revenue += float(perf.total_payout_usd)
                total_conversions += perf.approved_conversions
                processed += 1
            except Exception as exc:
                logger.error("DailyReport failed for network=%s: %s", network.network_key, exc)

        summary = {
            "date": str(target_date),
            "networks_processed": processed,
            "total_revenue_usd": round(total_revenue, 2),
            "total_conversions": total_conversions,
        }
        logger.info("DailyReport generated: %s", summary)
        self._notify(summary)
        return summary

    def _notify(self, summary: dict) -> None:
        """Send daily summary notification (Slack/email)."""
        try:
            from django.conf import settings
            slack_url = getattr(settings, "SLACK_WEBHOOK_URL", "")
            if slack_url:
                import requests
                msg = (
                    f"*Daily Postback Engine Report — {summary['date']}*\n"
                    f"Networks: {summary['networks_processed']} | "
                    f"Conversions: {summary['total_conversions']} | "
                    f"Revenue: ${summary['total_revenue_usd']:,.2f}"
                )
                requests.post(slack_url, json={"text": msg}, timeout=5)
        except Exception as exc:
            logger.debug("DailyReport notify failed (non-fatal): %s", exc)


daily_report = DailyReport()
