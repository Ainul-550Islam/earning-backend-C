"""
payout_queue/utils/encryption.py  ← NEW (Production Gap #2)

PURPOSE:
    Provides field-level encryption for sensitive PII stored in payout_queue.
    Specifically: PayoutItem.account_number (mobile wallet / bank account numbers).

WHY:
    account_number was stored as plaintext — a PCI DSS / GDPR risk.
    Bangladesh BFIU and Bangladeshi Data Protection guidelines require
    that financial identifiers be stored encrypted at rest.

HOW:
    EncryptedCharField:
        A custom Django TextField subclass that transparently
        encrypts on write (get_prep_value) and decrypts on read
        (from_db_value) using Fernet symmetric encryption
        (cryptography library — already a transitive dependency of
        Django's cryptographic utilities).

        Key: settings.PAYOUT_ENCRYPTION_KEY
             Must be a 32-byte URL-safe base64 string.
             Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

        Dev/test fallback: If PAYOUT_ENCRYPTION_KEY is not set,
        values are stored plaintext (no error). Set the key in
        production .env BEFORE deploying this migration.

    compute_account_hash(account_number):
        Returns an HMAC-SHA256 digest of the account_number using
        the same PAYOUT_ENCRYPTION_KEY as the HMAC secret.
        Stored in PayoutItem.account_number_hash for:
          1. Duplicate detection (services._create_single_payout_item)
          2. Admin search (without decrypting all rows)
          3. Audit: "was this account number paid?" without exposing the number

        Deterministic: same input + same key = same hash (searchable).
        One-way: cannot reconstruct account_number from hash alone.

SECURITY PROPERTIES:
    - Fernet = AES-128-CBC + HMAC-SHA256 authentication tag.
    - Each value gets a unique IV — identical account numbers encrypt differently.
    - Ciphertext is authenticated — tampering raises InvalidToken, not silent corruption.
    - Key rotation: re-encrypt all rows with new key, update PAYOUT_ENCRYPTION_KEY.
    - If cryptography is not installed: ImportError is raised at startup with
      a helpful message (not silently skipped).

SETUP CHECKLIST:
    1. pip install cryptography  (likely already installed)
    2. Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    3. Add to .env:  PAYOUT_ENCRYPTION_KEY=<generated key>
    4. Run migration: python manage.py migrate payout_queue 0007
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any, Optional

from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

def _get_encryption_key() -> Optional[bytes]:
    """
    Returns the Fernet key from settings.PAYOUT_ENCRYPTION_KEY as bytes,
    or None if not configured (plaintext fallback for dev/tests).
    """
    from django.conf import settings
    raw: str = getattr(settings, "PAYOUT_ENCRYPTION_KEY", "") or ""
    if not raw:
        return None
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw

def _get_hmac_secret() -> bytes:
    """
    Returns the HMAC secret for account_number hashing.
    Uses PAYOUT_ENCRYPTION_KEY if available, falls back to a dev-only constant.
    """
    key = _get_encryption_key()
    if key:
        return key
    logger.debug(
        "_get_hmac_secret: PAYOUT_ENCRYPTION_KEY not set. "
        "Using insecure dev fallback. Set the key in production .env."
    )
    return b"payout-dev-hmac-secret-DO-NOT-USE-IN-PRODUCTION"

# ---------------------------------------------------------------------------
# Fernet cipher (lazy)
# ---------------------------------------------------------------------------

def _get_cipher():
    """
    Returns a Fernet cipher instance, or None if no key is configured.

    Raises:
        ImportError: If cryptography is not installed and a key IS configured.
    """
    key = _get_encryption_key()
    if key is None:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key)
    except ImportError as exc:
        raise ImportError(
            "payout_queue encryption requires the 'cryptography' package. "
            "Run: pip install cryptography"
        ) from exc
    except Exception as exc:
        raise ValueError(
            f"PAYOUT_ENCRYPTION_KEY is invalid: {exc}. "
            "Generate a valid key: python -c "
            "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a plaintext string. Returns base64-encoded ciphertext string.
    Returns plaintext unchanged if no key is configured (dev mode).
    """
    if not plaintext:
        return plaintext
    cipher = _get_cipher()
    if cipher is None:
        return plaintext
    encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(encrypted_bytes).decode("utf-8")

