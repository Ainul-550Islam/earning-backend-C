# =============================================================================
# fraud_detection/mfa_validator.py  — MFA / 2FA VALIDATION SERVICE
#
# Business purpose:
#   - Generate TOTP secrets and QR codes for user enrollment
#   - Validate TOTP codes on login / high-risk actions
#   - Enforce MFA for high-risk users / admin roles
#   - Flag "MFA bypass attempts" as fraud signals
# =============================================================================
from __future__ import annotations
import hashlib, hmac, logging, struct, time
from base64 import b32decode, b32encode
from typing import Any, Optional
import os

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Settings
MFA_TOTP_PERIOD    = getattr(settings, "MFA_TOTP_PERIOD", 30)       # seconds
MFA_TOTP_DIGITS    = getattr(settings, "MFA_TOTP_DIGITS", 6)
MFA_MAX_ATTEMPTS   = getattr(settings, "MFA_MAX_ATTEMPTS", 3)
MFA_LOCKOUT_TTL    = getattr(settings, "MFA_LOCKOUT_TTL", 300)       # 5 min
MFA_WINDOW         = getattr(settings, "MFA_TOTP_WINDOW", 1)         # ±1 period


class MFAService:
    """
    TOTP-based MFA service.
    DRY: single class — used by security views AND fraud detection signals.
    No external library dependency (pure stdlib TOTP implementation).
    """

    # ── Enrollment ─────────────────────────────────────────────────────────────
    def generate_secret(self, user_id: Any) -> str:
        """Generate and cache a TOTP secret for a user."""
        secret = b32encode(os.urandom(20)).decode("utf-8")
        cache.set(f"mfa_secret:{user_id}", secret, timeout=None)  # persist
        logger.info("MFA secret generated for user %s", user_id)
        return secret

    def get_secret(self, user_id: Any) -> Optional[str]:
        return cache.get(f"mfa_secret:{user_id}")

    def get_provisioning_uri(self, user_id: Any, username: str) -> Optional[str]:
        """Return otpauth:// URI for QR code generation."""
        secret = self.get_secret(user_id)
        if not secret:
            return None
        issuer  = getattr(settings, "MFA_ISSUER", "FraudDetection")
        return (f"otpauth://totp/{issuer}:{username}"
                f"?secret={secret}&issuer={issuer}&digits={MFA_TOTP_DIGITS}"
                f"&period={MFA_TOTP_PERIOD}")

    def confirm_enrollment(self, user_id: Any, code: str) -> bool:
        """Verify user entered the correct code after scanning QR."""
        is_valid = self.validate_code(user_id, code)
        if is_valid:
            cache.set(f"mfa_enrolled:{user_id}", True, timeout=None)
            logger.info("MFA enrollment confirmed for user %s", user_id)
        return is_valid

    def is_enrolled(self, user_id: Any) -> bool:
        return bool(cache.get(f"mfa_enrolled:{user_id}"))

    # ── Validation ─────────────────────────────────────────────────────────────
    def validate_code(self, user_id: Any, code: str,
                      context: Optional[str] = None) -> bool:
        """
        Validate a TOTP code.
        Returns True if valid, False otherwise.
        Also records failed attempts and flags brute-force to fraud system.
        """
        if self._is_locked_out(user_id):
            logger.warning("MFA locked out: user=%s", user_id)
            self._flag_mfa_abuse(user_id, "lockout_bypass_attempt", context)
            return False

        secret = self.get_secret(user_id)
        if not secret:
            logger.warning("MFA validate: no secret for user %s", user_id)
            return False

        try:
            cleaned = "".join(filter(str.isdigit, str(code)))
            for delta in range(-MFA_WINDOW, MFA_WINDOW + 1):
                expected = self._generate_totp(secret, delta)
                if hmac.compare_digest(cleaned, expected):
                    self._reset_attempts(user_id)
                    return True
            self._record_failed_attempt(user_id, context)
            return False
        except Exception as exc:
            logger.error("MFA validate error: user=%s exc=%s", user_id, exc)
            return False

    def validate_for_action(self, user_id: Any, code: str,
                             action: str = "generic") -> bool:
        """Validate MFA before a high-risk action (ban, case close, etc.)."""
        return self.validate_code(user_id, code, context=f"action:{action}")

    # ── Enforcement ────────────────────────────────────────────────────────────
    def require_mfa_for_risk_level(self, user_id: Any,
                                   risk_score: int,
                                   threshold: int = 70) -> bool:
        """Return True if user with this risk score must complete MFA."""
        if risk_score < threshold:
            return False
        return not self.is_enrolled(user_id) or not cache.get(f"mfa_verified:{user_id}")

    def mark_session_verified(self, user_id: Any, ttl: int = 3600) -> None:
        """After successful MFA, mark the session as verified for ttl seconds."""
        cache.set(f"mfa_verified:{user_id}", True, timeout=ttl)

    def is_session_verified(self, user_id: Any) -> bool:
        return bool(cache.get(f"mfa_verified:{user_id}"))

    def revoke_session(self, user_id: Any) -> None:
        cache.delete(f"mfa_verified:{user_id}")
        logger.info("MFA session revoked for user %s", user_id)

    # ── Private ────────────────────────────────────────────────────────────────
    def _generate_totp(self, secret: str, delta: int = 0) -> str:
        """RFC 6238 TOTP implementation (no external library needed)."""
        key        = b32decode(secret.upper().replace(" ", ""))
        timestamp  = int(time.time()) // MFA_TOTP_PERIOD + delta
        msg        = struct.pack(">Q", timestamp)
        h          = hmac.new(key, msg, hashlib.sha1).digest()
        offset     = h[-1] & 0x0F
        code       = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
        return str(code % (10 ** MFA_TOTP_DIGITS)).zfill(MFA_TOTP_DIGITS)

    def _is_locked_out(self, user_id: Any) -> bool:
        return bool(cache.get(f"mfa_locked:{user_id}"))

    def _record_failed_attempt(self, user_id: Any,
                                context: Optional[str]) -> None:
        key   = f"mfa_attempts:{user_id}"
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=MFA_LOCKOUT_TTL)
        if count >= MFA_MAX_ATTEMPTS:
            cache.set(f"mfa_locked:{user_id}", True, timeout=MFA_LOCKOUT_TTL)
            self._flag_mfa_abuse(user_id, "max_attempts_exceeded", context)
            logger.warning("MFA lockout triggered: user=%s attempts=%d", user_id, count)

    def _reset_attempts(self, user_id: Any) -> None:
        cache.delete(f"mfa_attempts:{user_id}")
        cache.delete(f"mfa_locked:{user_id}")

    def _flag_mfa_abuse(self, user_id: Any, reason: str,
                         context: Optional[str]) -> None:
        try:
            from api.fraud_detection.signals import fraud_attempt_detected
            fraud_attempt_detected.send(
                sender    = self.__class__,
                user_id   = user_id,
                fraud_type= "mfa_abuse",
                risk_score= 85,
                metadata  = {"reason": reason, "context": context},
            )
        except Exception:
            pass


# ── Singleton ─────────────────────────────────────────────────────────────────
_mfa_service: Optional[MFAService] = None

def get_mfa_service() -> MFAService:
    global _mfa_service
    if _mfa_service is None:
        _mfa_service = MFAService()
    return _mfa_service
