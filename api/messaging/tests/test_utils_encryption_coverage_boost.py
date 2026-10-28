"""
test_utils_encryption_coverage_boost.py
=========================================
Real-execution coverage for messaging/utils/encryption.py.

The 'cryptography' package is actually installed in this environment, so
the ImportError fallback branches (meant for environments where it is
missing) can't be reached naturally. Those are covered by selectively
making `import cryptography...` raise via a patched __import__ that only
intercepts cryptography-prefixed module names (everything else - hashlib,
base64, etc. - imports normally, including inside the fallback code paths
themselves). Generic-exception branches are triggered with real invalid
inputs (wrong-length keys, tampered ciphertext) wherever the cryptography
library naturally raises for them, rather than mocked, per this project's
preference for dynamic execution over deep mocking.
"""
from __future__ import annotations

import builtins
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from api.messaging.utils import encryption as enc

pytestmark = pytest.mark.django_db(transaction=False)


@contextmanager
def _no_cryptography():
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cryptography" or name.startswith("cryptography."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


# ---------------------------------------------------------------------------
# generate_key_pair
# ---------------------------------------------------------------------------

class TestGenerateKeyPair:
    def test_happy_path_returns_32_byte_keys(self):
        priv, pub = enc.generate_key_pair()
        assert isinstance(priv, bytes) and len(priv) == 32
        assert isinstance(pub, bytes) and len(pub) == 32
        assert priv != pub

    def test_import_error_falls_back_to_random_bytes(self):
        with _no_cryptography():
            priv, pub = enc.generate_key_pair()
        assert len(priv) == 32
        assert len(pub) == 32

    def test_generic_exception_falls_back_to_random_bytes(self):
        with patch(
            "cryptography.hazmat.primitives.asymmetric.x25519.X25519PrivateKey.generate",
            side_effect=RuntimeError("boom"),
        ):
            priv, pub = enc.generate_key_pair()
        assert len(priv) == 32
        assert len(pub) == 32


# ---------------------------------------------------------------------------
# derive_shared_key / _hkdf
# ---------------------------------------------------------------------------

class TestDeriveSharedKey:
    def test_happy_path_ecdh_roundtrip_produces_matching_key(self):
        priv_a, pub_a = enc.generate_key_pair()
        priv_b, pub_b = enc.generate_key_pair()
        key_a = enc.derive_shared_key(priv_a, pub_b)
        key_b = enc.derive_shared_key(priv_b, pub_a)
        assert key_a == key_b
        assert len(key_a) == 32

    def test_import_error_falls_back_to_random_bytes(self):
        with _no_cryptography():
            key = enc.derive_shared_key(b"x" * 32, b"y" * 32)
        assert len(key) == 32

    def test_generic_exception_on_bad_key_length_falls_back(self):
        # X25519PrivateKey.from_private_bytes requires exactly 32 bytes;
        # a short key raises a real ValueError from the cryptography lib.
        key = enc.derive_shared_key(b"too-short", b"y" * 32)
        assert len(key) == 32


class TestHkdf:
    def test_happy_path_deterministic_length(self):
        derived = enc._hkdf(b"some-shared-secret", length=16)
        assert len(derived) == 16
        derived_again = enc._hkdf(b"some-shared-secret", length=16)
        assert derived == derived_again

    def test_default_length_is_32(self):
        assert len(enc._hkdf(b"secret")) == 32

    def test_import_error_falls_back_to_sha256(self):
        import hashlib

        with _no_cryptography():
            derived = enc._hkdf(b"secret", length=16)
        assert derived == hashlib.sha256(b"secret").digest()[:16]

    def test_generic_exception_falls_back_to_sha256(self):
        import hashlib

        with patch(
            "cryptography.hazmat.primitives.kdf.hkdf.HKDF.derive",
            side_effect=RuntimeError("boom"),
        ):
            derived = enc._hkdf(b"secret", length=16)
        assert derived == hashlib.sha256(b"secret").digest()[:16]


# ---------------------------------------------------------------------------
# encrypt_message / decrypt_message
# ---------------------------------------------------------------------------

class TestEncryptDecryptMessage:
    def test_roundtrip_happy_path(self):
        key = b"k" * 32
        ciphertext, nonce = enc.encrypt_message("hello world", key)
        assert ciphertext != b"hello world"
        assert len(nonce) == 12
        plaintext = enc.decrypt_message(ciphertext, key, nonce)
        assert plaintext == "hello world"

    def test_encrypt_import_error_returns_base64_plaintext(self):
        with _no_cryptography():
            ciphertext, nonce = enc.encrypt_message("hello", b"k" * 32)
        assert nonce == b"\x00" * 12
        import base64 as b64
        assert b64.b64decode(ciphertext).decode("utf-8") == "hello"

    def test_encrypt_generic_exception_on_bad_key_length_raises(self):
        """
        Regression test (Part 6 audit): AESGCM requires a 16/24/32-byte
        key; an invalid length raises a real ValueError from the
        cryptography library. This used to be silently swallowed and
        fell back to the SAME unencrypted-base64-plaintext path as the
        "cryptography not installed" case - meaning a caller bug (wrong
        key length) would silently store plaintext labeled as ciphertext
        in the DB (this function encrypts ChatMessage.content at rest).
        Now fails closed - the caller has to handle it, rather than the
        error disappearing into a log line while bad data gets written.
        """
        with pytest.raises(ValueError):
            enc.encrypt_message("hello", b"short-key")

    def test_decrypt_generic_exception_on_tampered_ciphertext_returns_none(self):
        key = b"k" * 32
        ciphertext, nonce = enc.encrypt_message("hello world", key)
        tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
        result = enc.decrypt_message(tampered, key, nonce)
        assert result is None

    def test_decrypt_import_error_decodes_base64_fallback_successfully(self):
        with _no_cryptography():
            ciphertext, nonce = enc.encrypt_message("round trip", b"k" * 32)
            plaintext = enc.decrypt_message(ciphertext, b"k" * 32, nonce)
        assert plaintext == "round trip"

    def test_decrypt_import_error_with_invalid_base64_returns_none(self):
        with _no_cryptography():
            result = enc.decrypt_message(b"not-valid-base64!!!", b"k" * 32, b"\x00" * 12)
        assert result is None


# ---------------------------------------------------------------------------
# encode_key / decode_key
# ---------------------------------------------------------------------------

class TestEncodeDecodeKey:
    def test_roundtrip(self):
        raw = b"\x01\x02\x03" * 10
        encoded = enc.encode_key(raw)
        assert isinstance(encoded, str)
        assert enc.decode_key(encoded) == raw


# ---------------------------------------------------------------------------
# encrypt_to_b64 / decrypt_from_b64
# ---------------------------------------------------------------------------

class TestEncryptDecryptToFromB64:
    def test_roundtrip(self):
        key = b"k" * 32
        payload = enc.encrypt_to_b64("hi there", key)
        assert set(payload.keys()) == {"ciphertext", "nonce"}
        assert isinstance(payload["ciphertext"], str)
        assert isinstance(payload["nonce"], str)
        result = enc.decrypt_from_b64(payload, key)
        assert result == "hi there"

    def test_decrypt_from_b64_returns_none_on_malformed_payload(self):
        result = enc.decrypt_from_b64({"ciphertext": "not base64 !!"}, b"k" * 32)
        assert result is None
