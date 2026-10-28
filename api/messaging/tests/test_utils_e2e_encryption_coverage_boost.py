"""
test_utils_e2e_encryption_coverage_boost.py
=============================================
Real-execution coverage for messaging/utils/e2e_encryption.py.

CONFIRMED BUG FIXED IN SOURCE (see e2e_encryption.py DoubleRatchet):
a freshly-constructed receiver (`DoubleRatchet(secret, is_sender=False)`)
could never decrypt a message - `ratchet_decrypt` always raised
"Cannot decrypt: receiving chain not initialized". Root cause was two
compounding issues in the initial chain-key derivation:
  1. The receiver-side init branch was gated on `self.DHs_priv` already
     being set, which is never true for a fresh receiver (only
     is_sender=True set it).
  2. Even ignoring (1), the sender seeded CKs from `_kdf_rk_step(...)[0]`
     while the (dead) receiver code seeded CKr from
     `_kdf_rk_step(...)[1]` - different halves of the same HKDF output,
     so they could never have matched anyway.
Not currently called from any production code path (only key generation
and the X3DH handshake are wired into views_extra.py; DoubleRatchet /
encrypt_message_e2e / decrypt_message_e2e have no callers yet), so this
was latent rather than a live incident - but it's a real, reproducible
defect, confirmed via direct execution before touching the source, and
regression-tested below (TestDoubleRatchetRoundtrip) so it can't return.

As with encryption.py, the 'cryptography' package is actually installed,
so ImportError fallback branches are reached via a selective import
patch; generic-exception branches are triggered with real invalid inputs
wherever the library naturally raises for them.
"""
from __future__ import annotations

import base64
import builtins
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from api.messaging.utils import e2e_encryption as e2e

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


def _identity_and_prekeys():
    sender_id_priv, sender_id_pub = e2e.generate_identity_key_pair()
    recip_id_priv, recip_id_pub = e2e.generate_identity_key_pair()
    recip_spk_priv, recip_spk_pub = e2e.generate_signed_prekey_pair()
    recip_otpk_priv, recip_otpk_pub = e2e.generate_prekey_pair()
    return dict(
        sender_id_priv=sender_id_priv, sender_id_pub=sender_id_pub,
        recip_id_priv=recip_id_priv, recip_id_pub=recip_id_pub,
        recip_spk_priv=recip_spk_priv, recip_spk_pub=recip_spk_pub,
        recip_otpk_priv=recip_otpk_priv, recip_otpk_pub=recip_otpk_pub,
    )


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

class TestGenerateIdentityKeyPair:
    def test_happy_path_32_byte_keys(self):
        priv, pub = e2e.generate_identity_key_pair()
        assert len(priv) == 32 and len(pub) == 32

    def test_import_error_falls_back_to_random_bytes(self):
        with _no_cryptography():
            priv, pub = e2e.generate_identity_key_pair()
        assert len(priv) == 32 and len(pub) == 32

    def test_aliases_point_to_the_same_function(self):
        assert e2e.generate_ephemeral_key_pair is e2e.generate_identity_key_pair
        assert e2e.generate_prekey_pair is e2e.generate_identity_key_pair
        assert e2e.generate_signed_prekey_pair is e2e.generate_identity_key_pair


# ---------------------------------------------------------------------------
# X3DH
# ---------------------------------------------------------------------------

