# api/djoyalty/encryption.py
"""
Djoyalty Encryption -- Field-level encryption for sensitive loyalty data।
Encrypts: bank account numbers, wallet numbers, personal data।
Uses: Fernet symmetric encryption (cryptography package)।
"Do not summarize or skip any logic. Provide the full code."
"""
import base64
import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


def get_encryption_key() -> bytes:
    """Get or derive encryption key from Django SECRET_KEY।"""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import os

        secret = getattr(settings, 'DJOYALTY_ENCRYPTION_KEY', None)
        if secret:
            return base64.urlsafe_b64encode(
                secret.encode()[:32].ljust(32, b'0')
            )

        # Derive from Django SECRET_KEY
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'djoyalty_salt_v1',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
        return key
    except ImportError:
        logger.warning('encryption.py: cryptography package not installed. '
                       'Run: pip install cryptography')
        return base64.urlsafe_b64encode(b'0' * 32)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field value।"""
    if not plaintext:
        return ''
    try:
        from cryptography.fernet import Fernet
        key = get_encryption_key()
        f = Fernet(key)
        token = f.encrypt(plaintext.encode())
        return token.decode()
    except Exception as e:
        logger.error('encrypt_field error: %s', e)
        return plaintext  # Fail open (do not lose data)


def decrypt_field(ciphertext: str) -> str:
    """Decrypt an encrypted field value।"""
    if not ciphertext:
        return ''
    try:
        from cryptography.fernet import Fernet, InvalidToken
        key = get_encryption_key()
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.debug('decrypt_field error (may be unencrypted data): %s', e)
        return ciphertext  # Return as-is if not encrypted


def mask_account_number(account: str, visible_chars: int = 4) -> str:
    """Mask account/phone number for display।"""
    if not account or len(account) <= visible_chars:
        return '***'
    return '*' * (len(account) - visible_chars) + account[-visible_chars:]


class EncryptedField:
    """
    Descriptor for auto-encrypt/decrypt on model fields।
    Usage in models:
        class CustomerBankAccount(models.Model):
            _account_number = models.CharField(max_length=500)
            account_number = EncryptedField('_account_number')
    """
    def __init__(self, field_name: str):
        self.field_name = field_name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        encrypted = getattr(obj, self.field_name, '')
        return decrypt_field(encrypted)

    def __set__(self, obj, value):
        setattr(obj, self.field_name, encrypt_field(value) if value else '')
