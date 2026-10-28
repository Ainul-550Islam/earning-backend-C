"""
utils/offer_cap.py — Redis-backed daily cap enforcement for offers.

Every OfferClick.record_click() calls check_and_increment().
Falls back to DB count if Redis is unavailable.

Keys:
  offer:cap:global:{offer_id}:{date}   → total completions today (global cap)
  offer:cap:user:{user_id}:{offer_id}:{date} → per-user completions today
"""
import datetime
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

_CAP_KEY_GLOBAL = "offer:cap:global:{offer_id}:{date}"
_CAP_KEY_USER   = "offer:cap:user:{user_id}:{offer_id}:{date}"
_TTL_SECONDS    = 86_400 + 3_600  # 25h — covers clock drift


def _today() -> str:
    return datetime.date.today().isoformat()


def _redis():
    """Return Django's cache backend (must be Redis in production)."""
    from django.core.cache import cache
    return cache


def check_and_increment(offer_id: str, user_id: str) -> Tuple[bool, str]:
    """
    Check caps and atomically increment if within limits.

    Returns:
        (allowed: bool, reason: str)
        allowed=True  → click is within cap, counter incremented
        allowed=False → cap exceeded, counter NOT incremented
    """
    from api.postback.models import Offer
    try:
        offer = Offer.objects.only("daily_cap", "user_daily_cap", "is_active").get(pk=offer_id)
    except Offer.DoesNotExist:
        return False, "offer_not_found"

    if not offer.is_active:
        return False, "offer_inactive"

    today = _today()
    cache = _redis()

    # ── Global cap check ───────────────────────────────────────────────────────
    if offer.daily_cap > 0:
        global_key = _CAP_KEY_GLOBAL.format(offer_id=offer_id, date=today)
        try:
            count = cache.get(global_key, 0)
            if count >= offer.daily_cap:
                return False, "global_cap_exceeded"
        except Exception as exc:
            logger.warning("Cap check Redis error (global): %s — falling back to DB", exc)
            # DB fallback
            from api.postback.models import UserOfferCompletion
            db_count = UserOfferCompletion.objects.filter(
                offer_id=offer_id,
                completed_at__date=datetime.date.today(),
            ).count()
            if db_count >= offer.daily_cap:
                return False, "global_cap_exceeded"

    # ── Per-user cap check ─────────────────────────────────────────────────────
    if offer.user_daily_cap > 0:
        user_key = _CAP_KEY_USER.format(user_id=user_id, offer_id=offer_id, date=today)
        try:
            user_count = cache.get(user_key, 0)
            if user_count >= offer.user_daily_cap:
                return False, "user_cap_exceeded"
        except Exception as exc:
            logger.warning("Cap check Redis error (user): %s — falling back to DB", exc)
            from api.postback.models import UserOfferCompletion
            user_db_count = UserOfferCompletion.objects.filter(
                offer_id=offer_id,
                user_id=user_id,
                completed_at__date=datetime.date.today(),
            ).count()
            if user_db_count >= offer.user_daily_cap:
                return False, "user_cap_exceeded"

    # ── Increment both counters atomically ────────────────────────────────────
    try:
        if offer.daily_cap > 0:
            gk = _CAP_KEY_GLOBAL.format(offer_id=offer_id, date=today)
            if not cache.add(gk, 1, timeout=_TTL_SECONDS):
                cache.incr(gk)
        if offer.user_daily_cap > 0:
            uk = _CAP_KEY_USER.format(user_id=user_id, offer_id=offer_id, date=today)
            if not cache.add(uk, 1, timeout=_TTL_SECONDS):
                cache.incr(uk)
    except Exception as exc:
        logger.warning("Cap increment failed (Redis): %s — continuing anyway", exc)

    return True, "ok"


def get_remaining_cap(offer_id: str) -> dict:
    """Return remaining global cap for today. Used by API response."""
    from api.postback.models import Offer
    today = _today()
    cache = _redis()
    try:
        offer = Offer.objects.only("daily_cap").get(pk=offer_id)
        if offer.daily_cap == 0:
            return {"unlimited": True}
        global_key = _CAP_KEY_GLOBAL.format(offer_id=offer_id, date=today)
        used = cache.get(global_key, 0)
        return {
            "daily_cap": offer.daily_cap,
            "used_today": used,
            "remaining": max(0, offer.daily_cap - used),
        }
    except Exception:
        return {"daily_cap": 0, "used_today": 0, "remaining": 0}


def reset_cap(offer_id: str, user_id: str = None):
    """Admin-only: manually reset cap counters for an offer."""
    today = _today()
    cache = _redis()
    keys = [_CAP_KEY_GLOBAL.format(offer_id=offer_id, date=today)]
    if user_id:
        keys.append(_CAP_KEY_USER.format(user_id=user_id, offer_id=offer_id, date=today))
    for k in keys:
        try:
            cache.delete(k)
        except Exception as exc:
            logger.warning("Cap reset failed for key %s: %s", k, exc)
