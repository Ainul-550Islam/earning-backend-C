"""Ainul Enterprise Engine — At-Rest Secret Encryption
crypto.py

SECURITY FIX (this audit): WebhookEndpoint.secret_key was a plain
CharField — stored in cleartext in the database. This secret is what
proves webhook authenticity to receivers (it's the HMAC signing key), so a
database read (backup leak, SQLi elsewhere in the platform, insider access,
etc.) would hand over every endpoint's signing secret at once, letting an
attacker forge valid-looking webhook deliveries.

Fixed with symmetric (Fernet/AES) envelope encryption, key derived via HKDF
from settings.SECRET_KEY by default (or an explicit WEBHOOKS['ENCRYPTION_KEY']
if you'd rather manage that separately from the Django secret key — the
usual production recommendation, since it lets you rotate one independently
of the other). This mirrors the encryption approach already used elsewhere
in this codebase family for at-rest secrets (see the dr_integration module).

Usage: models/core.py's WebhookEndpoint.secret_key uses EncryptedCharField
below, so no other file needs to change — endpoint.secret_key still reads
and writes as a plain string everywhere it's already used (SignatureEngine,
serializers, admin, etc.); only the DB column actually holds ciphertext.
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import models

logger = logging.getLogger("ainul.webhooks.crypto")

_ENCRYPTED_PREFIX = "enc:v1:"  # marks a value as our ciphertext, see below


def _derive_fernet_key() -> bytes:
    """
    Derive a 32-byte Fernet key via HKDF-SHA256.

    Uses WEBHOOKS['ENCRYPTION_KEY'] if set (recommended for production —
    keeps this independent of SECRET_KEY so either can rotate on its own),
    otherwise falls back to deriving from settings.SECRET_KEY so this works
    with zero extra configuration.
    """
    webhooks_settings = getattr(settings, "WEBHOOKS", {})
    key_material = webhooks_settings.get("ENCRYPTION_KEY") or settings.SECRET_KEY
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ainul-webhooks-secret-key-encryption-v1",
        info=b"webhook-endpoint-secret-key",
    )
    derived = hkdf.derive(key_material.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret for storage. Returns a string safe to put
    straight into a CharField (prefixed so decrypt_secret can recognize it,
    and so already-encrypted values aren't double-encrypted)."""
    if plaintext is None or plaintext == "":
        return plaintext
    if plaintext.startswith(_ENCRYPTED_PREFIX):
        return plaintext  # already encrypted — avoid double-wrapping
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return _ENCRYPTED_PREFIX + token.decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Decrypt a value previously produced by encrypt_secret(). Values that
    don't carry our prefix are returned unchanged — this makes the switch
    non-breaking for any secret_key rows written before this fix, and safe
    to run against a fresh (empty) table."""
    if value is None or value == "":
        return value
    if not value.startswith(_ENCRYPTED_PREFIX):
        return value
    token = value[len(_ENCRYPTED_PREFIX):].encode("utf-8")
    try:
        return _get_fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt secret_key value — wrong key or corrupted data")
        raise


class EncryptedCharField(models.CharField):
    """
    A CharField that transparently encrypts on write and decrypts on read.
    Everywhere else in the codebase, `endpoint.secret_key` continues to
    behave exactly like a plain string — only the DB column holds ciphertext.
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_secret(value)

    def to_python(self, value):
        # Called for deserialization / form-clean; may already be plaintext
        # (e.g. right after assignment, before a DB round-trip) or ciphertext
        # (e.g. loaded from a fixture) — decrypt_secret() handles both.
        if value is None:
            return value
        if isinstance(value, str):
            return decrypt_secret(value)
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        return encrypt_secret(value)
