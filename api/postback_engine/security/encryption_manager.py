"""
security/encryption_manager.py
────────────────────────────────
Field-level encryption for sensitive data.
Used for storing network secret keys, API keys, and webhook secrets.
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Falls back to plain storage if encryption key not configured.
"""
from __future__ import annotations
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Encrypt/decrypt sensitive string fields.

    Setup:
        In settings.py:
            POSTBACK_ENGINE_ENCRYPTION_KEY = os.environ.get("PE_ENCRYPTION_KEY", "")

        Generate a key:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()

    Usage:
        encrypted = encryption_manager.encrypt("my_secret_key")
        decrypted = encryption_manager.decrypt(encrypted)
    """

    _PREFIX = "enc:"  # prefix to identify encrypted values in DB

    def __init__(self):
        self._fernet = None
        self._initialised = False

    def _get_fernet(self):
        if self._initialised:
            return self._fernet
        self._initialised = True
        try:
            from django.conf import settings
            key = getattr(settings, "POSTBACK_ENGINE_ENCRYPTION_KEY", "")
            if not key:
                key = os.environ.get("PE_ENCRYPTION_KEY", "")
            if key:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except ImportError:
            logger.debug("cryptography not installed — field encryption disabled.")
        except Exception as exc:
            logger.warning("EncryptionManager init failed: %s", exc)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns prefixed ciphertext. Falls back to plaintext."""
        if not plaintext:
            return plaintext
        fernet = self._get_fernet()
        if not fernet:
            return plaintext  # no encryption configured
        try:
            token = fernet.encrypt(plaintext.encode("utf-8"))
            return self._PREFIX + base64.urlsafe_b64encode(token).decode("utf-8")
        except Exception as exc:
            logger.warning("EncryptionManager.encrypt failed: %s", exc)
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string. Returns original plaintext."""
        if not ciphertext or not ciphertext.startswith(self._PREFIX):
            return ciphertext  # not encrypted or plain
        fernet = self._get_fernet()
        if not fernet:
            return ciphertext
        try:
            raw = base64.urlsafe_b64decode(ciphertext[len(self._PREFIX):].encode("utf-8"))
            return fernet.decrypt(raw).decode("utf-8")
        except Exception as exc:
            logger.warning("EncryptionManager.decrypt failed: %s", exc)
            return ciphertext

    def is_encrypted(self, value: str) -> bool:
        return bool(value) and value.startswith(self._PREFIX)

    def rotate_key(self, new_key: str, values: list) -> list:
        """
        Re-encrypt a list of values with a new key.
        Use during key rotation to update stored secrets.
        """
        old_fernet = self._fernet
        try:
            from cryptography.fernet import Fernet
            new_fernet = Fernet(new_key.encode())
        except Exception as exc:
            logger.error("Key rotation failed: %s", exc)
            return values

        rotated = []
        for val in values:
            try:
                plaintext = self.decrypt(val)
                self._fernet = new_fernet
                rotated.append(self.encrypt(plaintext))
            except Exception:
                rotated.append(val)
        self._fernet = new_fernet
        return rotated


# Module-level singleton
encryption_manager = EncryptionManager()
