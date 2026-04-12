"""AD_PERFORMANCE/click_tracker.py — Click tracking and validation."""
import logging
from decimal import Decimal
from django.utils import timezone
from ..models import ClickLog, AdUnit

logger = logging.getLogger(__name__)


class ClickTracker:
    """Records ad clicks and validates for fraud."""

    MIN_TIME_AFTER_IMPRESSION_SEC = 0.5
    MAX_CLICKS_PER_IP_PER_HOUR    = 50

    @classmethod
    def track(cls, ad_unit_id: int, revenue: Decimal,
               impression=None, user=None, country: str = "",
               device_type: str = "", ip_address: str = "",
               user_agent: str = "") -> ClickLog:
        is_valid = cls.validate(ip_address, user_agent)
        log = ClickLog.objects.create(
            ad_unit_id=ad_unit_id, impression=impression, user=user,
            country=country or "", device_type=device_type or "",
            ip_address=ip_address or "127.0.0.1",
            revenue=revenue, is_valid=is_valid,
        )
        if is_valid:
            from django.db.models import F
            AdUnit.objects.filter(pk=ad_unit_id).update(clicks=F("clicks") + 1)
        logger.debug("Click: unit=%s valid=%s ip=%s", ad_unit_id, is_valid, ip_address)
        return log

    @classmethod
    def validate(cls, ip_address: str, user_agent: str = "") -> bool:
        from django.core.cache import cache
        key   = f"mt:click_ip:{ip_address}:{timezone.now().strftime('%Y%m%d%H')}"
        count = int(cache.get(key, 0))
        if count >= cls.MAX_CLICKS_PER_IP_PER_HOUR:
            return False
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=3600)
        return True

    @classmethod
    def ctr(cls, ad_unit_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            ad_unit_id=ad_unit_id, date__gte=cutoff
        ).aggregate(imp=Sum("impressions"), clk=Sum("clicks"))
        if not agg["imp"]:
            return Decimal("0")
        return (Decimal(agg["clk"] or 0) / agg["imp"] * 100).quantize(Decimal("0.0001"))
