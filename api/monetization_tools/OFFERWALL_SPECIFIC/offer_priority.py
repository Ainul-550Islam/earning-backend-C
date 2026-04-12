"""OFFERWALL_SPECIFIC/offer_priority.py — Offer display priority ranking."""
from decimal import Decimal
from typing import List


class OfferPriorityRanker:
    """Ranks offers by combined priority score for display ordering."""

    WEIGHTS = {
        "payout":    Decimal("0.4"),
        "featured":  Decimal("0.3"),
        "hot":       Decimal("0.15"),
        "new":       Decimal("0.10"),
        "expiry":    Decimal("0.05"),
    }

    @classmethod
    def score(cls, offer) -> Decimal:
        s = Decimal("0")
        s += Decimal(str(getattr(offer, "point_value", 0))) / 1000 * cls.WEIGHTS["payout"]
        s += cls.WEIGHTS["featured"] if getattr(offer, "is_featured", False) else Decimal("0")
        s += cls.WEIGHTS["hot"]      if getattr(offer, "is_hot", False)      else Decimal("0")
        expiry = getattr(offer, "expiry_date", None)
        if expiry:
            from django.utils import timezone
            from datetime import timedelta
            hours_left = (expiry - timezone.now()).total_seconds() / 3600
            if hours_left < 24:
                s += cls.WEIGHTS["expiry"]
        return s.quantize(Decimal("0.0001"))

    @classmethod
    def rank(cls, offers: list) -> list:
        return sorted(offers, key=lambda o: cls.score(o), reverse=True)
