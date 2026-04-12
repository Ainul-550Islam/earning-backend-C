"""
webhook_manager/webhook_analytics.py
──────────────────────────────────────
Analytics for outbound webhook performance.
Tracks delivery rates, latency, failure reasons.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.db.models import Count, Avg
from django.utils import timezone
from ..models import RetryLog

logger = logging.getLogger(__name__)


class WebhookAnalytics:

    def get_delivery_stats(self, days: int = 7) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        qs = RetryLog.objects.filter(retry_type="webhook", attempted_at__gte=cutoff)
        total = qs.count()
        succeeded = qs.filter(succeeded=True).count()
        failed = qs.filter(succeeded=False).count()
        return {
            "period_days": days,
            "total_attempts": total,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate_pct": round((succeeded / total * 100) if total > 0 else 0, 2),
        }

    def get_pending_retries(self) -> int:
        now = timezone.now()
        return RetryLog.objects.filter(
            retry_type="webhook",
            succeeded=False,
            next_retry_at__lte=now,
        ).count()

    def get_failure_breakdown(self, days: int = 7) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            RetryLog.objects.filter(
                retry_type="webhook",
                succeeded=False,
                attempted_at__gte=cutoff,
            )
            .values("attempt_number")
            .annotate(count=Count("id"))
            .order_by("attempt_number")
        )
        return [{"attempt": r["attempt_number"], "failures": r["count"]} for r in rows]


webhook_analytics = WebhookAnalytics()
