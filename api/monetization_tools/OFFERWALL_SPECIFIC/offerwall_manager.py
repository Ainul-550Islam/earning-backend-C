"""OFFERWALL_SPECIFIC/offerwall_manager.py — Offerwall manager."""
from ..models import Offerwall


class OfferwallManager:
    @staticmethod
    def active(tenant=None):
        qs = Offerwall.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related("network").order_by("sort_order", "name")

    @staticmethod
    def featured(tenant=None):
        qs = Offerwall.objects.filter(is_active=True, is_featured=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def activate(offerwall_id: int) -> bool:
        return bool(Offerwall.objects.filter(pk=offerwall_id).update(is_active=True))

    @staticmethod
    def deactivate(offerwall_id: int) -> bool:
        return bool(Offerwall.objects.filter(pk=offerwall_id).update(is_active=False))

    @staticmethod
    def stats(offerwall_id: int) -> dict:
        from ..models import Offer, OfferCompletion
        from django.db.models import Count, Sum
        offers = Offer.objects.filter(offerwall_id=offerwall_id)
        completions = OfferCompletion.objects.filter(offer__offerwall_id=offerwall_id, status="approved")
        return {
            "total_offers":   offers.count(),
            "active_offers":  offers.filter(status="active").count(),
            "completions":    completions.count(),
            "total_payout":   completions.aggregate(t=Sum("payout_amount"))["t"] or 0,
        }
