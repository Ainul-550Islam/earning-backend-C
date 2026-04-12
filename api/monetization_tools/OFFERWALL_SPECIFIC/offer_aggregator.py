"""OFFERWALL_SPECIFIC/offer_aggregator.py — Aggregates offers from multiple sources."""
from ..models import Offer, Offerwall


class OfferAggregator:
    """Pulls and merges offers from all active offerwalls."""

    @classmethod
    def all_active(cls, tenant=None, user=None, country: str = "",
                    device_type: str = "") -> list:
        walls = Offerwall.objects.filter(is_active=True)
        if tenant:
            walls = walls.filter(tenant=tenant)
        offers = []
        from ..services import OfferwallService
        for wall in walls:
            wall_offers = OfferwallService.get_offers(wall.id, user, country, device_type)
            offers.extend(wall_offers)
        return offers

    @classmethod
    def by_type(cls, offer_type: str, tenant=None) -> list:
        qs = Offer.objects.filter(offer_type=offer_type, status="active")
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("-point_value"))

    @classmethod
    def count_by_network(cls, tenant=None) -> list:
        from django.db.models import Count
        qs = Offer.objects.filter(status="active")
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("offerwall__network__display_name")
              .annotate(count=Count("id"))
              .order_by("-count")
        )
