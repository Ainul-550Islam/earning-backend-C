"""OFFERWALL_SPECIFIC/offer_notification.py — Offer event notifications."""
import logging
from ..services import NotificationService

logger = logging.getLogger(__name__)


class OfferNotificationSender:
    """Sends offer-related notifications to users."""

    @classmethod
    def on_approved(cls, completion) -> bool:
        return NotificationService.send(
            completion.user, "offer_approved",
            context={
                "offer_title":  completion.offer.title,
                "coins_earned": str(completion.reward_amount),
            },
            tenant=completion.tenant,
        )

    @classmethod
    def on_rejected(cls, completion, reason: str = "") -> bool:
        return NotificationService.send(
            completion.user, "offer_rejected",
            context={
                "offer_title": completion.offer.title,
                "reason":      reason,
            },
            tenant=completion.tenant,
        )

    @classmethod
    def on_new_offer(cls, users, offer) -> int:
        return NotificationService.send_bulk(
            users, "offer_approved",
            context={"offer_title": offer.title, "points": str(offer.point_value)},
        )

    @classmethod
    def on_expiring_soon(cls, users, offer, hours_left: int = 24) -> int:
        return NotificationService.send_bulk(
            users, "offer_approved",
            context={"offer_title": offer.title, "hours_left": hours_left},
        )
