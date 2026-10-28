# api/admin_panel/encryption.py
"""
Admin Panel Encryption Utilities.
AES-256-GCM symmetric encryption, field-level encryption,
key management, hashing, token generation.
Used for: encrypting sensitive config values, PII masking,
API key generation, secure audit log signing.

Reference: api/messaging/utils/encryption.py (X25519+AES-256-GCM).
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Any, Dict, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


# ===========================================================================
# ENCRYPTION KEY MANAGEMENT
# ===========================================================================

def get_encryption_key(key_name: str = 'ADMIN_PANEL_ENCRYPTION_KEY') -> bytes:
    """Get encryption key from settings. 32 bytes for AES-256."""
    raw = getattr(settings, key_name, '') or os.environ.get(key_name, '')
    if not raw:
        # Derive from Django SECRET_KEY (fallback)
        raw = settings.SECRET_KEY
        logger.warning(f"[Encryption] {key_name} not set — using SECRET_KEY derivative")
    key_bytes = hashlib.sha256(raw.encode()).digest()
    return key_bytes


# ===========================================================================
# AES-256-GCM ENCRYPTION
# ===========================================================================

def encrypt_aes256_gcm(plaintext: str, key: bytes = None) -> str:
    """
    Encrypt plaintext using AES-256-GCM.
    Returns base64-encoded: nonce (12 bytes) + ciphertext + tag (16 bytes).
    """
    key = key or get_encryption_key()
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode('utf-8')
    except ImportError:
        logger.warning("[Encryption] cryptography not installed — using simple XOR fallback")
        return _simple_encrypt(plaintext, key)
    except Exception as e:
        logger.error(f"[Encryption.encrypt] {e}")
        raise


def decrypt_aes256_gcm(ciphertext_b64: str, key: bytes = None) -> str:
    """
    Decrypt AES-256-GCM ciphertext.
    Input: base64-encoded nonce + ciphertext + tag.
    """
    key = key or get_encryption_key()
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        combined = base64.b64decode(ciphertext_b64.encode('utf-8'))
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except ImportError:
        return _simple_decrypt(ciphertext_b64, key)
    except Exception as e:
        logger.error(f"[Encryption.decrypt] {e}")
        raise


def _simple_encrypt(text: str, key: bytes) -> str:
    """Simple XOR encryption fallback (NOT secure — use only when cryptography not available)."""
    text_bytes = text.encode('utf-8')
    nonce = os.urandom(12)
    key_stream = (key * (len(text_bytes) // len(key) + 1))[:len(text_bytes)]
    encrypted = bytes(a ^ b for a, b in zip(text_bytes, key_stream))
    return base64.b64encode(nonce + encrypted).decode()


def _simple_decrypt(ciphertext_b64: str, key: bytes) -> str:
    """Simple XOR decryption fallback."""
    combined = base64.b64decode(ciphertext_b64.encode())
    encrypted = combined[12:]
    key_stream = (key * (len(encrypted) // len(key) + 1))[:len(encrypted)]
    decrypted = bytes(a ^ b for a, b in zip(encrypted, key_stream))
    return decrypted.decode('utf-8')


# ===========================================================================
# FIELD-LEVEL ENCRYPTION (for Django model fields)
# ===========================================================================

class EncryptedFieldMixin:
    """
    Mixin for encrypting model field values before save.
    Usage:
        class APIKeyModel(EncryptedFieldMixin, models.Model):
            api_key = models.TextField()

            def save(self, *args, **kwargs):
                self.api_key = self.encrypt_field('api_key')
                super().save(*args, **kwargs)
    """

    _ENCRYPTED_PREFIX = 'enc:'

    def encrypt_field(self, field_name: str) -> str:
        value = getattr(self, field_name, '')
        if not value or value.startswith(self._ENCRYPTED_PREFIX):
            return value
        encrypted = encrypt_aes256_gcm(str(value))
        return f"{self._ENCRYPTED_PREFIX}{encrypted}"

    def decrypt_field(self, field_name: str) -> str:
        value = getattr(self, field_name, '')
        if not value or not value.startswith(self._ENCRYPTED_PREFIX):
            return value
        try:
            return decrypt_aes256_gcm(value[len(self._ENCRYPTED_PREFIX):])
        except Exception:
            return ''

    def is_field_encrypted(self, field_name: str) -> bool:
        value = getattr(self, field_name, '')
        return bool(value and value.startswith(self._ENCRYPTED_PREFIX))


# ===========================================================================
# HASHING UTILITIES
# ===========================================================================

def hash_sha256(value: str, salt: str = '') -> str:
    """SHA-256 hash with optional salt."""
    data = f"{salt}{value}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def hash_sha512(value: str, salt: str = '') -> str:
    """SHA-512 hash."""
    data = f"{salt}{value}".encode('utf-8')
    return hashlib.sha512(data).hexdigest()


def hash_pbkdf2(value: str, salt: str = '', iterations: int = 100000) -> str:
    """PBKDF2 hash — for password-like values."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), iterations)
    return f"pbkdf2$sha256${iterations}${salt}${base64.b64encode(dk).decode()}"


