"""
click_tracking/click_deduplicator.py
──────────────────────────────────────
Prevents duplicate clicks from being counted.
A "duplicate click" is when the same user clicks the same offer multiple times
within a short window — common with back-button abuse and click flooding.
Uses Redis sliding window counter + DB unique constraint on click_id.
"""
from __future__ import annotations
import logging
from django.core.cache import cache
from django.utils import timezone
from ..models import ClickLog
from ..enums import ClickStatus

logger = logging.getLogger(__name__)

_KEY_USER_OFFER = "pe:click:dedup:uo:{user_id}:{offer_id}"
_DEDUP_WINDOW_SECS = 300   # 5 minutes — same user/offer click within 5min = duplicate


class ClickDeduplicator:

    def is_duplicate(self, user, offer_id: str, click_id: str = "") -> bool:
        """
        Check if this click is a duplicate.
        Returns True if user already clicked same offer within the dedup window.
        """
        if not user or not offer_id:
            return False

        user_id = str(getattr(user, "id", ""))
        cache_key = _KEY_USER_OFFER.format(user_id=user_id, offer_id=offer_id)

        if cache.get(cache_key):
            logger.debug("Duplicate click: user=%s offer=%s", user_id, offer_id[:20])
            return True

        # DB fallback check
        cutoff = timezone.now() - timezone.timedelta(seconds=_DEDUP_WINDOW_SECS)
        exists = ClickLog.objects.filter(
            user=user,
            offer_id=offer_id,
            clicked_at__gte=cutoff,
            status=ClickStatus.VALID,
        ).exclude(click_id=click_id).exists()

        return exists

    def record(self, user, offer_id: str) -> None:
        """Record a click for dedup tracking."""
        if not user or not offer_id:
            return
        user_id = str(getattr(user, "id", ""))
        cache_key = _KEY_USER_OFFER.format(user_id=user_id, offer_id=offer_id)
        try:
            cache.set(cache_key, "1", timeout=_DEDUP_WINDOW_SECS)
        except Exception as exc:
            logger.debug("ClickDeduplicator.record failed (non-fatal): %s", exc)

    def mark_duplicate(self, click_log: ClickLog) -> None:
        click_log.status = ClickStatus.DUPLICATE
        click_log.save(update_fields=["status", "updated_at"])


# Module-level singleton
click_deduplicator = ClickDeduplicator()
