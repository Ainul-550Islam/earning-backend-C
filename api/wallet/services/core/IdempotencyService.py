# api/wallet/services/core/IdempotencyService.py
"""
Idempotency key management — prevents duplicate transactions.

Usage:
    ikey = IdempotencyService.get("my-unique-key")
    if ikey:
        return ikey.response_data  # replay cached response
    # ... execute transaction ...
    IdempotencyService.save("my-unique-key", response_data, wallet=wallet)
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from ...models import IdempotencyKey
from ...constants import IDEMPOTENCY_TTL

logger = logging.getLogger("wallet.service.idempotency")


class IdempotencyService:

    @staticmethod
    def get(key: str) -> "IdempotencyKey | None":
        """Return a valid (non-expired) idempotency key, or None."""
        return IdempotencyKey.get_valid(key)

    @staticmethod
    def save(key: str, response_data: dict, wallet=None, user=None,
             amount: Decimal = None, ttl: int = None) -> IdempotencyKey:
        """
        Register a new idempotency key after a successful transaction.
        Overwrites expired keys with the same key string.
        """
        expires_at = timezone.now() + timedelta(seconds=ttl or IDEMPOTENCY_TTL)

        ikey, created = IdempotencyKey.objects.update_or_create(
            key=key,
            defaults={
                "wallet":        wallet,
                "user":          user or (wallet.user if wallet else None),
                "amount":        amount,
                "response_data": response_data,
                "expires_at":    expires_at,
            },
        )
        action = "created" if created else "refreshed"
        logger.debug(f"IdempotencyKey {action}: key={key} expires={expires_at}")
        return ikey

    @staticmethod
    def cleanup() -> int:
        """
        Delete expired idempotency keys.
        Called by cleanup_tasks daily.
        Returns count of deleted keys.
        """
        count, _ = IdempotencyKey.objects.filter(expires_at__lt=timezone.now()).delete()
        logger.info(f"Cleaned {count} expired idempotency keys")
        return count

    @staticmethod
    def is_duplicate(key: str) -> bool:
        """Quick check — returns True if key exists and is not expired."""
        return IdempotencyService.get(key) is not None
