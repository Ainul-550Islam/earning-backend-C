"""
utils/click_linker.py – Click-to-conversion linking for postback.

Links an incoming postback (lead_id / click_id) back to the original
OfferClick record stored in the ad_networks app.

Design:
  • Postback app owns the linking logic — OfferClick is read-only from here.
  • Lazy import of OfferClick so postback never hard-depends on ad_networks.
  • lookup_click_id() tries multiple strategies in order:
      1. adapted_payload already contains a click_id field (CPAlead sub_id1).
      2. lead_id matches OfferClick.click_id directly (many networks use same value).
      3. transaction_id matches OfferClick.click_id.
      4. Cache hit from a previous lookup (TTL=10min).
  • Result is stored in PostbackLog.click_id for audit and downstream use.
  • Failures are logged but never block the postback pipeline.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "postback:click_link"
_CACHE_TTL = 600  # 10 minutes


def resolve_click_id(
    *,
    adapted_payload: dict,
    postback_log,
) -> str:
    """
    Try to find the original click_id that triggered this conversion.

    Args:
        adapted_payload:  Normalised payload dict from the adapter.
        postback_log:     PostbackLog instance (not yet saved with click_id).

    Returns:
        click_id string if found, empty string otherwise.
        Also writes the result to postback_log.click_id (caller must save).
    """
    try:
        click_id = _do_resolve(adapted_payload, postback_log)
        if click_id:
            postback_log.click_id = click_id
            logger.debug(
                "click_linker: resolved click_id=%r for log=%s via strategy",
                click_id, postback_log.pk,
            )
        return click_id
    except Exception as exc:
        logger.warning(
            "click_linker: unexpected error for log=%s — %s (non-blocking)",
            getattr(postback_log, "pk", "?"), exc,
        )
        return ""


def _do_resolve(adapted_payload: dict, postback_log) -> str:
    lead_id = str(adapted_payload.get("lead_id", "") or "")
    transaction_id = str(adapted_payload.get("transaction_id", "") or "")
    network_key = str(adapted_payload.get("_network_key", "") or "")

    # ── Strategy 1: payload already has an explicit click_id ─────────────────
    # CPAlead puts click_id in sub_id1 when configured correctly.
    explicit = str(adapted_payload.get("click_id", "") or "").strip()
    if not explicit:
        # Also check sub_id1 — CPAlead convention
        sub1 = str(adapted_payload.get("sub_id1", "") or "").strip()
        if sub1 and _looks_like_click_id(sub1):
            explicit = sub1

    if explicit:
        logger.debug("click_linker: Strategy 1 (explicit) → %r", explicit)
        _cache_result(network_key, lead_id, explicit)
        return explicit

    # ── Strategy 2: Cache hit from previous identical lead_id ────────────────
    cached = _cache_get(network_key, lead_id)
    if cached:
        logger.debug("click_linker: Strategy 2 (cache) → %r", cached)
        return cached

    # ── Strategy 3: lead_id == OfferClick.click_id ───────────────────────────
    if lead_id:
        found = _lookup_offer_click(click_id=lead_id)
        if found:
            logger.debug("click_linker: Strategy 3 (lead_id == click_id) → %r", found)
            _cache_result(network_key, lead_id, found)
            return found

    # ── Strategy 4: transaction_id == OfferClick.click_id ────────────────────
    if transaction_id:
        found = _lookup_offer_click(click_id=transaction_id)
        if found:
            logger.debug("click_linker: Strategy 4 (txn_id == click_id) → %r", found)
            _cache_result(network_key, lead_id, found)
            return found

    logger.debug(
        "click_linker: no match found for lead_id=%r txn=%r network=%r",
        lead_id, transaction_id, network_key,
    )
    return ""


def _lookup_offer_click(click_id: str) -> str:
    """
    Lookup OfferClick by click_id.
    Returns the click_id string if found, empty string otherwise.
    Uses lazy import — postback app never hard-imports ad_networks.
    """
    if not click_id:
        return ""
    try:
        from api.ad_networks.models import OfferClick
        exists = OfferClick.objects.filter(click_id=click_id).only("click_id").exists()
        return click_id if exists else ""
    except ImportError:
        logger.debug("click_linker: ad_networks app not available — skipping DB lookup")
        return ""
    except Exception as exc:
        logger.warning("click_linker: OfferClick lookup error: %s", exc)
        return ""


def _looks_like_click_id(value: str) -> bool:
    """
    Heuristic: does this string look like a click_id (UUID or long hex)?
    Avoids treating short tracking codes (e.g. "US", "mobile") as click_ids.
    """
    import re
    # UUID v4 pattern
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE,
    )
    # Long alphanumeric (32+ chars)
    long_alnum = re.compile(r'^[a-zA-Z0-9_\-]{20,}$')
    return bool(uuid_pattern.match(value) or long_alnum.match(value))


def _cache_key(network_key: str, lead_id: str) -> str:
    import hashlib
    h = hashlib.md5(f"{network_key}:{lead_id}".encode()).hexdigest()[:16]
    return f"{_CACHE_PREFIX}:{h}"


def _cache_get(network_key: str, lead_id: str) -> str:
    if not lead_id:
        return ""
    try:
        return cache.get(_cache_key(network_key, lead_id), "")
    except Exception:
        return ""


def _cache_result(network_key: str, lead_id: str, click_id: str) -> None:
    if not lead_id or not click_id:
        return
    try:
        cache.set(_cache_key(network_key, lead_id), click_id, timeout=_CACHE_TTL)
    except Exception:
        pass
