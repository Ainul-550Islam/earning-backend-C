"""USER_MONETIZATION/offer_manager.py — User offer wall management."""
from ..services import OfferwallService


class OfferManager:
    @classmethod
    def available(cls, user, country: str = "", device_type: str = "", tenant=None):
        walls  = OfferwallService.get_active(tenant)
        offers = []
        for wall in walls:
            offers.extend(OfferwallService.get_offers(wall.id, user, country, device_type))
        return offers

    @classmethod
    def featured(cls, tenant=None):
        from ..models import Offer
        from django.utils import timezone
        now = timezone.now()
        return Offer.objects.filter(
            is_featured=True, status="active",
        ).filter(
            __import__("django.db.models", fromlist=["Q"]).Q(expiry_date__isnull=True) |
            __import__("django.db.models", fromlist=["Q"]).Q(expiry_date__gt=now)
        ).order_by("-point_value")
