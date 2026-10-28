# api/support/encryption.py
"""
Encryption utilities for support system.
Sensitive data (account numbers, KYC data) encrypted before storage.
Uses Django's Fernet encryption via cryptography library.
"""
import base64
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    """Get encryption key from settings."""
    key = getattr(settings, 'SUPPORT_ENCRYPTION_KEY', '')
    if not key:
        key = getattr(settings, 'SECRET_KEY', 'default-key')[:32]
    if isinstance(key, str):
        key = key.encode('utf-8')
    # Pad or truncate to 32 bytes
    key = (key * 4)[:32]
    return base64.urlsafe_b64encode(key)


def encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext string.
    Returns base64-encoded ciphertext.
    Falls back to plaintext if cryptography not installed.
    """
    if not plaintext:
        return ''
    try:
        from cryptography.fernet import Fernet
        f          = Fernet(_get_key())
        ciphertext = f.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(ciphertext).decode('utf-8')
    except ImportError:
        logger.debug('cryptography not installed — data stored unencrypted')
        return plaintext
    except Exception as e:
        logger.error(f'encryption.encrypt: {e}')
        return plaintext


def decrypt(ciphertext: str) -> str:
    """
    Decrypt ciphertext string.
    Returns plaintext.
    """
    if not ciphertext:
        return ''
    try:
        from cryptography.fernet import Fernet, InvalidToken
        f           = Fernet(_get_key())
        raw         = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
        plaintext   = f.decrypt(raw)
        return plaintext.decode('utf-8')
    except ImportError:
        return ciphertext
    except Exception as e:
        logger.debug(f'encryption.decrypt: {e}')
        return ciphertext


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive value for display.
    '01XXXXXXXXXX' → '01****6789'
    """
    if not value or len(value) <= visible_chars * 2:
        return '*' * len(value) if value else ''
    prefix = value[:visible_chars]
    suffix = value[-visible_chars:]
    middle = '*' * (len(value) - visible_chars * 2)
    return f'{prefix}{middle}{suffix}'


def hash_sensitive(value: str) -> str:
    """One-way hash for comparison (not reversible)."""
    import hashlib
    if not value:
        return ''
    salt = getattr(settings, 'SECRET_KEY', '')[:16]
    return hashlib.sha256(f'{salt}{value}'.encode()).hexdigest()


class EncryptedFieldMixin:
    """
    Mixin for model fields that should be encrypted.
    Usage in model:
        from api.support.encryption import EncryptedFieldMixin
        class WithdrawalDispute(EncryptedFieldMixin, models.Model):
            _encrypted_fields = ['account_number']
    """
    _encrypted_fields = []

    def save(self, *args, **kwargs):
        for field_name in self._encrypted_fields:
            val = getattr(self, field_name, None)
            if val and not val.startswith('enc:'):
                setattr(self, field_name, 'enc:' + encrypt(val))
        super().save(*args, **kwargs)

    def get_decrypted(self, field_name: str) -> str:
        """Get decrypted value of an encrypted field."""
        val = getattr(self, field_name, '')
        if val and val.startswith('enc:'):
            return decrypt(val[4:])
        return val