class TestX3dhHandshake:
    def test_sender_and_recipient_derive_matching_secret_without_otpk(self):
        k = _identity_and_prekeys()
        secret_a, eph_pub = e2e.x3dh_sender(
            k["sender_id_priv"], k["sender_id_pub"],
            k["recip_id_pub"], k["recip_spk_pub"],
        )
        secret_b = e2e.x3dh_recipient(
            k["recip_id_priv"], k["recip_spk_priv"],
            k["sender_id_pub"], eph_pub,
        )
        assert secret_a == secret_b
        assert len(secret_a) == 32

    def test_sender_and_recipient_derive_matching_secret_with_otpk(self):
        k = _identity_and_prekeys()
        secret_a, eph_pub = e2e.x3dh_sender(
            k["sender_id_priv"], k["sender_id_pub"],
            k["recip_id_pub"], k["recip_spk_pub"],
            k["recip_otpk_pub"],
        )
        secret_b = e2e.x3dh_recipient(
            k["recip_id_priv"], k["recip_spk_priv"],
            k["sender_id_pub"], eph_pub,
            k["recip_otpk_priv"],
        )
        assert secret_a == secret_b

    def test_otpk_changes_the_derived_secret(self):
        k = _identity_and_prekeys()
        secret_no_otpk, _ = e2e.x3dh_sender(
            k["sender_id_priv"], k["sender_id_pub"],
            k["recip_id_pub"], k["recip_spk_pub"],
        )
        secret_with_otpk, _ = e2e.x3dh_sender(
            k["sender_id_priv"], k["sender_id_pub"],
            k["recip_id_pub"], k["recip_spk_pub"],
            k["recip_otpk_pub"],
        )
        assert secret_no_otpk != secret_with_otpk

    def test_sender_import_error_falls_back(self):
        k = _identity_and_prekeys()
        with _no_cryptography():
            secret, eph_pub = e2e.x3dh_sender(
                k["sender_id_priv"], k["sender_id_pub"],
                k["recip_id_pub"], k["recip_spk_pub"],
            )
        assert len(secret) == 32
        assert len(eph_pub) == 32

    def test_sender_generic_exception_falls_back(self):
        # Wrong-length identity key raises a real ValueError inside the
        # try block once cryptography parses it.
        secret, eph_pub = e2e.x3dh_sender(
            b"too-short", b"y" * 32, b"z" * 32, b"w" * 32,
        )
        assert len(secret) == 32
        assert len(eph_pub) == 32

    def test_recipient_import_error_falls_back(self):
        k = _identity_and_prekeys()
        with _no_cryptography():
            secret = e2e.x3dh_recipient(
                k["recip_id_priv"], k["recip_spk_priv"],
                k["sender_id_pub"], b"e" * 32,
            )
        assert len(secret) == 32

    def test_recipient_generic_exception_falls_back(self):
        secret = e2e.x3dh_recipient(
            b"too-short", b"y" * 32, b"z" * 32, b"w" * 32,
        )
        assert len(secret) == 32


# ---------------------------------------------------------------------------
# DoubleRatchet - regression coverage for the fix described at module top
# ---------------------------------------------------------------------------

class TestDoubleRatchetRoundtrip:
    def test_fresh_receiver_can_decrypt_first_message(self):
        """Regression test for the confirmed bug: this used to always
        raise ValueError('Cannot decrypt: receiving chain not
        initialized') on a fresh receiver's very first message."""
        secret = b"s" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)

        payload = sender.ratchet_encrypt(b"hello world")
        plaintext = receiver.ratchet_decrypt(payload)

        assert plaintext == b"hello world"

    def test_multiple_sequential_messages_roundtrip(self):
        secret = b"m" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)

        for i in range(5):
            msg = f"message {i}".encode()
            payload = sender.ratchet_encrypt(msg)
            assert receiver.ratchet_decrypt(payload) == msg

    def test_message_counter_increments(self):
        secret = b"n" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        p0 = sender.ratchet_encrypt(b"a")
        p1 = sender.ratchet_encrypt(b"b")
        assert p0["n"] == 0
        assert p1["n"] == 1
        assert sender.Ns == 2

    def test_associated_data_must_match_to_decrypt(self):
        secret = b"a" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        payload = sender.ratchet_encrypt(b"secret", associated_data=b"ctx-1")
        with pytest.raises(Exception):
            receiver.ratchet_decrypt(payload, associated_data=b"ctx-2")

    def test_receiver_can_reply_using_its_own_ratchet_encrypt(self):
        # Exercises the CKs-not-yet-set fallback inside ratchet_encrypt
        # (only sender-constructed instances get CKs during __init__).
        secret = b"r" * 32
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        payload = receiver.ratchet_encrypt(b"reply")
        assert "header" in payload and "ciphertext" in payload


