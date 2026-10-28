"""
test_utils_encryption.py
=========================
Full coverage for messaging/utils/encryption.py
Functions: generate_key_pair, derive_shared_key, _hkdf,
           encrypt_message, decrypt_message, encode_key, decode_key
Place in: messaging/tests/test_utils_encryption.py
"""
from __future__ import annotations
import os
from django.test import TestCase
from ..utils.encryption import (
    generate_key_pair,
    derive_shared_key,
    _hkdf,
    encrypt_message,
    decrypt_message,
    encode_key,
    decode_key,
)


class TestGenerateKeyPair(TestCase):
    def test_returns_two_bytes_objects(self):
        priv, pub = generate_key_pair()
        self.assertIsInstance(priv, bytes)
        self.assertIsInstance(pub, bytes)

    def test_keys_are_32_bytes(self):
        priv, pub = generate_key_pair()
        self.assertEqual(len(priv), 32)
        self.assertEqual(len(pub), 32)

    def test_private_and_public_differ(self):
        priv, pub = generate_key_pair()
        self.assertNotEqual(priv, pub)

    def test_each_call_produces_unique_pair(self):
        priv1, pub1 = generate_key_pair()
        priv2, pub2 = generate_key_pair()
        self.assertNotEqual(priv1, priv2)
        self.assertNotEqual(pub1, pub2)

    def test_called_many_times_all_unique(self):
        public_keys = set()
        for _ in range(50):
            _, pub = generate_key_pair()
            public_keys.add(pub)
        self.assertEqual(len(public_keys), 50)


class TestDeriveSharedKey(TestCase):
    def test_returns_32_bytes(self):
        priv, pub = generate_key_pair()
        shared = derive_shared_key(priv, pub)
        self.assertIsInstance(shared, bytes)
        self.assertEqual(len(shared), 32)

    def test_ecdh_shared_secret_is_symmetric(self):
        """Alice and Bob compute the same shared key."""
        alice_priv, alice_pub = generate_key_pair()
        bob_priv, bob_pub = generate_key_pair()
        # Alice uses her private key + Bob's public key
        shared_alice = derive_shared_key(alice_priv, bob_pub)
        # Bob uses his private key + Alice's public key
        shared_bob = derive_shared_key(bob_priv, alice_pub)
        # Both should derive the same shared secret
        self.assertEqual(shared_alice, shared_bob)

    def test_different_peers_produce_different_secrets(self):
        alice_priv, alice_pub = generate_key_pair()
        bob_priv, bob_pub = generate_key_pair()
        charlie_priv, charlie_pub = generate_key_pair()
        s1 = derive_shared_key(alice_priv, bob_pub)
        s2 = derive_shared_key(alice_priv, charlie_pub)
        self.assertNotEqual(s1, s2)

    def test_returns_32_bytes_on_invalid_keys(self):
        """Should not raise — returns random bytes as fallback."""
        result = derive_shared_key(os.urandom(32), os.urandom(32))
        self.assertEqual(len(result), 32)


class TestHkdf(TestCase):
    def test_returns_bytes_of_correct_length(self):
        result = _hkdf(os.urandom(32), length=32)
        self.assertEqual(len(result), 32)

    def test_custom_length(self):
        result = _hkdf(os.urandom(32), length=16)
        self.assertEqual(len(result), 16)

    def test_deterministic(self):
        ikm = os.urandom(32)
        r1 = _hkdf(ikm)
        r2 = _hkdf(ikm)
        self.assertEqual(r1, r2)

    def test_different_inputs_produce_different_output(self):
        r1 = _hkdf(os.urandom(32))
        r2 = _hkdf(os.urandom(32))
        self.assertNotEqual(r1, r2)


class TestEncryptMessage(TestCase):
    def test_returns_ciphertext_and_nonce(self):
        key = os.urandom(32)
        ct, nonce = encrypt_message("Hello, World!", key)
        self.assertIsInstance(ct, bytes)
        self.assertIsInstance(nonce, bytes)

    def test_ciphertext_is_not_plaintext(self):
        key = os.urandom(32)
        plaintext = "This is a secret message"
        ct, nonce = encrypt_message(plaintext, key)
        self.assertNotEqual(ct, plaintext.encode())

    def test_nonce_is_12_bytes(self):
        key = os.urandom(32)
        _, nonce = encrypt_message("test", key)
        self.assertEqual(len(nonce), 12)

    def test_different_nonce_each_call(self):
        key = os.urandom(32)
        _, n1 = encrypt_message("same message", key)
        _, n2 = encrypt_message("same message", key)
        self.assertNotEqual(n1, n2)

    def test_empty_string_encrypted(self):
        key = os.urandom(32)
        ct, nonce = encrypt_message("", key)
        self.assertIsInstance(ct, bytes)

    def test_unicode_message(self):
        key = os.urandom(32)
        ct, nonce = encrypt_message("হ্যালো বিশ্ব 🌍", key)
        self.assertIsInstance(ct, bytes)


class TestDecryptMessage(TestCase):
    def test_decrypts_correctly(self):
        key = os.urandom(32)
        plaintext = "Secret message for testing"
        ct, nonce = encrypt_message(plaintext, key)
        recovered = decrypt_message(ct, key, nonce)
        self.assertEqual(recovered, plaintext)

    def test_returns_none_with_wrong_key(self):
        key = os.urandom(32)
        ct, nonce = encrypt_message("secret", key)
        wrong_key = os.urandom(32)
        result = decrypt_message(ct, wrong_key, nonce)
        self.assertIsNone(result)

    def test_returns_none_with_wrong_nonce(self):
        key = os.urandom(32)
        ct, _ = encrypt_message("secret", key)
        wrong_nonce = os.urandom(12)
        result = decrypt_message(ct, key, wrong_nonce)
        self.assertIsNone(result)

    def test_returns_none_with_corrupted_ciphertext(self):
        key = os.urandom(32)
        ct, nonce = encrypt_message("secret", key)
        # Corrupt the ciphertext
        corrupted = bytes([ct[0] ^ 0xFF]) + ct[1:]
        result = decrypt_message(corrupted, key, nonce)
        self.assertIsNone(result)

    def test_roundtrip_unicode(self):
        key = os.urandom(32)
        original = "বাংলা বার্তা ✉️"
        ct, nonce = encrypt_message(original, key)
        recovered = decrypt_message(ct, key, nonce)
        self.assertEqual(recovered, original)

    def test_roundtrip_long_message(self):
        key = os.urandom(32)
        original = "A" * 10000
        ct, nonce = encrypt_message(original, key)
        recovered = decrypt_message(ct, key, nonce)
        self.assertEqual(recovered, original)


class TestEncodeDecodeKey(TestCase):
    def test_encode_returns_string(self):
        key = os.urandom(32)
        encoded = encode_key(key)
        self.assertIsInstance(encoded, str)

    def test_decode_recovers_original_bytes(self):
        key = os.urandom(32)
        encoded = encode_key(key)
        decoded = decode_key(encoded)
        self.assertEqual(key, decoded)

    def test_url_safe_no_plus_or_slash(self):
        for _ in range(100):
            key = os.urandom(32)
            encoded = encode_key(key)
            self.assertNotIn("+", encoded)
            self.assertNotIn("/", encoded)

    def test_empty_bytes_encodeable(self):
        encoded = encode_key(b"")
        decoded = decode_key(encoded)
        self.assertEqual(decoded, b"")

    def test_roundtrip_all_byte_values(self):
        key = bytes(range(32))
        self.assertEqual(key, decode_key(encode_key(key)))
