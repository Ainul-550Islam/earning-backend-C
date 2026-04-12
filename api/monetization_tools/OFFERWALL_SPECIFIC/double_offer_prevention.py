"""OFFERWALL_SPECIFIC/double_offer_prevention.py — Prevents duplicate completions."""
from django.core.cache import cache
from ..models import OfferCompletion


class DoubleOfferPrevention:
    """Multi-layer deduplication for offer completions."""

    LOCK_TTL = 300  # 5 minutes

    @classmethod
    def acquire_lock(cls, user_id, offer_id: int) -> bool:
        key    = f"mt:offer_lock:{user_id}:{offer_id}"
        result = cache.add(key, 1, cls.LOCK_TTL)
        return result

    @classmethod
    def release_lock(cls, user_id, offer_id: int):
        cache.delete(f"mt:offer_lock:{user_id}:{offer_id}")

    @classmethod
    def is_duplicate(cls, user, offer_id: int, network_txn_id: str = "") -> bool:
        # DB check
        if OfferCompletion.objects.filter(
            user=user, offer_id=offer_id, status="approved"
        ).exists():
            return True
        # Network txn dedup
        if network_txn_id and OfferCompletion.objects.filter(
            network_transaction_id=network_txn_id
        ).exists():
            return True
        # Cache-based dedup (short-window)
        key = f"mt:offer_dedup:{user.id}:{offer_id}"
        if cache.get(key):
            return True
        cache.set(key, 1, 3600)
        return False
