"""
validation_engines/token_validator.py
───────────────────────────────────────
API token and nonce validation.
"""
from __future__ import annotations
import secrets
import logging
from django.core.cache import cache
from ..exceptions import InvalidSignatureException, NonceReusedException
from ..constants import CACHE_KEY_NONCE_USED, CACHE_TTL_NONCE

logger = logging.getLogger(__name__)


class TokenValidator:

    def validate_nonce(self, nonce: str, network_id: str) -> None:
        """Ensure nonce has not been used before (replay attack prevention)."""
        if not nonce:
            return
        cache_key = CACHE_KEY_NONCE_USED.format(nonce=f"{network_id}:{nonce}")
        if cache.get(cache_key):
            raise NonceReusedException(f"Nonce '{nonce[:16]}...' already used.")
        cache.set(cache_key, "1", timeout=CACHE_TTL_NONCE)

    def validate_api_key(self, provided_key: str, network_api_key: str) -> bool:
        """Constant-time API key comparison."""
        if not provided_key or not network_api_key:
            return False
        return secrets.compare_digest(provided_key.encode(), network_api_key.encode())

    def generate_nonce(self) -> str:
        return secrets.token_hex(16)


token_validator = TokenValidator()
