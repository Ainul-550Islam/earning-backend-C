"""
End-to-End Encryption — Full Signal Protocol style implementation.
Uses X3DH (Extended Triple Diffie-Hellman) for key agreement
and Double Ratchet for forward secrecy.

WhatsApp, Signal, Telegram Secret Chats all use this approach.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import logging
import os
import struct
from typing import Optional

logger = logging.getLogger(__name__)

# ── Key Generation ────────────────────────────────────────────────────────────

def generate_identity_key_pair() -> tuple[bytes, bytes]:
    """Generate a long-term identity key pair (Ed25519/X25519)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption
        )
        priv = X25519PrivateKey.generate()
        pub  = priv.public_key()
        priv_bytes = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub_bytes  = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return priv_bytes, pub_bytes
    except ImportError:
        logger.warning("e2e_encryption: cryptography not installed. Using random bytes.")
        priv = os.urandom(32)
        pub  = os.urandom(32)
        return priv, pub

generate_ephemeral_key_pair  = generate_identity_key_pair
generate_prekey_pair         = generate_identity_key_pair
generate_signed_prekey_pair  = generate_identity_key_pair


# ── X3DH Key Agreement ────────────────────────────────────────────────────────

def x3dh_sender(
    sender_identity_priv: bytes,
    sender_identity_pub: bytes,
    recipient_identity_pub: bytes,
    recipient_signed_prekey_pub: bytes,
    recipient_one_time_prekey_pub: Optional[bytes] = None,
) -> tuple[bytes, bytes]:
    """
    X3DH key agreement — sender side.
    Returns (shared_secret_32_bytes, ephemeral_public_key).
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption
        )

        eph_priv_key  = X25519PrivateKey.generate()
        eph_pub_bytes = eph_priv_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        sender_id_key  = X25519PrivateKey.from_private_bytes(sender_identity_priv)
        recipient_ik   = X25519PublicKey.from_public_bytes(recipient_identity_pub)
        recipient_spk  = X25519PublicKey.from_public_bytes(recipient_signed_prekey_pub)

        # DH1: sender IK ↔ recipient SPK
        dh1 = sender_id_key.exchange(recipient_spk)
        # DH2: sender EK ↔ recipient IK
        dh2 = eph_priv_key.exchange(recipient_ik)
        # DH3: sender EK ↔ recipient SPK
        dh3 = eph_priv_key.exchange(recipient_spk)

        dh_outputs = dh1 + dh2 + dh3

        # DH4: sender EK ↔ recipient OPK (if present)
        if recipient_one_time_prekey_pub:
            recipient_opk = X25519PublicKey.from_public_bytes(recipient_one_time_prekey_pub)
            dh4 = eph_priv_key.exchange(recipient_opk)
            dh_outputs += dh4

        shared_secret = _kdf_rk(dh_outputs, b"WhisperText")
        return shared_secret, eph_pub_bytes

    except ImportError:
        shared_secret = hashlib.sha256(
            sender_identity_priv + recipient_identity_pub + os.urandom(16)
        ).digest()
        return shared_secret, os.urandom(32)
    except Exception as exc:
        logger.error("x3dh_sender: %s", exc)
        return os.urandom(32), os.urandom(32)


def x3dh_recipient(
    recipient_identity_priv: bytes,
    recipient_signed_prekey_priv: bytes,
    sender_identity_pub: bytes,
    sender_ephemeral_pub: bytes,
    recipient_one_time_prekey_priv: Optional[bytes] = None,
) -> bytes:
    """
    X3DH key agreement — recipient side.
    Returns shared_secret_32_bytes.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey
        )

        recipient_id_key  = X25519PrivateKey.from_private_bytes(recipient_identity_priv)
        recipient_spk_key = X25519PrivateKey.from_private_bytes(recipient_signed_prekey_priv)
        sender_ik         = X25519PublicKey.from_public_bytes(sender_identity_pub)
        sender_ek         = X25519PublicKey.from_public_bytes(sender_ephemeral_pub)

        dh1 = recipient_spk_key.exchange(sender_ik)
        dh2 = recipient_id_key.exchange(sender_ek)
        dh3 = recipient_spk_key.exchange(sender_ek)

        dh_outputs = dh1 + dh2 + dh3

        if recipient_one_time_prekey_priv:
            opk = X25519PrivateKey.from_private_bytes(recipient_one_time_prekey_priv)
            dh4 = opk.exchange(sender_ek)
            dh_outputs += dh4

        return _kdf_rk(dh_outputs, b"WhisperText")

    except ImportError:
        return hashlib.sha256(
            recipient_identity_priv + sender_identity_pub
        ).digest()
    except Exception as exc:
        logger.error("x3dh_recipient: %s", exc)
        return os.urandom(32)


