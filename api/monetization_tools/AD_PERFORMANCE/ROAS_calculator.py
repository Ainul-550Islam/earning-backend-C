"""AD_PERFORMANCE/ROAS_calculator.py — Return on Ad Spend calculator."""
from decimal import Decimal
from django.db.models import Sum


class ROASCalculator:
    """Return on Ad Spend = Revenue / Ad Spend."""

    @staticmethod
    def calculate(revenue: Decimal, spend: Decimal) -> Decimal:
        if not spend:
            return Decimal("0.0000")
        return (revenue / spend).quantize(Decimal("0.0001"))

    @staticmethod
    def for_campaign(campaign_id: int, days: int = 30) -> dict:
        from ..models import AdCampaign, AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        try:
            campaign = AdCampaign.objects.get(pk=campaign_id)
        except AdCampaign.DoesNotExist:
            return {}
        cutoff  = timezone.now().date() - timedelta(days=days)
        revenue = AdPerformanceDaily.objects.filter(
            campaign_id=campaign_id, date__gte=cutoff
        ).aggregate(r=Sum("total_revenue"))["r"] or Decimal("0")
        spend   = campaign.spent_budget or Decimal("0")
        roas    = ROASCalculator.calculate(revenue, spend)
        return {
            "campaign_id": campaign_id,
            "revenue":     revenue,
            "spend":       spend,
            "roas":        roas,
            "profitable":  roas >= Decimal("1.0"),
        }

    @staticmethod
    def target_roas_bid(target_roas: Decimal, cvr_pct: Decimal,
                         avg_order_value: Decimal) -> Decimal:
        """Compute target CPA bid for given ROAS goal."""
        if not target_roas or not cvr_pct:
            return Decimal("0")
        return (avg_order_value * cvr_pct / 100 / target_roas).quantize(Decimal("0.0001"))
