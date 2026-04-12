"""
security/signature_generator.py – HMAC signature generation & verification.
"""
import hashlib
import hmac
import secrets
import urllib.parse
from typing import Tuple

from ..enums import SignatureAlgorithm


ALGORITHM_MAP = {
    SignatureAlgorithm.HMAC_SHA256: hashlib.sha256,
    SignatureAlgorithm.HMAC_SHA512: hashlib.sha512,
    SignatureAlgorithm.HMAC_MD5:    hashlib.md5,
    SignatureAlgorithm.MD5:         hashlib.md5,
}


def generate_hmac(
    secret: str,
    message: str,
    algorithm: str = SignatureAlgorithm.HMAC_SHA256,
) -> str:
    """Generate an HMAC hex digest."""
    algo = ALGORITHM_MAP.get(algorithm, hashlib.sha256)
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        algo,
    ).hexdigest()


def verify_hmac(
    secret: str,
    message: str,
    provided: str,
    algorithm: str = SignatureAlgorithm.HMAC_SHA256,
) -> bool:
    """Constant-time HMAC verification."""
    expected = generate_hmac(secret, message, algorithm)
    return hmac.compare_digest(
        expected.encode("utf-8"),
        provided.encode("utf-8"),
    )


def build_postback_signature_message(
    payload: dict,
    timestamp: str = "",
    nonce: str = "",
) -> str:
    """
    Build the canonical message string for postback signing.
    Payload params are sorted alphabetically for determinism.
    """
    sorted_params = sorted(payload.items())
    query = urllib.parse.urlencode(sorted_params)
    parts = [query]
    if timestamp:
        parts.append(f"ts={timestamp}")
    if nonce:
        parts.append(f"nonce={nonce}")
    return "&".join(parts)


def generate_nonce(length: int = 32) -> str:
    """Generate a cryptographically secure random nonce."""
    return secrets.token_hex(length)


def generate_webhook_signature(secret: str, body: str) -> str:
    """Generate a webhook payload signature."""
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_api_key(prefix: str = "pe") -> str:
    """Generate a new API key with a readable prefix."""
    token = secrets.token_urlsafe(32)
    return f"{prefix}_{token}"


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Return a masked version of a secret for display."""
    if len(secret) <= visible_chars:
        return "***"
    return secret[:visible_chars] + "*" * (len(secret) - visible_chars)
