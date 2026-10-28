# api/cms/two_factor.py
"""
TOTP-based Two-Factor Authentication service.

Uses pyotp for TOTP and stores the encrypted secret in Django cache
(configurable to DB in production via TwoFactorProfile model).
"""
import hashlib
import logging
import secrets
from typing import List, Tuple

from django.core.cache import cache
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

# Cache key templates
_SECRET_KEY  = "cms:2fa_secret:{user_id}"
_BCODES_KEY  = "cms:2fa_backup:{user_id}"
_USED_KEY    = "cms:2fa_used_backup:{user_id}:{code}"
_ENABLED_KEY = "cms:2fa_enabled:{user_id}"

_CACHE_TTL = 86400 * 30  # 30 days


class TOTPService:
    """Stateless TOTP helper — all state lives in cache (or DB in production)."""

    # ── Setup / teardown ─────────────────────────────────────────────────────

    @staticmethod
    def setup_2fa(user) -> Tuple[str, str]:
        """
        Generate a new TOTP secret for *user* and return (secret, otpauth_uri).

        The secret is stored **unconfirmed** in cache.  Call ``confirm_2fa()``
        after the user verifies their first code to mark it as active.
        """
        try:
            import pyotp
        except ImportError:
            pyotp = None  # type: ignore

        if pyotp:
            secret = pyotp.random_base32()
            totp   = pyotp.TOTP(secret)
            uri    = totp.provisioning_uri(
                name=user.email or str(user),
                issuer_name="CMS",
            )
        else:
            # Fallback without pyotp — still generates a valid base32 secret
            import base64
            raw    = secrets.token_bytes(20)
            secret = base64.b32encode(raw).decode().rstrip('=')
            uri    = (
                f"otpauth://totp/CMS:{user.email or user.id}"
                f"?secret={secret}&issuer=CMS"
            )

        # Persist (encrypted) so confirm_2fa / generate_backup_codes can read it
        from api.cms.encryption import AESCipher
        cache.set(_SECRET_KEY.format(user_id=user.id), AESCipher.encrypt(secret), _CACHE_TTL)
        return secret, uri

    @staticmethod
    def confirm_2fa(user) -> bool:
        """Mark 2FA as confirmed/enabled for this user."""
        if not cache.get(_SECRET_KEY.format(user_id=user.id)):
            return False
        cache.set(_ENABLED_KEY.format(user_id=user.id), True, _CACHE_TTL)
        return True

    @staticmethod
    def disable_2fa(user) -> None:
        """Remove all 2FA data for this user."""
        uid = user.id
        cache.delete(_SECRET_KEY.format(user_id=uid))
        cache.delete(_BCODES_KEY.format(user_id=uid))
        cache.delete(_ENABLED_KEY.format(user_id=uid))

    # ── Status ────────────────────────────────────────────────────────────────

    @staticmethod
    def is_enabled(user) -> bool:
        """Return True only when 2FA has been confirmed (not just set up)."""
        return bool(cache.get(_ENABLED_KEY.format(user_id=user.id)))

    # ── TOTP verification ─────────────────────────────────────────────────────

    @staticmethod
    def verify_totp(user, code: str) -> bool:
        """Verify a 6-digit TOTP code against the user's stored secret."""
        try:
            import pyotp
            from api.cms.encryption import AESCipher
            encrypted = cache.get(_SECRET_KEY.format(user_id=user.id))
            if not encrypted:
                return False
            secret = AESCipher.decrypt(encrypted)
            return pyotp.TOTP(secret).verify(code)
        except Exception as exc:
            logger.warning(f"TOTP verify failed for user {user.id}: {exc}")
            return False

    # ── Backup codes ──────────────────────────────────────────────────────────

    @staticmethod
    def generate_backup_codes(user, count: int = 8) -> List[str]:
        """
        Generate *count* one-time backup codes (each 8 hex chars long).
        Stores a hashed copy in cache; returns the plain codes once.
        """
        codes = [secrets.token_hex(4) for _ in range(count)]  # 4 bytes → 8 hex chars
        hashed = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
        cache.set(_BCODES_KEY.format(user_id=user.id), hashed, _CACHE_TTL)
        return codes

    @staticmethod
    def verify_backup_code(user, code: str) -> bool:
        """
        Verify and consume a backup code.
        Returns True only on first use; subsequent calls with the same code return False.
        """
        used_key = _USED_KEY.format(user_id=user.id, code=code)
        if cache.get(used_key):
            return False  # already consumed

        hashed_codes = cache.get(_BCODES_KEY.format(user_id=user.id)) or []
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in hashed_codes:
            cache.set(used_key, True, _CACHE_TTL)  # mark consumed
            return True
        return False
