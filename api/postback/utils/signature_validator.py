"""
utils/signature_validator.py

Defensive HMAC and signature verification utilities.

Security principles applied:
  • Constant-time comparison (hmac.compare_digest) everywhere.
  • Replay-attack prevention via timestamp + nonce.
  • Nonces stored in cache with TTL = tolerance window + buffer.
  • Algorithm is read from the NetworkPostbackConfig so keys can be
    rotated and algorithms changed without code deployment.
  • No secrets in logs or exceptions – only status booleans/codes.
"""
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Optional

from django.core.cache import cache

from ..constants import (
    CACHE_KEY_NONCE_USED,
    CACHE_TIMEOUT_NONCE,
    MAX_NONCE_LENGTH,
    SIGNATURE_TOLERANCE_SECONDS,
)
from ..exceptions import (
    InvalidSignatureException,
    NonceReusedException,
    SignatureExpiredException,
)

logger = logging.getLogger(__name__)

# Mapping from choice value → hashlib name
_ALGO_MAP = {
    "hmac_sha256": hashlib.sha256,
    "hmac_sha512": hashlib.sha512,
    "md5": hashlib.md5,
}


def _get_hash_fn(algorithm: str):
    fn = _ALGO_MAP.get(algorithm)
    if fn is None:
        raise ValueError(f"Unsupported signature algorithm: {algorithm!r}")
    return fn


def build_canonical_string(
    method: str,
    path: str,
    query_params: dict,
    body: bytes,
    timestamp: str,
    nonce: str,
) -> bytes:
    """
    Construct the canonical string that is signed.
    Format: METHOD\nPATH\nSORTED_QUERY\nBODY_HEX\nTIMESTAMP\nNONCE
    """
    sorted_query = urllib.parse.urlencode(sorted(query_params.items()))
    body_hex = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([
        method.upper(),
        path,
        sorted_query,
        body_hex,
        timestamp,
        nonce,
    ])
    return canonical.encode("utf-8")


def compute_signature(
    secret: str,
    canonical_bytes: bytes,
    algorithm: str = "hmac_sha256",
) -> str:
    """Compute HMAC signature over canonical bytes."""
    hash_fn = _get_hash_fn(algorithm)
    mac = hmac.new(secret.encode("utf-8"), canonical_bytes, hash_fn)
    return mac.hexdigest()


def verify_signature(
    *,
    provided_signature: str,
    secret: str,
    canonical_bytes: bytes,
    algorithm: str = "hmac_sha256",
) -> bool:
    """
    Constant-time signature comparison.
    Returns True if valid, False if not.
    Never raises – callers decide how to handle False.
    """
    if algorithm == "none":
        return True  # IP-only auth, no signature required
    try:
        expected = compute_signature(secret, canonical_bytes, algorithm)
        return hmac.compare_digest(
            expected.encode("utf-8"),
            provided_signature.encode("utf-8"),
        )
    except Exception as exc:
        logger.debug("Signature verification internal error: %s", type(exc).__name__)
        return False


def validate_timestamp(timestamp_str: str, tolerance: int = SIGNATURE_TOLERANCE_SECONDS) -> None:
    """
    Validate that the provided timestamp is within the tolerance window.
    Raises SignatureExpiredException if outside window.
    """
    try:
        ts = int(timestamp_str)
    except (TypeError, ValueError):
        raise InvalidSignatureException(detail="Timestamp header is not a valid integer.")

    now = int(time.time())
    drift = abs(now - ts)
    if drift > tolerance:
        raise SignatureExpiredException(
            detail=(
                f"Timestamp drift of {drift}s exceeds tolerance of {tolerance}s. "
                "Ensure server clocks are synchronised."
            )
        )


def validate_and_consume_nonce(nonce: str, network_id: str) -> None:
    """
    Check that the nonce has not been used before for this network,
    then mark it as used in the cache.
    Raises NonceReusedException if already seen.

    The nonce is namespaced per-network to allow reuse across networks.
    """
    if not nonce:
        raise InvalidSignatureException(detail="Nonce header is required but missing.")
    if len(nonce) > MAX_NONCE_LENGTH:
        raise InvalidSignatureException(
            detail=f"Nonce exceeds maximum length of {MAX_NONCE_LENGTH} characters."
        )

    cache_key = CACHE_KEY_NONCE_USED.format(nonce=f"{network_id}:{nonce}")
    if cache.get(cache_key) is not None:
        raise NonceReusedException()

    cache.set(cache_key, 1, timeout=CACHE_TIMEOUT_NONCE)


def validate_full_request(
    *,
    provided_signature: str,
    timestamp_str: str,
    nonce: str,
    secret: str,
    network_id: str,
    algorithm: str,
    method: str,
    path: str,
    query_params: dict,
    body: bytes,
) -> None:
    """
    Full defensive validation pipeline:
    1. Timestamp within tolerance window.
    2. Nonce not yet seen (replay prevention).
    3. HMAC signature matches.

    Raises the appropriate PostbackException on failure.
    Logs failure reasons at WARNING level WITHOUT including the secret.
    """
    # Step 1 – Timestamp
    validate_timestamp(timestamp_str)

    # Step 2 – Nonce
    validate_and_consume_nonce(nonce, network_id)

    # Step 3 – Signature
    canonical = build_canonical_string(
        method=method,
        path=path,
        query_params=query_params,
        body=body,
        timestamp=timestamp_str,
        nonce=nonce,
    )
    valid = verify_signature(
        provided_signature=provided_signature,
        secret=secret,
        canonical_bytes=canonical,
        algorithm=algorithm,
    )
    if not valid:
        logger.warning(
            "Invalid postback signature for network_id=%s algorithm=%s path=%s",
            network_id, algorithm, path,
        )
        raise InvalidSignatureException()
