"""
utils/encryption.py — Symmetric AES-256-GCM helpers + X25519 key pair.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RELATIONSHIP TO e2e_encryption.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This file provides LOW-LEVEL primitives:
  - generate_key_pair()    — X25519 key pair
  - derive_shared_key()    — ECDH → HKDF shared key
  - encrypt_message()      — AES-256-GCM encrypt
  - decrypt_message()      — AES-256-GCM decrypt
  - encode_key / decode_key — base64url helpers

utils/e2e_encryption.py builds a FULL SIGNAL PROTOCOL on top of these
primitives (X3DH + Double Ratchet). Use e2e_encryption.py for end-to-end
encrypted chat. Use this file for:
  - Encrypting individual fields at rest (e.g. ChatMessage.content at DB level)
  - One-shot encrypt/decrypt without ratchet state
  - Webhook payload signing helpers
  - Any code that needs a simple "encrypt this string, decrypt it later" API

Both files are intentionally kept separate:
  - This file has NO dependencies on e2e_encryption.py
  - e2e_encryption.py has NO dependencies on this file
  - Either can be used independently without pulling in the other
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage example (at-rest field encryption):

    from api.messaging.utils.encryption import generate_key_pair, derive_shared_key
    from api.messaging.utils.encryption import encrypt_message, decrypt_message

    # Server generates a per-chat key pair
    priv, pub = generate_key_pair()

    # Encrypt content before saving to DB
    ciphertext, nonce = encrypt_message(plaintext="Hello", key=shared_key)

    # Decrypt when reading from DB
    text = decrypt_message(ciphertext, key=shared_key, nonce=nonce)
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ── Key Generation ────────────────────────────────────────────────────────────

def generate_key_pair() -> tuple[bytes, bytes]:
    """
    Generate an X25519 key pair.

    Returns:
        (private_key_bytes, public_key_bytes) — each 32 bytes raw.

    Falls back to os.urandom(32) if the cryptography package is not installed
    (so tests / lightweight environments still import without error, but crypto
    operations will not be secure — a warning is logged).
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption,
        )
        private_key = X25519PrivateKey.generate()
        public_key  = private_key.public_key()
        priv_bytes  = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub_bytes   = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return priv_bytes, pub_bytes
    except ImportError:
        logger.warning(
            "encryption.generate_key_pair: 'cryptography' library not installed. "
            "Returning random bytes — NOT suitable for production. "
            "Run: pip install cryptography"
        )
        return os.urandom(32), os.urandom(32)
    except Exception as exc:
        logger.error("encryption.generate_key_pair: %s", exc)
        return os.urandom(32), os.urandom(32)