class TestDoubleRatchetDHStep:
    """
    Part 19 addition, INCOMPLETE - see handoff notes. DoubleRatchet
    previously only implemented the symmetric chain ratchet (see class
    docstring's prior "Does NOT implement the DH ratchet step" note). A
    _dh_ratchet_step method was added, triggered from ratchet_decrypt
    when the peer's ratchet public key changes, mirroring the reference
    algorithm's DHRatchet() step.

    What these tests actually established, and what they didn't:
      - Confirmed (test_normal_two_way_conversation_never_triggers_dh_step):
        an ordinary back-and-forth conversation never changes either
        side's DHs_pub, so _dh_ratchet_step's trigger condition never
        fires from message exchange alone - only __init__ sets DHs, and
        the only code that reassigns it afterward is _dh_ratchet_step
        itself, which needs a change already detected to run. Whether,
        and on what trigger, a party should proactively rotate is an
        open design question.
      - Attempted and abandoned: a "new device" simulation (directly
        overwriting bob.DHs_priv/DHs_pub mid-conversation) to exercise
        the trigger and prove round-tripping + break-in recovery
        end-to-end. This does NOT work with the current API: nothing
        re-derives bob's own CKs from his new DHs_priv when it's
        swapped in this way - only the RECEIVING side
        (_dh_ratchet_step, reacting to a change in the incoming
        header) updates CKs/CKr together. There is currently no
        sender-side equivalent for a party to proactively rotate its
        own key and correctly re-derive its own sending chain to
        match. Real Signal reconciles this by having the very first
        message in each direction *be* a DH ratchet step (the
        responder's long-term signed prekey doubles as their initial
        DHs) rather than treating "bootstrap" and "DH ratchet step" as
        two separate mechanisms the way this file's existing
        _INITIAL_CHAIN_INFO fixed-label bootstrap does - reconciling
        that is a real design change to how DoubleRatchet.__init__
        and x3dh_sender/x3dh_recipient hand off to each other, not
        something to guess at here.
      - test_dh_ratchet_step_math_is_internally_consistent below checks
        _dh_ratchet_step's KDF/DH calls in isolation (both directions
        of the DH agree, RK/CKr/CKs/DHs all update as specified) - this
        confirms the primitive itself is built correctly, but is NOT a
        substitute for the end-to-end proof above, which remains
        outstanding.
    """

    def test_normal_two_way_conversation_never_triggers_dh_step(self):
        secret = b"g" * 32
        alice = e2e.DoubleRatchet(secret, is_sender=True)
        bob = e2e.DoubleRatchet(secret, is_sender=False)
        bob_dhs_pub_before = bob.DHs_pub

        for i in range(6):
            bob.ratchet_decrypt(alice.ratchet_encrypt(f"a{i}".encode()))
            alice.ratchet_decrypt(bob.ratchet_encrypt(f"b{i}".encode()))

        assert bob.DHs_pub == bob_dhs_pub_before
        assert alice.DHr == bob_dhs_pub_before

    def test_dh_ratchet_step_math_is_internally_consistent(self):
        """
        Isolated check of _dh_ratchet_step's KDF/DH calls, NOT a claim
        that the full two-party protocol correctly reaches this method
        in practice (see class docstring). Manually places a receiver
        into a state where it has an established chain with a peer,
        then delivers a header claiming a new peer ratchet key, and
        checks the method derives what an independent, from-scratch
        computation of the same DH agreement says it should.
        """
        secret = b"h" * 32
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        # Establish an initial chain so CKr/DHr are non-None before rotating.
        sender_epoch0 = e2e.DoubleRatchet(secret, is_sender=True)
        receiver.ratchet_decrypt(sender_epoch0.ratchet_encrypt(b"epoch0"))

        rk_before = receiver.RK
        receiver_dhs_priv_before = receiver.DHs_priv

        new_peer_priv, new_peer_pub = e2e.generate_ephemeral_key_pair()
        receiver._dh_ratchet_step(new_peer_pub, their_pn=0)

        # Receiving-chain half: independently recompute DH(receiver's
        # OLD priv, new peer pub) and the resulting KDF_RK - must match
        # what the method derived for CKr.
        expected_dh_recv = e2e._dh(receiver_dhs_priv_before, new_peer_pub)
        expected_rk_1, expected_ckr = e2e._kdf_rk_step(rk_before, expected_dh_recv)
        assert receiver.CKr == expected_ckr

        # Sending-chain half: receiver must have rotated to a NEW DHs
        # (not reused the old one), and CKs must match DH(receiver's
        # NEW priv, same new peer pub) fed through KDF_RK a second time.
        assert receiver.DHs_priv != receiver_dhs_priv_before
        expected_dh_send = e2e._dh(receiver.DHs_priv, new_peer_pub)
        _, expected_cks = e2e._kdf_rk_step(expected_rk_1, expected_dh_send)
        assert receiver.CKs == expected_cks

        assert receiver.DHr == new_peer_pub
        assert receiver.Ns == 0 and receiver.Nr == 0

    def test_state_survives_to_dict_from_dict_across_multiple_calls(self):
        """
        NOTE: despite 3 message round-trips, this does NOT exercise
        _dh_ratchet_step (see class docstring) - both directions stay
        on their epoch-0 bootstrap chains throughout, since nothing
        here changes either side's DHs_pub. Kept as a real regression
        test of the ordinary multi-message state round-trip.
        """
        secret = b"f" * 32
        alice_state = None
        bob_state = None

        p1 = e2e.encrypt_message_e2e("first", secret, alice_state)
        alice_state = p1["ratchet_state"]
        r1 = e2e.decrypt_message_e2e(p1, secret, bob_state)
        bob_state = r1["ratchet_state"]
        assert r1["plaintext"] == "first"

        p2 = e2e.encrypt_message_e2e("reply", secret, bob_state)
        bob_state = p2["ratchet_state"]
        r2 = e2e.decrypt_message_e2e(p2, secret, alice_state)
        alice_state = r2["ratchet_state"]
        assert r2["plaintext"] == "reply"

        p3 = e2e.encrypt_message_e2e("post-rotation", secret, alice_state)
        r3 = e2e.decrypt_message_e2e(p3, secret, bob_state)
        assert r3["plaintext"] == "post-rotation"

    def test_to_dict_from_dict_state_roundtrip_mid_session(self):
        secret = b"d" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)

        first = sender.ratchet_encrypt(b"first")
        receiver.ratchet_decrypt(first)

        state = sender.to_dict()
        assert set(state.keys()) >= {"RK", "CKs", "CKr", "DHs_priv", "DHs_pub", "DHr", "Ns", "Nr", "PN"}

        restored_sender = e2e.DoubleRatchet.from_dict(state)
        second = restored_sender.ratchet_encrypt(b"second")
        assert receiver.ratchet_decrypt(second) == b"second"

    def test_from_dict_handles_null_fields(self):
        secret = b"z" * 32
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        state = receiver.to_dict()
        assert state["CKs"] is None  # never sent anything yet
        restored = e2e.DoubleRatchet.from_dict(state)
        assert restored.CKs is None
        assert restored.RK == secret

    def test_make_header_uses_zero_bytes_when_no_dhs_pub(self):
        secret = b"h" * 32
        ratchet = e2e.DoubleRatchet.__new__(e2e.DoubleRatchet)
        ratchet.DHs_pub = None
        ratchet.PN = 0
        ratchet.Ns = 0
        header = ratchet._make_header()
        assert header[:32] == b"\x00" * 32


