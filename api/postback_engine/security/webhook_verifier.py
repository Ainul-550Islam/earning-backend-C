"""
security/webhook_verifier.py
──────────────────────────────
Verifies incoming webhook signatures from third-party platforms.
Each platform has its own signature scheme.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WebhookVerifier:
    """Verifies incoming webhooks from various platforms."""

    def verify_stripe(self, payload: bytes, sig_header: str, secret: str) -> bool:
        """Verify Stripe webhook signature (stripe-signature header)."""
        try:
            parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
            ts = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed = f"{ts}.{payload.decode('utf-8')}"
            expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, v1)
        except Exception as exc:
            logger.warning("Stripe webhook verify failed: %s", exc)
            return False

    def verify_paypal(self, payload: bytes, headers: dict, secret: str) -> bool:
        """Verify PayPal IPN/webhook authenticity."""
        try:
            sig = headers.get("PAYPAL-TRANSMISSION-SIG", "")
            ts = headers.get("PAYPAL-TRANSMISSION-TIME", "")
            cert_url = headers.get("PAYPAL-CERT-URL", "")
            if not all([sig, ts]):
                return False
            message = f"{ts}.{payload.decode('utf-8')}"
            expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, sig)
        except Exception as exc:
            logger.warning("PayPal webhook verify failed: %s", exc)
            return False

    def verify_generic_hmac(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> bool:
        """Generic HMAC verification for any webhook."""
        try:
            algo = getattr(hashlib, algorithm, hashlib.sha256)
            expected = hmac.new(secret.encode(), payload, algo).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as exc:
            logger.warning("Generic webhook verify failed: %s", exc)
            return False

    def verify_applovin(self, query_string: str, secret: str) -> bool:
        """
        Verify AppLovin MAX SSV callback.
        AppLovin signs query string (sorted alphabetically, excluding 'hash').
        """
        try:
            import urllib.parse
            params = dict(urllib.parse.parse_qsl(query_string))
            params.pop("hash", None)
            sorted_qs = urllib.parse.urlencode(sorted(params.items()))
            expected = hashlib.sha256(f"{sorted_qs}{secret}".encode()).hexdigest()
            return hmac.compare_digest(expected, params.get("hash", ""))
        except Exception as exc:
            logger.warning("AppLovin verify failed: %s", exc)
            return False


webhook_verifier = WebhookVerifier()
