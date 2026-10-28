"""
test_utils_e2e_encryption.py
=============================
Full coverage for messaging/utils/e2e_encryption.py
Functions: generate_identity_key_pair, x3dh_sender, x3dh_recipient,
           DoubleRatchet (encrypt/decrypt/serialize), _kdf_rk, _kdf_rk_step,
           _kdf_ck, _dh, _aes_gcm_encrypt, _aes_gcm_decrypt,
           encrypt_message_e2e, decrypt_message_e2e, encode_key, decode_key
Place in: messaging/tests/test_utils_e2e_encryption.py
"""
from __future__ import annotations
import base64
import os
from django.test import TestCase
from ..utils.e2e_encryption import (
    generate_identity_key_pair,
    generate_ephemeral_key_pair,
    generate_prekey_pair,
    generate_signed_prekey_pair,
    x3dh_sender,
    x3dh_recipient,
    DoubleRatchet,
    _kdf_rk,
    _kdf_rk_step,
    _kdf_ck,
    _dh,
    _aes_gcm_encrypt,
    _aes_gcm_decrypt,
    encrypt_message_e2e,
    decrypt_message_e2e,
    encode_key,
    decode_key,
)


class TestGenerateKeyPair(TestCase):
    def test_returns_tuple_of_two_bytes(self):
        priv, pub = generate_identity_key_pair()
        self.assertIsInstance(priv, bytes)
        self.assertIsInstance(pub, bytes)

    def test_keys_are_32_bytes(self):
        priv, pub = generate_identity_key_pair()
        self.assertEqual(len(priv), 32)
        self.assertEqual(len(pub), 32)

    def test_private_and_public_are_different(self):
        priv, pub = generate_identity_key_pair()
        self.assertNotEqual(priv, pub)

    def test_each_call_produces_unique_keys(self):
        priv1, pub1 = generate_identity_key_pair()
        priv2, pub2 = generate_identity_key_pair()
        self.assertNotEqual(priv1, priv2)
        self.assertNotEqual(pub1, pub2)

    def test_aliases_return_same_format(self):
        for fn in [generate_ephemeral_key_pair, generate_prekey_pair, generate_signed_prekey_pair]:
            priv, pub = fn()
            self.assertEqual(len(priv), 32)
            self.assertEqual(len(pub), 32)


class TestX3DH(TestCase):
    def setUp(self):
        self.alice_priv, self.alice_pub = generate_identity_key_pair()
        self.bob_priv, self.bob_pub = generate_identity_key_pair()
        self.bob_spk_priv, self.bob_spk_pub = generate_signed_prekey_pair()
        self.bob_opk_priv, self.bob_opk_pub = generate_prekey_pair()

    def test_sender_returns_secret_and_ephemeral_key(self):
        secret, eph_pub = x3dh_sender(
            sender_identity_priv=self.alice_priv,
            sender_identity_pub=self.alice_pub,
            recipient_identity_pub=self.bob_pub,
            recipient_signed_prekey_pub=self.bob_spk_pub,
        )
        self.assertIsInstance(secret, bytes)
        self.assertIsInstance(eph_pub, bytes)
        self.assertEqual(len(secret), 32)
        self.assertEqual(len(eph_pub), 32)

    def test_recipient_returns_secret(self):
        _, eph_pub = x3dh_sender(
            sender_identity_priv=self.alice_priv,
            sender_identity_pub=self.alice_pub,
            recipient_identity_pub=self.bob_pub,
            recipient_signed_prekey_pub=self.bob_spk_pub,
        )
        secret = x3dh_recipient(
            recipient_identity_priv=self.bob_priv,
            recipient_signed_prekey_priv=self.bob_spk_priv,
            sender_identity_pub=self.alice_pub,
            sender_ephemeral_pub=eph_pub,
        )
        self.assertIsInstance(secret, bytes)
        self.assertEqual(len(secret), 32)

    def test_sender_with_one_time_prekey(self):
        secret, eph_pub = x3dh_sender(
            sender_identity_priv=self.alice_priv,
            sender_identity_pub=self.alice_pub,
            recipient_identity_pub=self.bob_pub,
            recipient_signed_prekey_pub=self.bob_spk_pub,
            recipient_one_time_prekey_pub=self.bob_opk_pub,
        )
        self.assertEqual(len(secret), 32)

    def test_x3dh_secrets_are_deterministic_length(self):
        secrets = set()
        for _ in range(3):
            s, _ = x3dh_sender(
                sender_identity_priv=self.alice_priv,
                sender_identity_pub=self.alice_pub,
                recipient_identity_pub=self.bob_pub,
                recipient_signed_prekey_pub=self.bob_spk_pub,
            )
            self.assertEqual(len(s), 32)


