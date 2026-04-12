"""ANALYTICS_REPORTING/real_time_analytics.py — Real-time metrics dashboard."""
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache


class RealTimeAnalytics:
    CACHE_TTL = 60  # 1-minute cache

    @classmethod
    def current_metrics(cls, tenant_id=None) -> dict:
        key = f"mt:rt_metrics:{tenant_id or 'all'}"
        cached = cache.get(key)
        if cached:
            return cached
        from ..models import ImpressionLog, ClickLog, OfferCompletion
        from django.db.models import Count, Sum
        last_hour = timezone.now() - timezone.timedelta(hours=1)
        imp = ImpressionLog.objects.filter(logged_at__gte=last_hour, is_bot=False)
        clk = ClickLog.objects.filter(clicked_at__gte=last_hour, is_valid=True)
        ofc = OfferCompletion.objects.filter(created_at__gte=last_hour, status="approved")
        result = {
            "timestamp":      str(timezone.now()),
            "last_hour_imp":  imp.count(),
            "last_hour_clk":  clk.count(),
            "last_hour_offers": ofc.count(),
            "last_hour_coins":  ofc.aggregate(t=Sum("reward_amount"))["t"] or Decimal("0"),
        }
        cache.set(key, result, cls.CACHE_TTL)
        return result

    @classmethod
    def active_users_now(cls) -> int:
        key = "mt:active_users_now"
        return int(cache.get(key, 0))

    @classmethod
    def increment_active_user(cls, user_id: str):
        key = f"mt:au:{user_id}"
        cache.set(key, 1, timeout=300)