# ---------------------------------------------------------------------------
# Skipped-message-key handling (Part 6 audit fix: out-of-order delivery)
# ---------------------------------------------------------------------------

class TestSkippedMessageKeys:
    """
    Regression tests for the confirmed gap: MKSKIPPED was initialized but
    never read or written anywhere, so ratchet_decrypt() always assumed
    the next message was exactly the next KDF step. Any real-world
    reordering (WS reconnect, retry, multiple network paths) made
    decryption fail outright for the out-of-order message, permanently -
    there was no way to recover once a gap opened up.
    """

    def test_out_of_order_delivery_within_single_session(self):
        secret = b"o" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)

        p0 = sender.ratchet_encrypt(b"msg-0")
        p1 = sender.ratchet_encrypt(b"msg-1")
        p2 = sender.ratchet_encrypt(b"msg-2")

        # Arrives out of order: 2, then 0, then 1
        assert receiver.ratchet_decrypt(p2) == b"msg-2"
        assert receiver.ratchet_decrypt(p0) == b"msg-0"
        assert receiver.ratchet_decrypt(p1) == b"msg-1"

    def test_out_of_order_delivery_with_persisted_state_roundtrip(self):
        """
        The critical case: encrypt_message_e2e/decrypt_message_e2e are
        stateless per call by design (their own docstrings: persist
        ratchet_state and pass it back in on the next call) - this is
        the actual pattern the rest of the codebase uses, reconstructing
        a fresh DoubleRatchet via from_dict() on every single call. If
        MKSKIPPED isn't correctly serialized across that round-trip, the
        in-memory fix above wouldn't actually help in production even
        though it works when the same objects stay in memory.
        """
        secret = b"p" * 32
        s1 = e2e.encrypt_message_e2e("msg-0", secret)
        s2 = e2e.encrypt_message_e2e("msg-1", secret, ratchet_state=s1["ratchet_state"])
        s3 = e2e.encrypt_message_e2e("msg-2", secret, ratchet_state=s2["ratchet_state"])

        # Receiver gets message 2 first, with no prior state at all.
        r2 = e2e.decrypt_message_e2e(s3, secret)
        assert r2["plaintext"] == "msg-2"

        # Message 0 arrives late - state was persisted/reloaded between
        # every call, exactly like a real DB-backed conversation.
        r0 = e2e.decrypt_message_e2e(s1, secret, ratchet_state=r2["ratchet_state"])
        assert r0["plaintext"] == "msg-0"

        # Message 1 arrives last.
        r1 = e2e.decrypt_message_e2e(s2, secret, ratchet_state=r0["ratchet_state"])
        assert r1["plaintext"] == "msg-1"

        # All skipped keys should have been consumed - none left over.
        assert r1["ratchet_state"]["MKSKIPPED"] == {}

    def test_out_of_order_delivery_fully_shuffled_five_messages(self):
        secret = b"f" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        payloads = [sender.ratchet_encrypt(f"m{i}".encode()) for i in range(5)]

        shuffled = [payloads[3], payloads[0], payloads[4], payloads[1], payloads[2]]
        results = [receiver.ratchet_decrypt(p) for p in shuffled]
        assert results == [b"m3", b"m0", b"m4", b"m1", b"m2"]
        assert receiver.MKSKIPPED == {}

    def test_max_skip_protection_rejects_huge_gap(self):
        secret = b"g" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        for _ in range(receiver.MAX_SKIP + 5):
            payload = sender.ratchet_encrypt(b"x")
        # `payload` is now message n = MAX_SKIP+4 - a fresh receiver
        # jumping straight to it would have to derive/store MAX_SKIP+4
        # keys, which is exactly the DoS scenario MAX_SKIP guards against.
        with pytest.raises(ValueError, match="too many skipped"):
            receiver.ratchet_decrypt(payload)

    def test_replayed_message_after_key_consumed_fails(self):
        secret = b"r" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        p0 = sender.ratchet_encrypt(b"once")
        assert receiver.ratchet_decrypt(p0) == b"once"
        with pytest.raises(ValueError, match="unavailable"):
            receiver.ratchet_decrypt(p0)  # same message again

    def test_skipped_key_removed_from_mkskipped_after_use(self):
        secret = b"k" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        p0 = sender.ratchet_encrypt(b"a")
        p1 = sender.ratchet_encrypt(b"b")

        receiver.ratchet_decrypt(p1)  # skips p0's key, stores it
        assert len(receiver.MKSKIPPED) == 1

        receiver.ratchet_decrypt(p0)  # consumes the stored key
        assert len(receiver.MKSKIPPED) == 0

    def test_mkskipped_survives_to_dict_from_dict_roundtrip(self):
        secret = b"m" * 32
        sender = e2e.DoubleRatchet(secret, is_sender=True)
        receiver = e2e.DoubleRatchet(secret, is_sender=False)
        p0 = sender.ratchet_encrypt(b"a")
        p1 = sender.ratchet_encrypt(b"b")

        receiver.ratchet_decrypt(p1)  # p0's key gets skipped and stored
        assert len(receiver.MKSKIPPED) == 1

        state = receiver.to_dict()
        assert "MKSKIPPED" in state
        assert len(state["MKSKIPPED"]) == 1

        restored = e2e.DoubleRatchet.from_dict(state)
        assert len(restored.MKSKIPPED) == 1
        assert restored.ratchet_decrypt(p0) == b"a"


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

