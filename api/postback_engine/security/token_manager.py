"""
security/token_manager.py
───────────────────────────
Manages short-lived tokens for postback authentication.
Tokens are used as an alternative to HMAC signatures for simple networks.
"""
from __future__ import annotations
import hashlib
import secrets
import time
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)
_TOKEN_TTL = 300  # 5 minutes
_KEY = "pe:token:{token_hash}"


class TokenManager:

    def generate(self, network_key: str, metadata: dict = None) -> str:
        """Generate a short-lived authentication token for a network."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()[:32]
        cache_key = _KEY.format(token_hash=token_hash)
        cache.set(cache_key, {
            "network_key": network_key,
            "created_at": time.time(),
            **(metadata or {}),
        }, timeout=_TOKEN_TTL)
        return raw_token

    def validate(self, token: str, expected_network_key: str = None) -> dict:
        """
        Validate a token and return its metadata.
        Returns {} if token is invalid or expired.
        """
        if not token:
            return {}
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        cache_key = _KEY.format(token_hash=token_hash)
        data = cache.get(cache_key)
        if not data:
            return {}
        if expected_network_key and data.get("network_key") != expected_network_key:
            return {}
        return data

    def revoke(self, token: str) -> None:
        """Immediately invalidate a token."""
        if not token:
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        cache.delete(_KEY.format(token_hash=token_hash))

    def is_valid(self, token: str, network_key: str = None) -> bool:
        return bool(self.validate(token, network_key))


token_manager = TokenManager()
