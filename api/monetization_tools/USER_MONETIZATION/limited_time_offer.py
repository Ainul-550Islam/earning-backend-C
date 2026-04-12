"""USER_MONETIZATION/limited_time_offer.py — Time-limited offer management."""
from django.utils import timezone
from ..models import Offer


class LimitedTimeOfferManager:
    @classmethod
    def expiring_soon(cls, hours: int = 24, tenant=None) -> list:
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(hours=hours)
        qs = Offer.objects.filter(status="active", expiry_date__lte=cutoff,
                                   expiry_date__gt=timezone.now())
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("expiry_date").values(
            "id", "title", "point_value", "expiry_date", "offer_type",
        ))

    @classmethod
    def countdown_seconds(cls, offer) -> int:
        if not offer.expiry_date:
            return -1
        diff = offer.expiry_date - timezone.now()
        return max(0, int(diff.total_seconds()))

    @classmethod
    def featured_timed(cls, tenant=None) -> list:
        qs = Offer.objects.filter(
            status="active", is_featured=True,
            expiry_date__gt=timezone.now()
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("expiry_date"))
