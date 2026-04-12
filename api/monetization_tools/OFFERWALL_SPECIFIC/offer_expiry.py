"""OFFERWALL_SPECIFIC/offer_expiry.py — Offer expiry management."""
from django.utils import timezone
from ..models import Offer


class OfferExpiryManager:
    """Manages offer expiry — deactivates expired offers."""

    @classmethod
    def expire_due(cls, tenant=None) -> int:
        qs = Offer.objects.filter(status="active", expiry_date__lt=timezone.now())
        if tenant:
            qs = qs.filter(tenant=tenant)
        count = qs.update(status="expired")
        return count

    @classmethod
    def expiring_soon(cls, hours: int = 24, tenant=None):
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(hours=hours)
        qs = Offer.objects.filter(status="active", expiry_date__lte=cutoff,
                                   expiry_date__gt=timezone.now())
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("expiry_date")

    @classmethod
    def extend(cls, offer_id: int, hours: int = 24) -> bool:
        from datetime import timedelta
        now = timezone.now()
        try:
            offer = Offer.objects.get(pk=offer_id)
            if offer.expiry_date:
                offer.expiry_date = offer.expiry_date + timedelta(hours=hours)
            else:
                offer.expiry_date = now + timedelta(hours=hours)
            offer.save(update_fields=["expiry_date"])
            return True
        except Offer.DoesNotExist:
            return False