class TestHighLevelHelpers:
    def test_encrypt_decrypt_message_e2e_fresh_session(self):
        secret = b"e" * 32
        payload = e2e.encrypt_message_e2e("hi there", secret)
        assert "ratchet_state" in payload
        # A brand-new decrypt-side session (mirrors how a real recipient,
        # who has never seen this chat before, would call this).
        result = e2e.decrypt_message_e2e(payload, secret)
        assert result["plaintext"] == "hi there"
        assert "ratchet_state" in result

    def test_encrypt_with_existing_ratchet_state(self):
        secret = b"f" * 32
        first_payload = e2e.encrypt_message_e2e("first", secret)
        second_payload = e2e.encrypt_message_e2e(
            "second", secret, ratchet_state=first_payload["ratchet_state"]
        )
        assert second_payload["n"] == 1

    def test_decrypt_with_existing_ratchet_state_advances_the_chain(self):
        """Regression test for the decrypt_message_e2e state-threading
        gap described at module top: decrypting a *second* message in
        the same conversation must use the persisted ratchet_state from
        the first decrypt call, or it silently re-derives the first
        message's key and fails to decrypt the second."""
        secret = b"g" * 32

        p1 = e2e.encrypt_message_e2e("one", secret)
        result1 = e2e.decrypt_message_e2e(p1, secret)
        assert result1["plaintext"] == "one"

        p2 = e2e.encrypt_message_e2e(
            "two", secret, ratchet_state=p1["ratchet_state"]
        )
        result2 = e2e.decrypt_message_e2e(
            p2, secret, ratchet_state=result1["ratchet_state"]
        )
        assert result2["plaintext"] == "two"

    def test_decrypt_recovers_when_earlier_message_in_chain_never_arrives(self):
        """
        Previously documented a limitation: if the caller ignores the
        returned ratchet_state and passes None every time, a fresh
        receiver starting partway through the sender's chain (having
        "missed" message n=0) could never decrypt n=1, since decryption
        blindly assumed the next message was exactly the next KDF step.
        Part 6 audit fix: this is the same underlying gap as out-of-order
        delivery - the skipped-key handling in ratchet_decrypt() now
        correctly derives through to whatever `n` the arriving message
        actually declares, whether the earlier message merely hasn't
        arrived *yet* or never arrives at all.
        """
        secret = b"h" * 32
        p1 = e2e.encrypt_message_e2e("one", secret)
        e2e.decrypt_message_e2e(p1, secret)  # ratchet_state discarded

        p2 = e2e.encrypt_message_e2e(
            "two", secret, ratchet_state=p1["ratchet_state"]
        )
        result = e2e.decrypt_message_e2e(p2, secret)  # fresh session again
        assert result["plaintext"] == "two"