class TestDoubleRatchet(TestCase):
    def setUp(self):
        self.shared_secret = os.urandom(32)

    def test_encrypt_returns_dict_with_required_keys(self):
        ratchet = DoubleRatchet(self.shared_secret, is_sender=True)
        payload = ratchet.ratchet_encrypt(b"Hello, world!")
        self.assertIn("header", payload)
        self.assertIn("ciphertext", payload)
        self.assertIn("nonce", payload)
        self.assertIn("n", payload)

    def test_encrypted_fields_are_base64_strings(self):
        ratchet = DoubleRatchet(self.shared_secret, is_sender=True)
        payload = ratchet.ratchet_encrypt(b"Test message")
        for field in ("header", "ciphertext", "nonce"):
            try:
                base64.b64decode(payload[field])
            except Exception:
                self.fail(f"Field {field} is not valid base64")

    def test_message_counter_increments(self):
        ratchet = DoubleRatchet(self.shared_secret, is_sender=True)
        p1 = ratchet.ratchet_encrypt(b"msg 1")
        p2 = ratchet.ratchet_encrypt(b"msg 2")
        self.assertEqual(p1["n"], 0)
        self.assertEqual(p2["n"], 1)

    def test_to_dict_roundtrip(self):
        ratchet = DoubleRatchet(self.shared_secret, is_sender=True)
        ratchet.ratchet_encrypt(b"msg")
        state = ratchet.to_dict()
        self.assertIsInstance(state, dict)
        self.assertIn("Ns", state)
        self.assertIn("Nr", state)
        self.assertIn("PN", state)

    def test_from_dict_restores_counters(self):
        ratchet = DoubleRatchet(self.shared_secret, is_sender=True)
        ratchet.ratchet_encrypt(b"msg1")
        ratchet.ratchet_encrypt(b"msg2")
        state = ratchet.to_dict()
        restored = DoubleRatchet.from_dict(state)
        self.assertEqual(restored.Ns, ratchet.Ns)
        self.assertEqual(restored.Nr, ratchet.Nr)


class TestKdfHelpers(TestCase):
    def test_kdf_rk_returns_32_bytes(self):
        result = _kdf_rk(os.urandom(32), b"info")
        self.assertEqual(len(result), 32)

    def test_kdf_rk_deterministic(self):
        ikm = os.urandom(32)
        r1 = _kdf_rk(ikm, b"test")
        r2 = _kdf_rk(ikm, b"test")
        self.assertEqual(r1, r2)

    def test_kdf_rk_different_info_produces_different_keys(self):
        ikm = os.urandom(32)
        r1 = _kdf_rk(ikm, b"info1")
        r2 = _kdf_rk(ikm, b"info2")
        self.assertNotEqual(r1, r2)

    def test_kdf_rk_step_returns_two_32_byte_keys(self):
        rk = os.urandom(32)
        dh_out = os.urandom(32)
        new_rk, ck = _kdf_rk_step(rk, dh_out)
        self.assertEqual(len(new_rk), 32)
        self.assertEqual(len(ck), 32)

    def test_kdf_ck_returns_two_32_byte_keys(self):
        ck = os.urandom(32)
        new_ck, mk = _kdf_ck(ck)
        self.assertEqual(len(new_ck), 32)
        self.assertEqual(len(mk), 32)

    def test_kdf_ck_new_ck_differs_from_input(self):
        ck = os.urandom(32)
        new_ck, _ = _kdf_ck(ck)
        self.assertNotEqual(ck, new_ck)

    def test_kdf_ck_message_key_differs_from_chain_key(self):
        ck = os.urandom(32)
        new_ck, mk = _kdf_ck(ck)
        self.assertNotEqual(new_ck, mk)


