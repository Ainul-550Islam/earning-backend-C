"""OFFERWALL_SPECIFIC/offer_capping.py — Offer daily/total completion caps."""
from django.core.cache import cache
from ..models import OfferCompletion


class OfferCapper:
    """Enforces completion caps at offer and user level."""

    @classmethod
    def daily_completions(cls, user, offer_id: int) -> int:
        from django.utils import timezone
        return OfferCompletion.objects.filter(
            user=user, offer_id=offer_id,
            created_at__date=timezone.now().date(),
        ).count()

    @classmethod
    def total_completions(cls, user, offer_id: int) -> int:
        return OfferCompletion.objects.filter(
            user=user, offer_id=offer_id, status="approved"
        ).count()

    @classmethod
    def is_capped(cls, user, offer) -> dict:
        daily_cap = getattr(offer, "daily_completion_limit", 0)
        total_cap = getattr(offer, "total_completion_limit", 0)
        reasons   = []
        if daily_cap and cls.daily_completions(user, offer.id) >= daily_cap:
            reasons.append("daily_cap_reached")
        if total_cap and cls.total_completions(user, offer.id) >= total_cap:
            reasons.append("total_cap_reached")
        return {"capped": len(reasons) > 0, "reasons": reasons}
