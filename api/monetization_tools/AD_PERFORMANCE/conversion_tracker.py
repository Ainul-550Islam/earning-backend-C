"""AD_PERFORMANCE/conversion_tracker.py — Conversion event tracking."""
import logging
from decimal import Decimal
from ..models import ConversionLog, AdCampaign

logger = logging.getLogger(__name__)


class ConversionTracker:
    """Records conversions (installs, purchases, leads) for ad campaigns."""

    @classmethod
    def track(cls, campaign_id: int, conversion_type: str,
               payout: Decimal, click=None, user=None,
               is_verified: bool = False, country: str = "",
               device_type: str = "") -> ConversionLog:
        log = ConversionLog.objects.create(
            campaign_id=campaign_id, click=click, user=user,
            conversion_type=conversion_type, payout=payout,
            is_verified=is_verified, country=country or "",
            device_type=device_type or "",
        )
        if is_verified:
            from django.db.models import F
            AdCampaign.objects.filter(pk=campaign_id).update(
                total_conversions=F("total_conversions") + 1,
                spent_budget=F("spent_budget") + payout,
            )
        logger.info("Conversion: campaign=%s type=%s payout=%s", campaign_id, conversion_type, payout)
        return log

    @classmethod
    def cvr(cls, campaign_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            campaign_id=campaign_id, date__gte=cutoff
        ).aggregate(clk=Sum("clicks"), cnv=Sum("conversions"))
        if not agg["clk"]:
            return Decimal("0")
        return (Decimal(agg["cnv"] or 0) / agg["clk"] * 100).quantize(Decimal("0.0001"))

    @classmethod
    def total_revenue(cls, campaign_id: int) -> Decimal:
        from django.db.models import Sum
        return ConversionLog.objects.filter(
            campaign_id=campaign_id, is_verified=True
        ).aggregate(t=Sum("payout"))["t"] or Decimal("0")
