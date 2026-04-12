"""AD_PLACEMENTS/ad_unit_manager.py — AdUnit lifecycle management."""
from decimal import Decimal
from django.db.models import F


class AdUnitManager:
    """Manages ad unit creation, updates, and counter ops."""

    @staticmethod
    def create(campaign_id: int, name: str, ad_format: str,
               network_id: int = None, **kwargs):
        from ..models import AdUnit
        return AdUnit.objects.create(
            campaign_id=campaign_id, name=name,
            ad_format=ad_format, ad_network_id=network_id, **kwargs,
        )

    @staticmethod
    def get_active_for_campaign(campaign_id: int):
        from ..models import AdUnit
        return AdUnit.objects.filter(campaign_id=campaign_id, is_active=True)

    @staticmethod
    def increment_impression(unit_id: int, revenue: Decimal = Decimal("0")):
        from ..models import AdUnit
        AdUnit.objects.filter(pk=unit_id).update(
            impressions=F("impressions") + 1,
            revenue=F("revenue") + revenue,
        )

    @staticmethod
    def increment_click(unit_id: int):
        from ..models import AdUnit
        AdUnit.objects.filter(pk=unit_id).update(clicks=F("clicks") + 1)

    @staticmethod
    def get_top_performers(tenant=None, limit: int = 10):
        from ..models import AdUnit
        qs = AdUnit.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-revenue")[:limit]

    @staticmethod
    def pause(unit_id: int) -> bool:
        from ..models import AdUnit
        return bool(AdUnit.objects.filter(pk=unit_id).update(is_active=False))