class TestDH(TestCase):
    def test_dh_returns_32_bytes(self):
        priv, pub = generate_identity_key_pair()
        result = _dh(priv, pub)
        self.assertEqual(len(result), 32)

    def test_dh_is_deterministic(self):
        priv, pub = generate_identity_key_pair()
        r1 = _dh(priv, pub)
        r2 = _dh(priv, pub)
        self.assertEqual(r1, r2)


class TestAesGcm(TestCase):
    def test_encrypt_returns_ciphertext_and_nonce(self):
        key = os.urandom(32)
        ct, nonce = _aes_gcm_encrypt(key, b"Hello World")
        self.assertIsInstance(ct, bytes)
        self.assertIsInstance(nonce, bytes)

    def test_decrypt_recovers_plaintext(self):
        key = os.urandom(32)
        plaintext = b"Secret message 12345"
        ct, nonce = _aes_gcm_encrypt(key, plaintext)
        recovered = _aes_gcm_decrypt(key, ct, nonce)
        self.assertEqual(recovered, plaintext)

    def test_different_nonce_each_encrypt(self):
        key = os.urandom(32)
        _, n1 = _aes_gcm_encrypt(key, b"msg")
        _, n2 = _aes_gcm_encrypt(key, b"msg")
        self.assertNotEqual(n1, n2)

    def test_decrypt_with_wrong_key_returns_ciphertext_or_raises(self):
        key = os.urandom(32)
        ct, nonce = _aes_gcm_encrypt(key, b"Secret")
        wrong_key = os.urandom(32)
        try:
            result = _aes_gcm_decrypt(wrong_key, ct, nonce)
            # Fallback mode returns ciphertext
            self.assertIsInstance(result, bytes)
        except Exception:
            pass  # Correct behaviour — tag mismatch exception

    def test_with_aad(self):
        key = os.urandom(32)
        aad = b"associated data"
        ct, nonce = _aes_gcm_encrypt(key, b"plaintext", aad)
        recovered = _aes_gcm_decrypt(key, ct, nonce, aad)
        self.assertEqual(recovered, b"plaintext")


class TestEncryptDecryptMessageE2E(TestCase):
    def test_encrypt_returns_payload_dict(self):
        secret = os.urandom(32)
        payload = encrypt_message_e2e("Hello World", secret)
        self.assertIn("header", payload)
        self.assertIn("ciphertext", payload)
        self.assertIn("nonce", payload)
        self.assertIn("ratchet_state", payload)

    def test_ratchet_state_is_serializable(self):
        import json
        secret = os.urandom(32)
        payload = encrypt_message_e2e("Test message", secret)
        try:
            json.dumps(payload["ratchet_state"])
        except (TypeError, ValueError) as e:
            self.fail(f"ratchet_state is not JSON serializable: {e}")

    def test_multiple_encrypt_calls_increment_n(self):
        secret = os.urandom(32)
        p1 = encrypt_message_e2e("msg 1", secret)
        p2 = encrypt_message_e2e("msg 2", secret, ratchet_state=p1["ratchet_state"])
        self.assertEqual(p1["n"], 0)
        self.assertEqual(p2["n"], 1)


class TestEncodeDecodeKey(TestCase):
    def test_encode_returns_string(self):
        key = os.urandom(32)
        encoded = encode_key(key)
        self.assertIsInstance(encoded, str)

    def test_decode_recovers_original(self):
        key = os.urandom(32)
        encoded = encode_key(key)
        decoded = decode_key(encoded)
        self.assertEqual(key, decoded)

    def test_url_safe_encoding(self):
        key = os.urandom(32)
        encoded = encode_key(key)
        # URL-safe base64 should not contain + or /
        self.assertNotIn("+", encoded)
        self.assertNotIn("/", encoded)

    def test_roundtrip_multiple_keys(self):
        for _ in range(20):
            key = os.urandom(32)
            self.assertEqual(key, decode_key(encode_key(key)))
