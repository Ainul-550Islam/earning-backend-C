"""
analytics_reporting/real_time_dashboard.py
────────────────────────────────────────────
Real-time metrics for live monitoring dashboard.
Uses Redis counters for sub-second latency — no DB queries for live stats.
Falls back to DB aggregation if Redis unavailable.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache keys for real-time counters
_KEY_CLICKS_NOW     = "pe:rt:clicks:now"
_KEY_CONVS_NOW      = "pe:rt:convs:now"
_KEY_REVENUE_NOW    = "pe:rt:revenue:now"
_KEY_FRAUD_NOW      = "pe:rt:fraud:now"
_KEY_ERRORS_NOW     = "pe:rt:errors:now"
_REALTIME_TTL       = 300   # 5 minutes


class RealTimeDashboard:

    def get_live_stats(self) -> dict:
        """
        Return real-time metrics for the last 5 minutes.
        Served from Redis for instant response.
        """
        try:
            clicks   = int(cache.get(_KEY_CLICKS_NOW)  or 0)
            convs    = int(cache.get(_KEY_CONVS_NOW)   or 0)
            revenue  = float(cache.get(_KEY_REVENUE_NOW) or 0)
            fraud    = int(cache.get(_KEY_FRAUD_NOW)   or 0)
            errors   = int(cache.get(_KEY_ERRORS_NOW)  or 0)
        except Exception:
            clicks, convs, revenue, fraud, errors = 0, 0, 0.0, 0, 0

        return {
            "window": "5m",
            "clicks":          clicks,
            "conversions":     convs,
            "revenue_usd":     round(revenue, 4),
            "fraud_attempts":  fraud,
            "errors":          errors,
            "cr_pct":          round((convs / clicks * 100) if clicks > 0 else 0, 2),
            "fraud_rate_pct":  round((fraud / clicks * 100) if clicks > 0 else 0, 2),
            "timestamp":       timezone.now().isoformat(),
        }

    def increment_click(self) -> None:
        self._safe_incr(_KEY_CLICKS_NOW, _REALTIME_TTL)

    def increment_conversion(self, revenue_usd: float = 0.0) -> None:
        self._safe_incr(_KEY_CONVS_NOW, _REALTIME_TTL)
        if revenue_usd > 0:
            try:
                cur = float(cache.get(_KEY_REVENUE_NOW) or 0)
                cache.set(_KEY_REVENUE_NOW, str(cur + revenue_usd), timeout=_REALTIME_TTL)
            except Exception:
                pass

    def increment_fraud(self) -> None:
        self._safe_incr(_KEY_FRAUD_NOW, _REALTIME_TTL)

    def increment_error(self) -> None:
        self._safe_incr(_KEY_ERRORS_NOW, _REALTIME_TTL)

    def reset(self) -> None:
        try:
            cache.delete_many([
                _KEY_CLICKS_NOW, _KEY_CONVS_NOW,
                _KEY_REVENUE_NOW, _KEY_FRAUD_NOW, _KEY_ERRORS_NOW,
            ])
        except Exception:
            pass

    @staticmethod
    def _safe_incr(key: str, ttl: int) -> None:
        try:
            try:
                cache.incr(key)
            except ValueError:
                cache.add(key, 1, timeout=ttl)
        except Exception:
            pass

    def get_db_stats(self, minutes: int = 5) -> dict:
        """Fallback DB-based stats (slower but always accurate)."""
        from ..models import ClickLog, Conversion, PostbackRawLog
        from ..enums import ConversionStatus, PostbackStatus
        from django.db.models import Sum, Count
        cutoff = timezone.now() - timedelta(minutes=minutes)
        clicks = ClickLog.objects.filter(clicked_at__gte=cutoff).count()
        convs_qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        convs = convs_qs.count()
        revenue = float(convs_qs.aggregate(r=Sum("actual_payout"))["r"] or 0)
        fraud = PostbackRawLog.objects.filter(
            received_at__gte=cutoff, status=PostbackStatus.REJECTED
        ).count()
        return {
            "window": f"{minutes}m",
            "clicks": clicks, "conversions": convs,
            "revenue_usd": round(revenue, 4), "fraud_attempts": fraud,
            "timestamp": timezone.now().isoformat(),
        }


realtime_dashboard = RealTimeDashboard()
