"""OFFERWALL_SPECIFIC/offer_filter.py — Offer filtering engine."""
from django.utils import timezone


class OfferFilter:
    @classmethod
    def by_country(cls, offers: list, country: str) -> list:
        if not country:
            return offers
        return [
            o for o in offers
            if not getattr(o, "target_countries", None)
            or country.upper() in (o.target_countries or [])
        ]

    @classmethod
    def by_device(cls, offers: list, device_type: str) -> list:
        if not device_type:
            return offers
        return [
            o for o in offers
            if not getattr(o, "target_devices", None)
            or device_type.lower() in (o.target_devices or [])
        ]

    @classmethod
    def by_type(cls, offers: list, offer_type: str) -> list:
        if not offer_type or offer_type == "all":
            return offers
        return [o for o in offers if getattr(o, "offer_type", "") == offer_type]

    @classmethod
    def exclude_completed(cls, offers: list, user) -> list:
        from ..models import OfferCompletion
        completed = set(
            OfferCompletion.objects.filter(user=user, status="approved")
              .values_list("offer_id", flat=True)
        )
        return [o for o in offers if o.id not in completed]

    @classmethod
    def not_expired(cls, offers: list) -> list:
        now = timezone.now()
        return [
            o for o in offers
            if not getattr(o, "expiry_date", None) or o.expiry_date > now
        ]
