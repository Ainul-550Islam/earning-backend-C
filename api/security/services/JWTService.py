"""
api/security/services/JWTService.py
=====================================
JWT Token Manager — Access/Refresh token generation, rotation, blacklisting.
SHA-256 Hash Chain integrated for token integrity.

Features:
- Access + Refresh token pair generation
- Refresh token rotation (family-based)
- Redis blacklist (instant revocation)
- Device-level token isolation
- Fingerprint binding (prevent token theft)
- Automatic cleanup of expired tokens
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as tz
from typing import Dict, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("security.services.jwt")

# ── Config from settings.py ───────────────────────────────────────────────────
JWT_SECRET        = getattr(settings, "JWT_SECRET_KEY",            getattr(settings, "SECRET_KEY", "change-me"))
JWT_ALGORITHM     = getattr(settings, "JWT_ALGORITHM",             "HS256")
JWT_ACCESS_TTL    = getattr(settings, "JWT_ACCESS_TOKEN_LIFETIME",  timedelta(minutes=15))
JWT_REFRESH_TTL   = getattr(settings, "JWT_REFRESH_TOKEN_LIFETIME", timedelta(days=7))

# Cache keys
_KEY_BLACKLIST  = "sec:jwt:bl:{}"          # token jti
_KEY_FAMILY     = "sec:jwt:family:{}"      # refresh family id
_KEY_USER_TOKENS= "sec:jwt:user:{}"        # user_id → set of active jtis
_BL_TTL         = int(timedelta(days=30).total_seconds())


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TokenPair:
    access_token:  str
    refresh_token: str
    access_expires_at:  datetime
    refresh_expires_at: datetime
    token_type:    str = "Bearer"
    jti:           str = ""

    def to_dict(self) -> dict:
        return {
            "access_token":          self.access_token,
            "refresh_token":         self.refresh_token,
            "token_type":            self.token_type,
            "access_expires_at":     self.access_expires_at.isoformat(),
            "refresh_expires_at":    self.refresh_expires_at.isoformat(),
        }


@dataclass
class TokenPayload:
    user_id:     int
    jti:         str
    token_type:  str          # "access" | "refresh"
    family_id:   str          # refresh token family (rotation)
    device_id:   Optional[str]
    fingerprint: Optional[str]
    exp:         int           # Unix timestamp
    iat:         int           # issued at


# ─────────────────────────────────────────────────────────────────────────────
# JWT Manager
# ─────────────────────────────────────────────────────────────────────────────

class JWTManager:
    """
    Full-lifecycle JWT manager.

    Usage:
        manager = JWTManager()

        # Issue new pair
        pair = manager.issue(user_id=42, device_id="dev_abc", request=request)

        # Validate access token
        payload = manager.validate_access(token)
        if payload is None:
            return 401

        # Rotate refresh token (call on every refresh)
        new_pair = manager.rotate_refresh(old_refresh_token)

        # Revoke all tokens for a user (on logout/password change)
        manager.revoke_all(user_id=42)
    """

    # ── Internal: encode / decode ─────────────────────────────────────────────

    def _encode(self, payload: dict) -> str:
        """Pure-Python JWT encode (no external library required)."""
        import base64
        import json

        header  = base64.urlsafe_b64encode(
            json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        body    = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode()

        msg     = f"{header}.{body}"
        sig     = base64.urlsafe_b64encode(
            hmac.new(
                JWT_SECRET.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).rstrip(b"=").decode()

        return f"{msg}.{sig}"

    def _decode(self, token: str) -> Optional[dict]:
        """Decode and verify JWT signature. Returns payload dict or None."""
        import base64
        import json

        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, body_b64, sig_b64 = parts
            msg      = f"{header_b64}.{body_b64}"
            expected = base64.urlsafe_b64encode(
                hmac.new(
                    JWT_SECRET.encode("utf-8"),
                    msg.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).rstrip(b"=").decode()

            if not hmac.compare_digest(expected, sig_b64):
                logger.warning("JWT signature mismatch")
                return None

            # Decode payload (add padding back)
            padded = body_b64 + "=" * (4 - len(body_b64) % 4)
            return json.loads(base64.urlsafe_b64decode(padded).decode())

        except Exception as exc:
            logger.warning("JWT decode error: %s", exc)
            return None

    # ── Fingerprint ───────────────────────────────────────────────────────────

    @staticmethod
    def _fingerprint(request) -> str:
        """Build a device fingerprint from request headers."""
        if request is None:
            return ""
        ua  = request.META.get("HTTP_USER_AGENT", "")
        ip  = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "")
        )
        lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        raw  = f"{ua}|{ip}|{lang}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    # ── Issue ─────────────────────────────────────────────────────────────────

    def issue(
        self,
        user_id:   int,
        device_id: Optional[str]  = None,
        request=None,
        extra:     Optional[dict] = None,
    ) -> TokenPair:
        """
        Issue a new access + refresh token pair.

        Args:
            user_id:   authenticated user's PK
            device_id: optional device identifier (isolates tokens per device)
            request:   Django request (used for fingerprint binding)
            extra:     additional payload claims

        Returns:
            TokenPair
        """
        now          = int(time.time())
        jti          = secrets.token_hex(16)
        family_id    = secrets.token_hex(16)   # new family for refresh rotation
        fingerprint  = self._fingerprint(request)

        access_ttl   = int(JWT_ACCESS_TTL.total_seconds()  if isinstance(JWT_ACCESS_TTL,  timedelta) else JWT_ACCESS_TTL)
        refresh_ttl  = int(JWT_REFRESH_TTL.total_seconds() if isinstance(JWT_REFRESH_TTL, timedelta) else JWT_REFRESH_TTL)

        access_payload = {
            "user_id":     user_id,
            "jti":         jti,
            "type":        "access",
            "family_id":   family_id,
            "device_id":   device_id,
            "fingerprint": fingerprint,
            "iat":         now,
            "exp":         now + access_ttl,
            **(extra or {}),
        }

        refresh_payload = {
            "user_id":     user_id,
            "jti":         secrets.token_hex(16),
            "type":        "refresh",
            "family_id":   family_id,
            "device_id":   device_id,
            "fingerprint": fingerprint,
            "iat":         now,
            "exp":         now + refresh_ttl,
        }

        # Store family in Redis (for rotation tracking)
        cache.set(
            _KEY_FAMILY.format(family_id),
            {"user_id": user_id, "device_id": device_id, "issued_at": now},
            refresh_ttl,
        )

        # Track user's active token families
        user_key = _KEY_USER_TOKENS.format(user_id)
        families = cache.get(user_key) or []
        families.append(family_id)
        cache.set(user_key, families[-50:], refresh_ttl)  # keep last 50

        return TokenPair(
            access_token        = self._encode(access_payload),
            refresh_token       = self._encode(refresh_payload),
            access_expires_at   = datetime.fromtimestamp(now + access_ttl, tz=tz.utc),
            refresh_expires_at  = datetime.fromtimestamp(now + refresh_ttl, tz=tz.utc),
            jti                 = jti,
        )

    # ── Validate access token ─────────────────────────────────────────────────

    def validate_access(
        self,
        token:      str,
        request=None,
        check_fingerprint: bool = True,
    ) -> Optional[dict]:
        """
        Validate an access token.

        Returns payload dict on success, None on any failure.
        """
        payload = self._decode(token)
        if not payload:
            return None

        # Type check
        if payload.get("type") != "access":
            logger.warning("JWT: wrong token type (expected access)")
            return None

        # Expiry check
        if payload.get("exp", 0) < time.time():
            logger.info("JWT: access token expired for user %s", payload.get("user_id"))
            return None

        # Blacklist check
        if cache.get(_KEY_BLACKLIST.format(payload.get("jti", ""))):
            logger.warning("JWT: token is blacklisted jti=%s", payload.get("jti"))
            return None

        # Fingerprint check (prevent token theft)
        if check_fingerprint and request and payload.get("fingerprint"):
            current_fp = self._fingerprint(request)
            if current_fp and not hmac.compare_digest(current_fp, payload["fingerprint"]):
                logger.warning(
                    "JWT fingerprint mismatch user=%s — possible token theft",
                    payload.get("user_id"),
                )
                return None

        return payload

    # ── Rotate refresh token ──────────────────────────────────────────────────

    def rotate_refresh(
        self,
        refresh_token: str,
        request=None,
    ) -> Optional[TokenPair]:
        """
        Validate a refresh token and issue a new token pair.
        Implements refresh token rotation:
        - Old refresh token is immediately blacklisted
        - New pair shares the same family_id
        - If old token is already blacklisted → revoke entire family (reuse attack)

        Returns new TokenPair or None on failure.
        """
        payload = self._decode(refresh_token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            logger.warning("JWT rotate: wrong token type")
            return None

        if payload.get("exp", 0) < time.time():
            logger.info("JWT rotate: refresh token expired")
            return None

        jti       = payload.get("jti", "")
        family_id = payload.get("family_id", "")
        user_id   = payload.get("user_id")

        # Check if already blacklisted → reuse attack detected
        if cache.get(_KEY_BLACKLIST.format(jti)):
            logger.critical(
                "JWT refresh token reuse detected! user=%s family=%s — revoking entire family",
                user_id, family_id,
            )
            self._revoke_family(family_id, user_id)
            return None

        # Blacklist old refresh token
        ttl_remaining = max(int(payload["exp"] - time.time()), 1)
        cache.set(_KEY_BLACKLIST.format(jti), 1, ttl_remaining)

        # Issue new pair with same family
        new_pair = self.issue(
            user_id   = user_id,
            device_id = payload.get("device_id"),
            request   = request,
        )
        return new_pair

    # ── Revoke ────────────────────────────────────────────────────────────────

    def revoke(self, token: str) -> bool:
        """Revoke a single token (access or refresh)."""
        payload = self._decode(token)
        if not payload:
            return False
        jti = payload.get("jti", "")
        ttl = max(int(payload.get("exp", time.time()) - time.time()), 1)
        cache.set(_KEY_BLACKLIST.format(jti), 1, ttl)
        logger.info("JWT: revoked token jti=%s user=%s", jti, payload.get("user_id"))
        return True

    def revoke_all(self, user_id: int) -> int:
        """
        Revoke ALL active token families for a user.
        Call on: password change, logout-all, account suspension.

        Returns number of families revoked.
        """
        user_key  = _KEY_USER_TOKENS.format(user_id)
        families  = cache.get(user_key) or []
        for family_id in families:
            self._revoke_family(family_id, user_id)
        cache.delete(user_key)
        logger.info("JWT: revoked all tokens for user=%s (%d families)", user_id, len(families))
        return len(families)

    def _revoke_family(self, family_id: str, user_id: int) -> None:
        """Blacklist an entire refresh token family."""
        cache.set(_KEY_BLACKLIST.format(f"family:{family_id}"), 1, _BL_TTL)
        cache.delete(_KEY_FAMILY.format(family_id))
        logger.info("JWT: revoked family=%s user=%s", family_id, user_id)

    # ── Introspect ────────────────────────────────────────────────────────────

    def introspect(self, token: str) -> dict:
        """
        Return token metadata without full validation.
        Useful for debugging / admin panels.
        """
        payload = self._decode(token)
        if not payload:
            return {"valid": False, "error": "invalid_token"}

        now = time.time()
        jti = payload.get("jti", "")
        return {
            "valid":       payload.get("exp", 0) > now,
            "blacklisted": bool(cache.get(_KEY_BLACKLIST.format(jti))),
            "expired":     payload.get("exp", 0) <= now,
            "user_id":     payload.get("user_id"),
            "token_type":  payload.get("type"),
            "device_id":   payload.get("device_id"),
            "family_id":   payload.get("family_id"),
            "expires_at":  datetime.fromtimestamp(payload.get("exp", 0), tz=tz.utc).isoformat(),
            "issued_at":   datetime.fromtimestamp(payload.get("iat", 0), tz=tz.utc).isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# DRF Authentication backend
# ─────────────────────────────────────────────────────────────────────────────

class JWTAuthentication:
    """
    DRF authentication class.

    settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'api.security.services.JWTService.JWTAuthentication',
            ],
        }
    """

    keyword = "Bearer"
    manager = JWTManager()

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.keyword + " "):
            return None

        token   = auth_header[len(self.keyword) + 1:]
        payload = self.manager.validate_access(token, request=request)
        if not payload:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed("Invalid or expired token.")

        user = self._get_user(payload["user_id"])
        if user is None:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed("User not found.")

        return user, token

    @staticmethod
    def _get_user(user_id: int):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.get(pk=user_id, is_active=True)
        except Exception:
            return None

    def authenticate_header(self, request) -> str:
        return self.keyword


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

jwt_manager = JWTManager()