def derive_shared_key(private_key_bytes: bytes, peer_public_key_bytes: bytes) -> bytes:
    """
    Derive a 32-byte AES key via X25519 ECDH + HKDF-SHA256.

    Args:
        private_key_bytes:     Raw 32-byte X25519 private key.
        peer_public_key_bytes: Raw 32-byte X25519 public key from the peer.

    Returns:
        32-byte shared AES key derived via HKDF-SHA256.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey,
        )
        private_key = X25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key  = X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        shared_secret = private_key.exchange(public_key)
        return _hkdf(shared_secret)
    except ImportError:
        logger.warning(
            "encryption.derive_shared_key: 'cryptography' library not installed. "
            "Returning random bytes — NOT secure."
        )
        return os.urandom(32)
    except Exception as exc:
        logger.error("encryption.derive_shared_key: %s", exc)
        return os.urandom(32)


def _hkdf(input_key: bytes, length: int = 32) -> bytes:
    """
    HKDF-SHA256 key derivation.

    Args:
        input_key: Raw key material bytes.
        length:    Output length in bytes (default 32).

    Returns:
        Derived key bytes of the requested length.
    """
    try:
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=None,
            info=b"messaging_encryption_v1",
        )
        return hkdf.derive(input_key)
    except ImportError:
        import hashlib
        return hashlib.sha256(input_key).digest()[:length]
    except Exception as exc:
        logger.error("encryption._hkdf: %s", exc)
        import hashlib
        return hashlib.sha256(input_key).digest()[:length]


# ── AES-256-GCM Encrypt / Decrypt ────────────────────────────────────────────

def encrypt_message(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt a plaintext string with AES-256-GCM.

    Args:
        plaintext: UTF-8 string to encrypt.
        key:       32-byte AES key (from derive_shared_key or random).

    Returns:
        (ciphertext_with_auth_tag, nonce)
        Both values must be stored and passed to decrypt_message().
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm    = AESGCM(key)
        nonce     = os.urandom(12)   # 96-bit nonce, GCM standard
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return ciphertext, nonce
    except ImportError:
        logger.warning(
            "encryption.encrypt_message: 'cryptography' not available. "
            "Returning base64-encoded plaintext — NOT encrypted."
        )
        encoded = base64.b64encode(plaintext.encode("utf-8"))
        return encoded, b"\x00" * 12
    except Exception as exc:
        # Part 6 audit fix: this used to fall back to the same silent,
        # unencrypted-plaintext-as-base64 path as the "cryptography not
        # installed" case above - but this branch catches everything
        # else too, e.g. AESGCM(key) rejecting a key that isn't exactly
        # 16/24/32 bytes. That's a caller bug, not "the library isn't
        # installed", and this function is documented as encrypting
        # ChatMessage.content at rest - silently storing plaintext
        # labeled as ciphertext on any crypto error is a worse outcome
        # than the caller getting an exception it has to handle. Fails
        # closed here; the ImportError branch above (intentional,
        # environment-level degradation) is unchanged.
        logger.error("encryption.encrypt_message: %s", exc)
        raise


def decrypt_message(ciphertext: bytes, key: bytes, nonce: bytes) -> Optional[str]:
    """
    Decrypt an AES-256-GCM encrypted message.

    Args:
        ciphertext: Ciphertext bytes including auth tag (from encrypt_message).
        key:        32-byte AES key used during encryption.
        nonce:      12-byte nonce used during encryption.

    Returns:
        Decrypted UTF-8 string, or None if decryption fails.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm    = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except ImportError:
        # Fallback: ciphertext is actually base64 plaintext from encrypt_message fallback
        try:
            return base64.b64decode(ciphertext).decode("utf-8")
        except Exception:
            return None
    except Exception as exc:
        logger.error("encryption.decrypt_message: decryption failed: %s", exc)
        return None


# ── Key Encoding Helpers ──────────────────────────────────────────────────────

def encode_key(key_bytes: bytes) -> str:
    """
    Encode raw key bytes as a URL-safe base64 string.

    Suitable for JSON transport, URL params, and DB storage.
    """
    return base64.urlsafe_b64encode(key_bytes).decode("ascii")


def decode_key(key_str: str) -> bytes:
    """
    Decode a URL-safe base64 key string back to raw bytes.

    Raises:
        binascii.Error: if the string is not valid base64.
    """
    return base64.urlsafe_b64decode(key_str.encode("ascii"))


# ── Convenience: encrypt/decrypt with base64-encoded output ──────────────────

def encrypt_to_b64(plaintext: str, key: bytes) -> dict:
    """
    Encrypt plaintext and return a JSON-serializable dict.

    Returns:
        {"ciphertext": "<base64>", "nonce": "<base64>"}
    """
    ciphertext, nonce = encrypt_message(plaintext, key)
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce":      base64.b64encode(nonce).decode(),
    }


def decrypt_from_b64(payload: dict, key: bytes) -> Optional[str]:
    """
    Decrypt a dict produced by encrypt_to_b64().

    Args:
        payload: {"ciphertext": "<base64>", "nonce": "<base64>"}
        key:     32-byte AES key.

    Returns:
        Decrypted string or None on failure.
    """
    try:
        ciphertext = base64.b64decode(payload["ciphertext"])
        nonce      = base64.b64decode(payload["nonce"])
        return decrypt_message(ciphertext, key, nonce)
    except Exception as exc:
        logger.error("encryption.decrypt_from_b64: %s", exc)
        return None
