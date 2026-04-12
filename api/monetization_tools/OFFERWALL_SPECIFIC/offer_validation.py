"""OFFERWALL_SPECIFIC/offer_validation.py — Offer completion validation."""
from decimal import Decimal
from django.utils import timezone


class OfferValidator:
    """Validates offer completions before crediting rewards."""

    @classmethod
    def validate(cls, offer, user, payload: dict) -> dict:
        errors = []

        # Check offer active
        if offer.status != "active":
            errors.append("Offer is not active.")

        # Check expiry
        if offer.expiry_date and offer.expiry_date < timezone.now():
            errors.append("Offer has expired.")

        # Check duplicate
        from ..models import OfferCompletion
        if OfferCompletion.objects.filter(
            user=user, offer=offer, status="approved"
        ).exists():
            errors.append("Offer already completed.")

        # Check daily limit
        if offer.daily_completion_limit:
            today_count = OfferCompletion.objects.filter(
                user=user, offer=offer,
                created_at__date=timezone.now().date(),
            ).count()
            if today_count >= offer.daily_completion_limit:
                errors.append("Daily completion limit reached.")

        return {"valid": len(errors) == 0, "errors": errors}
