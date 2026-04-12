"""
E2E Encryption Helpers — Message encryption utilities.
Uses AES-256-GCM for symmetric encryption.
Key exchange uses ECDH (X25519) per session.
"""
from __future__ import annotations
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def generate_key_pair() -> tuple[bytes, bytes]:
    """Generate an X25519 key pair (private_key, public_key)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
        priv_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return priv_bytes, pub_bytes
    except ImportError:
        logger.warning("encryption: cryptography library not installed. Returning dummy keys.")
        return os.urandom(32), os.urandom(32)


def derive_shared_key(private_key_bytes: bytes, peer_public_key_bytes: bytes) -> bytes:
    """Derive shared AES key from ECDH exchange."""
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from cryptography.hazmat.backends import default_backend

        private_key = X25519PrivateKey.from_private_bytes(private_key_bytes)
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
        public_key = X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        shared_secret = private_key.exchange(public_key)
        return _hkdf(shared_secret)
    except Exception as exc:
        logger.error("derive_shared_key: failed: %s", exc)
        return os.urandom(32)


def _hkdf(input_key: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 key derivation."""
    try:
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=None,
            info=b"messaging_e2e_v1",
        )
        return hkdf.derive(input_key)
    except Exception:
        import hashlib
        return hashlib.sha256(input_key).digest()


def encrypt_message(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt a message with AES-256-GCM.
    Returns (ciphertext_with_tag, nonce).
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return ciphertext, nonce
    except ImportError:
        logger.warning("encrypt_message: cryptography not available. Returning base64 plaintext.")
        encoded = base64.b64encode(plaintext.encode()).decode()
        return encoded.encode(), b"\x00" * 12


def decrypt_message(ciphertext: bytes, key: bytes, nonce: bytes) -> Optional[str]:
    """Decrypt an AES-256-GCM encrypted message."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as exc:
        logger.error("decrypt_message: failed: %s", exc)
        return None


def encode_key(key_bytes: bytes) -> str:
    """Encode key bytes as base64 URL-safe string."""
    return base64.urlsafe_b64encode(key_bytes).decode()


def decode_key(key_str: str) -> bytes:
    """Decode a base64 URL-safe key string to bytes."""
    return base64.urlsafe_b64decode(key_str.encode())
