"""REVENUE_MODELS/sponsorship_revenue.py — Flat-rate sponsorship revenue."""
from decimal import Decimal
from django.db.models import Sum, Count


class SponsorshipRevenueTracker:
    """Tracks flat-rate / CPD (Cost Per Day) sponsorship revenue."""

    @staticmethod
    def total(tenant=None, start=None, end=None) -> Decimal:
        from ..models import AdCampaign
        qs = AdCampaign.objects.filter(pricing_model="flat", status="ended")
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(start_date__date__gte=start)
        if end:    qs = qs.filter(end_date__date__lte=end)
        return qs.aggregate(t=Sum("spent_budget"))["t"] or Decimal("0")

    @staticmethod
    def daily_rate(total_budget: Decimal, days: int) -> Decimal:
        if not days:
            return Decimal("0")
        return (total_budget / days).quantize(Decimal("0.01"))

    @staticmethod
    def impressions_value(impressions: int, ecpm: Decimal) -> Decimal:
        return (Decimal(impressions) / 1000 * ecpm).quantize(Decimal("0.0001"))
