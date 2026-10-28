"""
utils/s2s_sender.py – S2S (Server-to-Server) outbound postback sender.

Fires an HTTP callback to the advertiser's postback URL after a lead
is successfully processed.

Design principles:
  • Fully self-contained inside the postback app – no other app dependency.
  • Uses httpx for async-friendly HTTP calls (falls back to requests if unavailable).
  • Macro substitution: replaces {lead_id}, {payout}, {goal_id} etc. in the URL.
  • Retries with exponential backoff (3 attempts).
  • Logs success/failure to PostbackS2SLog (lightweight model).
  • Never raises – failures are logged, never bubbled up to the webhook receiver.
"""
import hashlib
import hmac
import logging
import re
import time
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

# Macro pattern: {lead_id}, {PAYOUT}, {Sub_Id1} etc.
_MACRO_PATTERN = re.compile(r"\{(\w+)\}")

# Standard macro names → adapted payload key
_MACRO_MAP = {
    "lead_id": "lead_id",
    "offer_id": "offer_id",
    "user_id": "user_id",
    "payout": "payout",
    "currency": "currency",
    "transaction_id": "transaction_id",
    "goal_id": "goal_id",
    "sub_id": "sub_id1",
    "sub_id1": "sub_id1",
    "sub_id2": "sub_id2",
    "sub_id3": "sub_id3",
    "timestamp": "timestamp",
    "network_key": "_network_key",
    # Extended macros — CPAlead + world standards
    "ip_address": "_source_ip",     # {ip_address} macro
    "ip": "_source_ip",             # {ip} alias
    "country": "country",           # {country} geo
    "device": "device",             # {device}
    "click_id": "click_id",         # {click_id}
    "event_type": "event_type",     # {event_type} — install/sale/lead
    "status": "cpalead_status",     # {status} — approved/reversed
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds


def _substitute_macros(url_template: str, adapted_payload: dict) -> str:
    """
    Replace {macro} placeholders in the URL template with values from adapted_payload.
    Unknown macros are replaced with empty string.
    Values are URL-encoded.
    """
    def replace(match):
        macro_name = match.group(1).lower()
        key = _MACRO_MAP.get(macro_name, macro_name)
        value = adapted_payload.get(key, "")
        return urllib.parse.quote(str(value), safe="")

    return _MACRO_PATTERN.sub(replace, url_template)


def _add_hmac_param(url: str, secret: str, adapted_payload: dict) -> str:
    """
    Optionally sign the outbound postback URL with an HMAC param.
    Appends &sig=<hex> to the URL.
    """
    if not secret:
        return url
    lead_id = adapted_payload.get("lead_id", "")
    payout = adapted_payload.get("payout", "0")
    ts = str(int(time.time()))
    msg = f"{lead_id}:{payout}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sig={sig}&sig_ts={ts}"


def _fire_http(url: str, method: str = "GET", timeout: int = 10) -> tuple:
    """
    Fire the HTTP request. Returns (status_code, response_text, error_msg).
    Tries httpx first, then requests, then urllib.
    """
    # Try httpx (preferred)
    try:
        import httpx
        if method.upper() == "POST":
            r = httpx.post(url, timeout=timeout)
        else:
            r = httpx.get(url, timeout=timeout)
        return r.status_code, r.text[:500], None
    except ImportError:
        pass
    except Exception as e:
        return None, None, str(e)

    # Fallback to requests
    try:
        import requests
        if method.upper() == "POST":
            r = requests.post(url, timeout=timeout)
        else:
            r = requests.get(url, timeout=timeout)
        return r.status_code, r.text[:500], None
    except ImportError:
        pass
    except Exception as e:
        return None, None, str(e)

    # Last resort: urllib
    try:
        import urllib.request
        req = urllib.request.Request(url, method=method.upper())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(500).decode("utf-8", errors="replace"), None
    except Exception as e:
        return None, None, str(e)


def _enforce_https(url: str, network_key: str) -> str:
    """
    Enforce HTTPS on outbound S2S callback URLs.
    HTTP is silently upgraded to HTTPS with a warning.
    Mirrors Everflow / CPAlead best practice.
    """
    if url.startswith("http://"):
        logger.warning(
            "S2S callback URL uses HTTP (insecure) for network=%s — upgrading to HTTPS",
            network_key,
        )
        return "https://" + url[7:]
    return url


def _safe_encode_value(value: str) -> str:
    """
    URL-encode macro values so special characters in sub_ids, emails,
    or campaign names don't break the outbound callback URL.
    Spaces → %20, & → %26, = → %3D, etc.
    """
    return urllib.parse.quote(str(value), safe="")


def fire_s2s_postback(
    *,
    network_config,
    adapted_payload: dict,
    postback_log_id: Optional[str] = None,
) -> bool:
    """
    Fire the S2S outbound postback to the advertiser callback URL.

    Args:
        network_config:   NetworkPostbackConfig instance.
        adapted_payload:  The adapted (standardised) payload dict.
        postback_log_id:  UUID of the PostbackLog for audit linkage.

    Returns:
        True if at least one attempt succeeded (HTTP 2xx), False otherwise.
    """
    # Get callback URL from network config
    callback_url_template = getattr(network_config, "callback_url", "") or ""
    if not callback_url_template.strip():
        # No callback configured – nothing to do
        logger.debug(
            "S2S postback: no callback_url configured for network=%s, skipping.",
            getattr(network_config, "network_key", "?"),
        )
        return True  # Not a failure – just not configured

    # Enrich payload with source_ip so {ip_address} macro works
    adapted_payload = dict(adapted_payload)
    if not adapted_payload.get("_source_ip"):
        adapted_payload["_source_ip"] = getattr(network_config, "_last_source_ip", "")

    # Build final URL
    method = getattr(network_config, "callback_method", "GET") or "GET"
    network_key = getattr(network_config, "network_key", "?")

    final_url = _substitute_macros(callback_url_template, adapted_payload)

    # Enforce HTTPS (never fire over plain HTTP)
    final_url = _enforce_https(final_url, network_key)

    # Optionally sign the URL
    callback_secret = getattr(network_config, "callback_secret", "") or ""
    if callback_secret:
        final_url = _add_hmac_param(final_url, callback_secret, adapted_payload)

    # ── Fire delay (Everflow-style delay_ms) ─────────────────────────────────────────
    delay_ms = 0
    if postback_log_id:
        try:
            from ..models import PostbackLog
            log = PostbackLog.objects.only("fire_delay_ms").get(pk=postback_log_id)
            delay_ms = min(log.fire_delay_ms or 0, 300_000)  # max 5 minutes
        except Exception:
            pass
    if delay_ms > 0:
        logger.debug("S2S delay %dms for log=%s", delay_ms, postback_log_id)
        time.sleep(delay_ms / 1000.0)

    # ── Retry loop ────────────────────────────────────────────────────────────
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        status_code, response_text, error_msg = _fire_http(final_url, method=method)

        if error_msg:
            logger.warning(
                "S2S postback attempt %d/%d failed (network=%s log=%s): %s",
                attempt, _MAX_RETRIES, network_key, postback_log_id, error_msg,
            )
            last_error = error_msg
        elif status_code and 200 <= status_code < 300:
            logger.info(
                "S2S postback success: network=%s log=%s status=%d attempt=%d",
                network_key, postback_log_id, status_code, attempt,
            )
            _record_s2s_result(
                postback_log_id=postback_log_id,
                url=final_url,
                status_code=status_code,
                response_text=response_text,
                success=True,
                attempt=attempt,
            )
            return True
        else:
            logger.warning(
                "S2S postback attempt %d/%d non-2xx: network=%s log=%s status=%s",
                attempt, _MAX_RETRIES, network_key, postback_log_id, status_code,
            )
            last_error = f"HTTP {status_code}"

        if attempt < _MAX_RETRIES:
            backoff = _BACKOFF_BASE ** attempt
            time.sleep(backoff)

    # All retries exhausted
    logger.error(
        "S2S postback all retries exhausted: network=%s log=%s last_error=%s",
        network_key, postback_log_id, last_error,
    )
    _record_s2s_result(
        postback_log_id=postback_log_id,
        url=final_url,
        status_code=None,
        response_text=None,
        success=False,
        attempt=_MAX_RETRIES,
        error=last_error,
    )
    return False


def _record_s2s_result(
    *,
    postback_log_id,
    url: str,
    status_code,
    response_text,
    success: bool,
    attempt: int,
    error: str = None,
):
    """
    Save the S2S attempt result to PostbackS2SLog.
    Wrapped in try/except so DB failures never break the postback flow.
    """
    try:
        from ..models import PostbackS2SLog
        PostbackS2SLog.objects.create(
            postback_log_id=postback_log_id,
            callback_url=url[:2000],
            http_status=status_code,
            response_body=(response_text or "")[:1000],
            success=success,
            attempt_number=attempt,
            error_message=(error or "")[:500],
        )
    except Exception as exc:
        logger.warning("_record_s2s_result: could not save S2SLog: %s", exc)
