"""OFFERWALL_SPECIFIC/offer_completion_tracker.py — Tracks offer completions."""
import logging
from decimal import Decimal
from ..models import OfferCompletion

logger = logging.getLogger(__name__)


class OfferCompletionTracker:
    """Records and processes offer completion events."""

    @classmethod
    def record(cls, offer, user, payout_amount: Decimal,
                reward_amount: Decimal, network_txn_id: str = "",
                ip_address: str = "", fraud_score: int = 0,
                tenant=None) -> OfferCompletion:
        status = "fraud" if fraud_score >= 70 else "pending"
        completion = OfferCompletion.objects.create(
            offer=offer, user=user,
            payout_amount=payout_amount,
            reward_amount=reward_amount,
            network_transaction_id=network_txn_id,
            ip_address=ip_address or "127.0.0.1",
            fraud_score=fraud_score,
            status=status,
            tenant=tenant,
        )
        logger.info("OfferCompletion recorded: id=%d user=%s offer=%s fraud=%d status=%s",
                    completion.id, user.id, offer.id, fraud_score, status)
        return completion

    @classmethod
    def approve(cls, completion_id: int, reviewer=None) -> bool:
        from ..services import RewardService
        from django.utils import timezone
        try:
            c = OfferCompletion.objects.get(pk=completion_id, status="pending")
            RewardService.credit(
                c.user, c.reward_amount,
                transaction_type="offer_reward",
                description=f"Offer approved: {c.offer.title}",
                reference_id=str(c.transaction_id),
            )
            OfferCompletion.objects.filter(pk=completion_id).update(
                status="approved", approved_at=timezone.now()
            )
            return True
        except Exception as e:
            logger.error("approve completion %d error: %s", completion_id, e)
            return False
