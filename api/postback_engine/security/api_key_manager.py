"""
security/api_key_manager.py
─────────────────────────────
Manages API keys for network authentication.
API keys are an alternative auth method for networks that don't support HMAC.
"""
from __future__ import annotations
import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)


class APIKeyManager:

    def generate(self, prefix: str = "pe") -> str:
        """
        Generate a cryptographically secure API key.
        Format: pe_<64-char-hex>
        """
        token = secrets.token_hex(32)
        return f"{prefix}_{token}"

    def hash_for_storage(self, api_key: str) -> str:
        """
        Hash an API key before storing in DB (like password hashing).
        Store the hash, not the plaintext.
        """
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def verify(self, provided_key: str, stored_hash: str) -> bool:
        """Constant-time comparison of provided key against stored hash."""
        if not provided_key or not stored_hash:
            return False
        expected_hash = self.hash_for_storage(provided_key)
        return secrets.compare_digest(expected_hash, stored_hash)

    def mask(self, api_key: str, visible_chars: int = 8) -> str:
        """Return masked version for display (e.g. pe_abc12345...)."""
        if not api_key or len(api_key) <= visible_chars:
            return "***"
        return api_key[:visible_chars] + "..." + api_key[-4:]

    def validate_format(self, api_key: str) -> bool:
        """Check API key has the expected format."""
        if not api_key:
            return False
        parts = api_key.split("_", 1)
        return len(parts) == 2 and len(parts[1]) >= 32


api_key_manager = APIKeyManager()