# ---------------------------------------------------------------------------
# KDF / DH / AES-GCM helpers (direct)
# ---------------------------------------------------------------------------

class TestKdfRk:
    def test_happy_path(self):
        out = e2e._kdf_rk(b"input-key-material", b"info")
        assert len(out) == 32

    def test_import_error_falls_back_to_sha256(self):
        import hashlib
        with _no_cryptography():
            out = e2e._kdf_rk(b"secret", b"info")
        assert out == hashlib.sha256(b"secret" + b"info").digest()


class TestKdfRkStep:
    def test_happy_path_returns_two_32_byte_values(self):
        rk, ck = e2e._kdf_rk_step(b"r" * 32, b"dh-output")
        assert len(rk) == 32
        assert len(ck) == 32
        assert rk != ck

    def test_deterministic_given_same_inputs(self):
        a = e2e._kdf_rk_step(b"r" * 32, b"x")
        b = e2e._kdf_rk_step(b"r" * 32, b"x")
        assert a == b

    def test_import_error_falls_back(self):
        with _no_cryptography():
            rk, ck = e2e._kdf_rk_step(b"r" * 32, b"dh-output")
        assert len(rk) == 32
        assert len(ck) == 32


class TestKdfCk:
    def test_returns_new_chain_key_and_message_key(self):
        new_ck, mk = e2e._kdf_ck(b"c" * 32)
        assert len(new_ck) == 32
        assert len(mk) == 32
        assert new_ck != mk

    def test_stepping_is_deterministic_and_advances(self):
        ck0 = b"c" * 32
        ck1, mk1 = e2e._kdf_ck(ck0)
        ck2, mk2 = e2e._kdf_ck(ck1)
        assert ck1 != ck0
        assert mk1 != mk2