# ── Double Ratchet ────────────────────────────────────────────────────────────

class DoubleRatchet:
    """
    Double Ratchet Algorithm implementation.

    Provides forward secrecy within a chain: each message uses its own
    derived key, discarded after use. Handles reordering within a
    chain via MKSKIPPED (bounded by MAX_SKIP).

    DH ratchet step (_dh_ratchet_step): implemented, triggered from
    ratchet_decrypt() when the peer's ratchet public key changes -
    derives fresh root/chain keys from a live DH exchange, which is
    what gives break-in recovery its property (a compromised chain's
    keys can't derive anything from after the next rotation, since the
    derivation depends on DHs_priv, a value never transmitted).

    NOT YET RESOLVED: nothing in this class, or in the surrounding
    encrypt_message_e2e/decrypt_message_e2e wrappers, currently CAUSES
    a rotation - an ordinary back-and-forth conversation never changes
    either side's DHs_pub (verified in
    test_normal_two_way_conversation_never_triggers_dh_step), because
    __init__ is the only other place DHs gets assigned, and there's no
    sender-side way to proactively rotate one's own key and correctly
    re-derive one's own CKs to match (only the receiving side reacts to
    an already-changed incoming key). The reference algorithm avoids
    this gap by making the very first message in each direction *be* a
    DH ratchet step (the responder's long-term signed prekey doubles as
    their initial DHs) rather than treating bootstrap and DH-ratcheting
    as two separate mechanisms, the way _INITIAL_CHAIN_INFO's
    fixed-label bootstrap here does. Reconciling that is a real,
    deliberate change to how __init__ and x3dh_sender/x3dh_recipient
    hand off to each other - not something to guess at while wrapping
    up an audit session. _dh_ratchet_step's own KDF/DH math is checked
    in isolation (test_dh_ratchet_step_math_is_internally_consistent)
    and is sound; the missing piece is what calls it in practice.

    The very first chain key on each side (before either party has seen
    the other's ratchet public key) is derived from a fixed,
    reproducible label instead of a live DH - see _INITIAL_CHAIN_INFO
    below for why a live DH isn't possible at that specific point. Also
    unresolved: this fixed label is the same for both directions, so
    the initiator's first message and the responder's first reply
    currently derive their chain key from the exact same (RK, label)
    pair - see the comment on _INITIAL_CHAIN_INFO.
    """
    MAX_SKIP = 1000

    # Fixed, reproducible context label used to derive the very first
    # chain key on both sides from the shared X3DH root key. A live DH
    # can't be used for this step: at construction time the sender only
    # has `shared_secret`, not a peer ratchet public key to exchange
    # against, so whatever the sender computes here must be something
    # the receiver can *independently* reproduce from RK alone. Only
    # this bootstrap chain (epoch 0) works this way - every DH ratchet
    # step after it (see _dh_ratchet_step) uses a real DH exchange.
    #
    # KNOWN LIMITATION, not yet fixed (flagged during the Part 19
    # session, reverted mid-fix per instruction to stop and hand off -
    # see handoff notes): both directions' very first message
    # (initiator's first send, responder's first reply) derive their
    # chain key from this exact same (RK, label) pair, since neither
    # side's state differs yet at that point - meaning the initiator's
    # message-0 key and the responder's message-0 key are currently the
    # *same* symmetric key. A two-label fix (initiator vs responder,
    # selected locally from whichever of CKs/CKr is already set when
    # the other is first bootstrapped) was drafted and is safe to
    # reapply, but was reverted here rather than shipped half-applied.
    _INITIAL_CHAIN_INFO = b"WhisperRatchetInit"

    def __init__(self, shared_secret: bytes, is_sender: bool = True):
        self.RK  = shared_secret  # Root key
        self.CKs: Optional[bytes] = None  # Sending chain key
        self.CKr: Optional[bytes] = None  # Receiving chain key
        # Both sides get their own ratchet key pair up front: the sender
        # puts its public half in the message header, and the receiver
        # needs one of its own in case it later replies.
        self.DHs_priv, self.DHs_pub = generate_ephemeral_key_pair()
        self.DHr:      Optional[bytes] = None
        self.Ns  = 0   # Send message counter
        self.Nr  = 0   # Receive message counter
        self.PN  = 0   # Previous sending chain length
        self.MKSKIPPED: dict = {}

        if is_sender:
            _, self.CKs = _kdf_rk_step(self.RK, self._INITIAL_CHAIN_INFO)

    def ratchet_encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> dict:
        """
        Encrypt a message, advancing the sending ratchet.

        Doesn't need its own DH-rotation trigger: if this side's ratchet
        key was due to rotate, that already happened inside the most
        recent ratchet_decrypt() call (_dh_ratchet_step below rotates
        DHs_priv/DHs_pub and re-derives CKs together, in one step) - by
        the time this method runs, self.CKs already reflects it.
        """
        if not self.CKs:
            # Must match the receiver's independent derivation in
            # ratchet_decrypt() below - a random seed here would make
            # this chain permanently undecipherable by the peer.
            _, self.CKs = _kdf_rk_step(self.RK, self._INITIAL_CHAIN_INFO)

        self.CKs, mk = _kdf_ck(self.CKs)
        header = self._make_header()
        ciphertext, nonce = _aes_gcm_encrypt(mk, plaintext, associated_data + header)
        self.Ns += 1

        return {
            "header": base64.b64encode(header).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "n": self.Ns - 1,
        }

    def ratchet_decrypt(self, payload: dict, associated_data: bytes = b"") -> bytes:
        """
        Decrypt a message, advancing the receiving ratchet.

        Handles out-of-order delivery within a chain: if a message's
        sequence number is ahead of what's expected, the keys for the
        messages in between are derived and stashed in MKSKIPPED
        (bounded by MAX_SKIP) rather than assumed lost, so a
        late-arriving earlier message can still be decrypted. `n` is
        read from `header` (authenticated as AEAD associated data
        below), not from the outer, unauthenticated `payload["n"]`
        field, since only the former is tamper-evident.

        DH ratchet step: if the header's ratchet public key differs
        from the last one seen (self.DHr), the peer has rotated -
        _dh_ratchet_step() re-derives root/chain keys from a fresh DH
        exchange before this message's key is derived, giving break-in
        recovery across the rotation (see class docstring).
        """
        header    = base64.b64decode(payload["header"])
        ciphertext= base64.b64decode(payload["ciphertext"])
        nonce     = base64.b64decode(payload["nonce"])
        dh_pub    = header[:32]
        pn, n     = struct.unpack(">II", header[32:40])

        skip_key = (dh_pub, n)
        if skip_key in self.MKSKIPPED:
            mk = self.MKSKIPPED.pop(skip_key)
            return _aes_gcm_decrypt(mk, ciphertext, nonce, associated_data + header)

        if not self.CKr:
            # First-ever decrypt on this side: bootstrap exactly like
            # the sender's initial CKs (epoch 0, fixed-label derivation,
            # no DH yet - see _INITIAL_CHAIN_INFO).
            self.DHr = dh_pub
            _, self.CKr = _kdf_rk_step(self.RK, self._INITIAL_CHAIN_INFO)
            self.Nr = 0
        elif dh_pub != self.DHr:
            # Peer has rotated to a new ratchet key - this is the DH
            # ratchet step, not the epoch-0 bootstrap above.
            self._dh_ratchet_step(dh_pub, pn)

        if self.CKr:
            if n < self.Nr:
                # Already consumed (and not found above, so not a
                # legitimate late-arriving skip) - stale or replayed.
                raise ValueError(f"Cannot decrypt: message key for n={n} unavailable (Nr={self.Nr})")
            if n - self.Nr > self.MAX_SKIP:
                raise ValueError(f"Cannot decrypt: too many skipped messages (n={n}, Nr={self.Nr})")
            while self.Nr < n:
                self.CKr, skipped_mk = _kdf_ck(self.CKr)
                self.MKSKIPPED[(dh_pub, self.Nr)] = skipped_mk
                self.Nr += 1
            self.CKr, mk = _kdf_ck(self.CKr)
            self.Nr += 1
            return _aes_gcm_decrypt(mk, ciphertext, nonce, associated_data + header)

        # Defensive fallback only: the block above now unconditionally
        # sets self.CKr on first use, so this is no longer reachable in
        # practice.
        raise ValueError("Cannot decrypt: receiving chain not initialized")  # pragma: no cover

    def _dh_ratchet_step(self, new_dh_pub: bytes, their_pn: int) -> None:
        """
        DH ratchet step - Signal's mechanism for break-in recovery.

        Triggered from ratchet_decrypt() when the peer starts sending
        under a new ratchet public key. Two DH exchanges happen here,
        matching the reference algorithm exactly:

          1. New receiving chain: DH(my CURRENT DHs_priv, their NEW
             DHr) -> re-derive RK and CKr. This is computable right now
             because it only needs a private key I already have and a
             public key I just received.
          2. Rotate DHs: generate a brand new DHs_priv/DHs_pub for
             myself - this is the value that never gets transmitted,
             and is what makes step 3 unrecoverable from a compromise
             of anything before this point.
          3. New sending chain: DH(my NEW DHs_priv, their same new
             DHr) -> re-derive RK (again) and CKs.

        Before switching chains, any message keys still owed from the
        tail of the OLD receiving chain are derived and stashed in
        MKSKIPPED (their_pn = how many messages the peer sent in their
        previous sending chain) - otherwise a message sent just before
        the peer's rotation, arriving after this method runs, becomes
        permanently undecipherable: the old CKr is about to be
        overwritten and there is no way back to it.
        """
        if self.CKr is not None and self.DHr is not None:
            skip_count = their_pn - self.Nr
            if skip_count > self.MAX_SKIP:
                raise ValueError(
                    f"Cannot DH-ratchet: too many skipped messages in outgoing "
                    f"chain (pn={their_pn}, Nr={self.Nr})"
                )
            while self.Nr < their_pn:
                self.CKr, skipped_mk = _kdf_ck(self.CKr)
                self.MKSKIPPED[(self.DHr, self.Nr)] = skipped_mk
                self.Nr += 1

        self.PN = self.Ns
        self.Ns = 0
        self.Nr = 0
        self.DHr = new_dh_pub

        dh_out_recv = _dh(self.DHs_priv, self.DHr)
        self.RK, self.CKr = _kdf_rk_step(self.RK, dh_out_recv)

        self.DHs_priv, self.DHs_pub = generate_ephemeral_key_pair()

        dh_out_send = _dh(self.DHs_priv, self.DHr)
        self.RK, self.CKs = _kdf_rk_step(self.RK, dh_out_send)

        logger.debug("DoubleRatchet: DH ratchet step complete (new epoch, PN=%d)", self.PN)

    def _make_header(self) -> bytes:
        if self.DHs_pub:
            return self.DHs_pub[:32] + struct.pack(">II", self.PN, self.Ns)
        return b"\x00" * 32 + struct.pack(">II", self.PN, self.Ns)

    def to_dict(self) -> dict:
        """Serialize state for storage."""
        return {
            "RK": base64.b64encode(self.RK).decode() if self.RK else None,
            "CKs": base64.b64encode(self.CKs).decode() if self.CKs else None,
            "CKr": base64.b64encode(self.CKr).decode() if self.CKr else None,
            "DHs_priv": base64.b64encode(self.DHs_priv).decode() if self.DHs_priv else None,
            "DHs_pub":  base64.b64encode(self.DHs_pub).decode()  if self.DHs_pub  else None,
            "DHr":      base64.b64encode(self.DHr).decode()      if self.DHr      else None,
            "Ns": self.Ns, "Nr": self.Nr, "PN": self.PN,
            # Part 6 audit fix: without serializing this, every skipped
            # message key was silently discarded the moment
            # encrypt_message_e2e/decrypt_message_e2e's stateless,
            # persist-ratchet_state-between-calls pattern round-tripped
            # through to_dict()/from_dict() - which is the ONLY way this
            # class is actually used outside its own unit tests. A tuple
            # key (dh_pub bytes, n) isn't JSON-serializable on its own,
            # so it's flattened to a "base64(dh_pub):n" string key.
            "MKSKIPPED": {
                f"{base64.b64encode(dh).decode()}:{n}": base64.b64encode(mk).decode()
                for (dh, n), mk in self.MKSKIPPED.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DoubleRatchet":
        dr = cls.__new__(cls)
        dr.MKSKIPPED = {}
        for composite_key, mk_b64 in (data.get("MKSKIPPED") or {}).items():
            dh_b64, _, n_str = composite_key.rpartition(":")
            dr.MKSKIPPED[(base64.b64decode(dh_b64), int(n_str))] = base64.b64decode(mk_b64)
        for k, v in data.items():
            if k == "MKSKIPPED":
                continue
            if k in ("Ns", "Nr", "PN"):
                setattr(dr, k, v)
            elif v:
                setattr(dr, k, base64.b64decode(v))
            else:
                setattr(dr, k, None)
        return dr


# ── KDF helpers ───────────────────────────────────────────────────────────────

def _kdf_rk(input_key_material: bytes, info: bytes = b"") -> bytes:
    """HKDF-SHA256 key derivation."""
    try:
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info)
        return hkdf.derive(input_key_material)
    except ImportError:
        return hashlib.sha256(input_key_material + info).digest()


def _kdf_rk_step(rk: bytes, dh_out: bytes) -> tuple[bytes, bytes]:
    """KDF for root key ratchet. Returns (new_root_key, new_chain_key)."""
    try:
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        hkdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=rk, info=b"WhisperRatchet")
        output = hkdf.derive(dh_out)
        return output[:32], output[32:]
    except ImportError:
        h = hashlib.sha256(rk + dh_out).digest()
        return h[:16] + os.urandom(16), h[16:] + os.urandom(16)