def verify_pbkdf2(value: str, stored_hash: str) -> bool:
    """Verify a PBKDF2 hash."""
    try:
        _, algo, iterations, salt, hash_b64 = stored_hash.split('$')
        dk = hashlib.pbkdf2_hmac(algo.replace('sha', 'sha'), value.encode(), salt.encode(), int(iterations))
        return base64.b64encode(dk).decode() == hash_b64
    except Exception:
        return False


def hmac_sign(message: str, secret: str = '') -> str:
    """HMAC-SHA256 signature."""
    key = (secret or settings.SECRET_KEY).encode()
    sig = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
    return sig


def hmac_verify(message: str, signature: str, secret: str = '') -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac_sign(message, secret)
    return hmac.compare_digest(expected, signature)


# ===========================================================================
# TOKEN GENERATION
# ===========================================================================

def generate_api_key(prefix: str = 'ap', length: int = 32) -> str:
    """Generate a secure API key: ap_<32 random chars>"""
    token = secrets.token_urlsafe(length)
    return f"{prefix}_{token}"


def generate_secret(length: int = 32) -> str:
    """Generate a cryptographically secure secret."""
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return str(secrets.randbelow(10 ** length)).zfill(length)


def generate_webhook_secret() -> str:
    """Generate a webhook signing secret (hex, 32 bytes)."""
    return secrets.token_hex(32)


# ===========================================================================
# PII MASKING
# ===========================================================================

def mask_pii(value: str, pii_type: str = 'generic') -> str:
    """
    Mask PII for logs and display.
    pii_type: generic | email | phone | ip | nid | card
    """
    if not value:
        return ''
    import re
    maskers = {
        'email':   lambda v: re.sub(r'(?<=.{2}).(?=[^@]*@)', '*', v) if '@' in v else v[:3] + '***',
        'phone':   lambda v: v[:3] + '****' + v[-3:] if len(v) >= 7 else '***',
        'ip':      lambda v: '.'.join(v.split('.')[:3]) + '.xxx' if '.' in v else v,
        'nid':     lambda v: '***' + v[-4:] if len(v) >= 4 else '***',
        'card':    lambda v: '*' * (len(v) - 4) + v[-4:] if len(v) > 4 else '****',
        'generic': lambda v: v[:2] + '***' + v[-2:] if len(v) > 4 else '***',
    }
    masker = maskers.get(pii_type, maskers['generic'])
    try:
        return masker(value)
    except Exception:
        return '***'


def sanitize_for_log(data: Dict) -> Dict:
    """Remove/mask sensitive fields from data before logging."""
    sensitive = {'password', 'token', 'secret', 'api_key', 'private_key',
                 'nid', 'card_number', 'cvv', 'pin', 'otp', 'auth_token'}
    result = {}
    for key, value in data.items():
        if key.lower() in sensitive:
            result[key] = '***REDACTED***'
        elif isinstance(value, str) and len(value) > 100:
            result[key] = value[:50] + '...[truncated]'
        else:
            result[key] = value
    return result


# ===========================================================================
# ADMIN CONFIG ENCRYPTION
# ===========================================================================

def encrypt_config_value(value: str) -> str:
    """Encrypt a SystemConfig value for storage."""
    return encrypt_aes256_gcm(value)


def decrypt_config_value(encrypted: str) -> str:
    """Decrypt a SystemConfig value for use."""
    return decrypt_aes256_gcm(encrypted)


def is_encrypted_value(value: str) -> bool:
    """Check if a value is encrypted."""
    try:
        decoded = base64.b64decode(value.encode())
        return len(decoded) >= 12  # At minimum: nonce (12 bytes)
    except Exception:
        return False