class TestDh:
    def test_real_exchange_is_symmetric(self):
        priv_a, pub_a = e2e.generate_identity_key_pair()
        priv_b, pub_b = e2e.generate_identity_key_pair()
        assert e2e._dh(priv_a, pub_b) == e2e._dh(priv_b, pub_a)

    def test_falls_back_to_sha256_on_bad_keys(self):
        import hashlib
        result = e2e._dh(b"too-short", b"also-short")
        assert result == hashlib.sha256(b"too-short" + b"also-short").digest()


class TestAesGcm:
    def test_encrypt_decrypt_roundtrip(self):
        key = b"k" * 32
        ct, nonce = e2e._aes_gcm_encrypt(key, b"payload", b"aad")
        pt = e2e._aes_gcm_decrypt(key, ct, nonce, b"aad")
        assert pt == b"payload"

    def test_encrypt_import_error_returns_plaintext_and_zero_nonce(self):
        with _no_cryptography():
            ct, nonce = e2e._aes_gcm_encrypt(b"k" * 32, b"payload")
        assert ct == b"payload"
        assert nonce == b"\x00" * 12

    def test_decrypt_import_error_returns_ciphertext_unchanged(self):
        with _no_cryptography():
            pt = e2e._aes_gcm_decrypt(b"k" * 32, b"already-plaintext", b"\x00" * 12)
        assert pt == b"already-plaintext"


# ---------------------------------------------------------------------------
# encode_key / decode_key
# ---------------------------------------------------------------------------

class TestEncodeDecodeKey:
    def test_roundtrip(self):
        raw = b"\x01\x02\x03" * 10
        encoded = e2e.encode_key(raw)
        assert isinstance(encoded, str)
        assert e2e.decode_key(encoded) == raw
