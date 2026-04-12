# api/offer_inventory/security_fraud/click_signature.py
"""
Click Signature — HMAC-signed, tamper-proof click tokens.
Prevents click injection and token forgery.
"""
import hmac
import hashlib
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

SIGNING_SECRET = getattr(settings, 'CLICK_SIGNING_SECRET', 'change-me-in-production')


class ClickSignatureManager:
    """
    Creates and verifies HMAC-SHA256 click signatures.
    Token format: {click_token}:{timestamp}:{signature}
    """

    @classmethod
    def sign(cls, click_token: str, offer_id: str,
             user_id: str, ip: str) -> str:
        """Generate HMAC signature for a click."""
        payload  = cls._build_payload(click_token, offer_id, user_id, ip)
        sig      = hmac.new(
            SIGNING_SECRET.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return sig

    @classmethod
    def verify(cls, click_token: str, offer_id: str,
               user_id: str, ip: str, signature: str) -> bool:
        """Verify a signature. Timing-safe."""
        if not all([click_token, signature]):
            return False
        expected = cls.sign(click_token, offer_id, user_id, ip)
        return hmac.compare_digest(expected, signature)

    @classmethod
    def create_signed_token(cls, click_token: str, offer_id: str,
                             user_id: str, ip: str) -> str:
        """Return a signed URL-safe token string."""
        ts  = str(int(time.time()))
        sig = cls.sign(click_token + ts, offer_id, user_id, ip)
        return f'{click_token}.{ts}.{sig[:16]}'

    @classmethod
    def verify_signed_token(cls, signed_token: str, offer_id: str,
                             user_id: str, ip: str,
                             max_age_seconds: int = 86400) -> bool:
        """Verify a signed token including freshness check."""
        try:
            parts       = signed_token.rsplit('.', 2)
            if len(parts) != 3:
                return False
            click_token, ts_str, sig_short = parts
            ts = int(ts_str)
            if time.time() - ts > max_age_seconds:
                logger.warning(f'Click token expired: age={(time.time()-ts):.0f}s')
                return False
            full_sig = cls.sign(click_token + ts_str, offer_id, user_id, ip)
            return hmac.compare_digest(full_sig[:16], sig_short)
        except Exception as e:
            logger.warning(f'Token verification error: {e}')
            return False

    @staticmethod
    def _build_payload(click_token: str, offer_id: str,
                       user_id: str, ip: str) -> str:
        return f'{click_token}:{offer_id}:{user_id}:{ip}'

    @staticmethod
    def store(click) -> str:
        """Create signature and persist to DB."""
        from api.offer_inventory.models import ClickSignature
        sig = ClickSignatureManager.sign(
            click_token=click.click_token,
            offer_id   =str(click.offer_id),
            user_id    =str(click.user_id) if click.user_id else '',
            ip         =click.ip_address or '',
        )
        ClickSignature.objects.create(
            click    =click,
            signature=sig,
            algorithm='hmac-sha256',
        )
        return sig