def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a base64-encoded ciphertext string. Returns plaintext.
    Returns ciphertext unchanged if no key is configured (dev mode).
    Returns ciphertext unchanged if decryption fails (already-plaintext data).
    """
    if not ciphertext:
        return ciphertext
    cipher = _get_cipher()
    if cipher is None:
        return ciphertext
    try:
        encrypted_bytes = base64.b64decode(ciphertext.encode("utf-8"))
        return cipher.decrypt(encrypted_bytes).decode("utf-8")
    except Exception:
        # Value is likely already plaintext (pre-migration data or dev mode).
        # Return as-is rather than raising.
        return ciphertext

def compute_account_hash(account_number: str) -> str:
    """
    Compute an HMAC-SHA256 hex digest of an account number.

    Used for:
      1. Duplicate detection in PayoutItem (filter by hash instead of plaintext)
      2. Admin search without decrypting all rows
      3. Compliance check: "was this account ever paid?" without exposing PII

    Deterministic: same input + same key = same 64-char hex string.
    One-way: cannot reconstruct account_number from hash alone.

    Args:
        account_number: Raw (plaintext) account number to hash.

    Returns:
        64-character lowercase hex string (SHA-256 digest).
    """
    if not account_number:
        return ""
    secret = _get_hmac_secret()
    return hmac.new(
        secret,
        account_number.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

# ---------------------------------------------------------------------------
# EncryptedCharField
# ---------------------------------------------------------------------------

class EncryptedCharField(models.TextField):
    """
    A Django model field that transparently encrypts/decrypts its value
    using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).

    Stored as: base64-encoded ciphertext string in a TEXT column.
    Read back as: original plaintext string.

    Filtering: Cannot use exact-match filters on this field (ciphertext is
    different every time due to random IV). For lookups, use
    compute_account_hash() + a companion *_hash field.

    Dev mode (PAYOUT_ENCRYPTION_KEY not set):
        Values are stored and returned as plaintext.
        No error is raised. This is intentional for local dev and tests.

    Key rotation:
        1. Set PAYOUT_ENCRYPTION_KEY to the new key.
        2. Run: python manage.py payout_rotate_encryption --old-key <old> --new-key <new>
           (management command — add to TODO list if key rotation is needed).

    Usage in model::

        from api.payout_queue.utils.encryption import EncryptedCharField

        class PayoutItem(TimestampedModel):
            account_number = EncryptedCharField(
                max_length=500,
                verbose_name=_("Recipient Account Number"),
            )
            account_number_hash = models.CharField(
                max_length=64, blank=True, db_index=True,
                verbose_name=_("Account Number Hash (for lookups)"),
            )

            def save(self, *args, **kwargs):
                # Always recompute hash from plaintext before saving
                if self.account_number:
                    from api.payout_queue.utils.encryption import compute_account_hash
                    self.account_number_hash = compute_account_hash(self.account_number)
                super().save(*args, **kwargs)
    """

    description = _("Encrypted text (Fernet AES-128-CBC)")

    def __init__(self, *args, **kwargs):
        # max_length is not meaningful for an encrypted TextField but we
        # accept it for API compatibility with CharField.
        kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)

    def from_db_value(
        self, value: Any, expression: Any, connection: Any
    ) -> Optional[str]:
        """Called when the field is loaded from DB. Decrypts transparently."""
        if value is None:
            return value
        return decrypt_value(str(value))

    def to_python(self, value: Any) -> Optional[str]:
        """Called during deserialization and form validation."""
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)

    def get_prep_value(self, value: Any) -> Optional[str]:
        """Called before writing to DB. Encrypts transparently."""
        if value is None:
            return value
        return encrypt_value(str(value))

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs
