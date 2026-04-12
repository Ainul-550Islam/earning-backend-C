"""OPTIMIZATION_ENGINES/ad_pacing_engine.py — Campaign budget pacing."""
from decimal import Decimal
from django.utils import timezone


class AdPacingEngine:
    """Controls campaign spend pacing to avoid budget exhaustion."""

    @staticmethod
    def daily_budget_remaining(campaign_id: int) -> Decimal:
        from ..models import AdCampaign
        try:
            c = AdCampaign.objects.get(pk=campaign_id)
            return max(Decimal("0"), (c.daily_budget or Decimal("0")) - (c.daily_spent or Decimal("0")))
        except AdCampaign.DoesNotExist:
            return Decimal("0")

    @staticmethod
    def pacing_rate(campaign_id: int) -> Decimal:
        """Fraction of day elapsed vs fraction of daily budget spent."""
        from ..models import AdCampaign
        try:
            c = AdCampaign.objects.get(pk=campaign_id)
            if not c.daily_budget or c.daily_budget == 0:
                return Decimal("1.0")
            now         = timezone.now()
            day_elapsed = Decimal(str((now.hour * 60 + now.minute) / 1440))
            spent_frac  = (c.daily_spent or Decimal("0")) / c.daily_budget
            return (spent_frac / day_elapsed).quantize(Decimal("0.0001")) if day_elapsed else Decimal("0")
        except AdCampaign.DoesNotExist:
            return Decimal("1.0")

    @staticmethod
    def should_throttle(campaign_id: int, threshold: Decimal = Decimal("1.5")) -> bool:
        return AdPacingEngine.pacing_rate(campaign_id) >= threshold

    @staticmethod
    def recommended_bid_multiplier(campaign_id: int) -> Decimal:
        rate = AdPacingEngine.pacing_rate(campaign_id)
        if rate >= Decimal("1.5"):
            return Decimal("0.5")
        if rate >= Decimal("1.2"):
            return Decimal("0.8")
        if rate <= Decimal("0.5"):
            return Decimal("1.5")
        return Decimal("1.0")