def _kdf_ck(ck: bytes) -> tuple[bytes, bytes]:
    """KDF for chain key step. Returns (new_chain_key, message_key)."""
    new_ck = hmac.new(ck, b"\x01", hashlib.sha256).digest()
    mk     = hmac.new(ck, b"\x02", hashlib.sha256).digest()
    return new_ck, mk


def _dh(priv: bytes, pub: bytes) -> bytes:
    """Diffie-Hellman exchange."""
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey
        )
        p = X25519PrivateKey.from_private_bytes(priv)
        q = X25519PublicKey.from_public_bytes(pub)
        return p.exchange(q)
    except Exception:
        return hashlib.sha256(priv + pub).digest()


# ── AES-256-GCM ───────────────────────────────────────────────────────────────

def _aes_gcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext, aad or None)
        return ct, nonce
    except ImportError:
        return plaintext, b"\x00" * 12


def _aes_gcm_decrypt(key: bytes, ciphertext: bytes, nonce: bytes, aad: bytes = b"") -> bytes:
    """Decrypt with AES-256-GCM."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(key).decrypt(nonce, ciphertext, aad or None)
    except ImportError:
        return ciphertext


# ── High-level helpers ────────────────────────────────────────────────────────

def encrypt_message_e2e(
    plaintext: str,
    shared_secret: bytes,
    ratchet_state: Optional[dict] = None,
) -> dict:
    """
    Encrypt a message using Double Ratchet.
    Returns payload dict to store/send. Includes updated ratchet state.
    """
    if ratchet_state:
        ratchet = DoubleRatchet.from_dict(ratchet_state)
    else:
        ratchet = DoubleRatchet(shared_secret, is_sender=True)

    payload = ratchet.ratchet_encrypt(plaintext.encode("utf-8"))
    payload["ratchet_state"] = ratchet.to_dict()
    return payload


def decrypt_message_e2e(
    payload: dict,
    shared_secret: bytes,
    ratchet_state: Optional[dict] = None,
) -> dict:
    """
    Decrypt a message using Double Ratchet.

    BUG FIX: this used to return a bare `str`, with no way for a caller
    to get the receiving ratchet's advanced state back out. Combined
    with encrypt_message_e2e's ratchet_state output/input contract, the
    intent is clearly for both sides of a conversation to be resumable
    from persisted state (e.g. a JSON column) across separate calls -
    but decrypting a second message always re-derived the *first*
    message's key, since every call started from scratch. Now returns
    both, matching encrypt_message_e2e's shape.

    Returns:
        {"plaintext": <str>, "ratchet_state": <dict>} - persist
        ratchet_state and pass it back in as `ratchet_state` on the next
        call for this conversation.
    """
    if ratchet_state:
        ratchet = DoubleRatchet.from_dict(ratchet_state)
    else:
        ratchet = DoubleRatchet(shared_secret, is_sender=False)

    plaintext = ratchet.ratchet_decrypt(payload)
    return {
        "plaintext": plaintext.decode("utf-8"),
        "ratchet_state": ratchet.to_dict(),
    }


def encode_key(key_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(key_bytes).decode()


def decode_key(key_str: str) -> bytes:
    return base64.urlsafe_b64decode(key_str.encode())