# =============================================================================
# api/promotions/security_vault/secure_storage.py
# AES-256 + Fernet Encrypted Data Storage
# Sensitive data (PAN, national ID, bank account) encrypted করে DB তে রাখে
# =============================================================================

import base64
import hashlib
import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

logger = logging.getLogger('security_vault.secure_storage')


# =============================================================================
# ── SETUP ─────────────────────────────────────────────────────────────────────
# =============================================================================
#
# settings.py তে এগুলো define করুন:
#   FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')  # Fernet key (32-byte base64)
#   FIELD_ENCRYPTION_KEY_BACKUP = env('FIELD_ENCRYPTION_KEY_BACKUP', default='')  # key rotation
#
# Key generate করতে:
#   from cryptography.fernet import Fernet
#   print(Fernet.generate_key().decode())


# =============================================================================
# ── FERNET ENGINE ─────────────────────────────────────────────────────────────
# =============================================================================

class FernetEngine:
    """
    Fernet symmetric encryption — authenticated encryption with AEAD।
    AES-128-CBC + HMAC-SHA256 under the hood।
    Key rotation support আছে (MultiFernet)।
    """

    def __init__(self):
        self._fernet = None

    @property
    def fernet(self):
        if self._fernet is None:
            self._fernet = self._build_fernet()
        return self._fernet

    def _build_fernet(self):
        try:
            from cryptography.fernet import Fernet, MultiFernet, InvalidToken
        except ImportError:
            raise ImproperlyConfigured(
                'cryptography package required. Install: pip install cryptography'
            )

        primary_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
        if not primary_key:
            raise ImproperlyConfigured(
                'FIELD_ENCRYPTION_KEY must be set in settings.py. '
                'Generate with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
            )

        keys = [Fernet(primary_key.encode() if isinstance(primary_key, str) else primary_key)]

        # Backup keys (key rotation এর জন্য)
        backup_key = getattr(settings, 'FIELD_ENCRYPTION_KEY_BACKUP', None)
        if backup_key:
            keys.append(Fernet(backup_key.encode() if isinstance(backup_key, str) else backup_key))

        return MultiFernet(keys) if len(keys) > 1 else keys[0]

    def encrypt(self, plaintext: str) -> str:
        """String encrypt করে base64 encoded ciphertext return করে।"""
        if not plaintext:
            return ''
        try:
            encrypted = self.fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted).decode('ascii')
        except Exception as e:
            logger.exception(f'Encryption failed: {e}')
            raise

    def decrypt(self, ciphertext: str) -> str:
        """Encrypted string decrypt করে।"""
        if not ciphertext:
            return ''
        try:
            from cryptography.fernet import InvalidToken
            raw       = base64.urlsafe_b64decode(ciphertext.encode('ascii'))
            decrypted = self.fernet.decrypt(raw)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.exception(f'Decryption failed — possible key mismatch or corruption: {e}')
            raise ValueError('Decryption failed. Data may be corrupted or key may have changed.')

    def encrypt_json(self, data: dict) -> str:
        """dict/list কে JSON serialize করে encrypt করে।"""
        return self.encrypt(json.dumps(data, separators=(',', ':')))

    def decrypt_json(self, ciphertext: str) -> dict:
        """Encrypted JSON decrypt করে dict return করে।"""
        raw = self.decrypt(ciphertext)
        return json.loads(raw)

    def rotate_key(self, ciphertext: str) -> str:
        """
        Key rotation — পুরনো key দিয়ে decrypt করে নতুন key দিয়ে encrypt করে।
        Backup key থাকলে MultiFernet এটি automatically handle করে।
        """
        plaintext = self.decrypt(ciphertext)
        return self.encrypt(plaintext)


# Singleton
_engine = FernetEngine()


# =============================================================================
# ── DJANGO MODEL FIELD ────────────────────────────────────────────────────────
# =============================================================================

class EncryptedCharField(models.TextField):
    """
    Transparent encrypted CharField।
    DB তে encrypted, Python এ plain text।

    Usage:
        class UserProfile(models.Model):
            bank_account = EncryptedCharField(max_length=50, blank=True)
            national_id  = EncryptedCharField(max_length=20)
    """

    def __init__(self, *args, **kwargs):
        # max_length DB তে apply হয় না (encrypted data longer হয়)
        kwargs.setdefault('max_length', 2000)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value) -> str:
        """Python → DB: encrypt করো।"""
        if value is None or value == '':
            return value
        if self._is_already_encrypted(value):
            return value
        return _engine.encrypt(str(value))

    def from_db_value(self, value, expression, connection) -> Optional[str]:
        """DB → Python: decrypt করো।"""
        if value is None or value == '':
            return value
        try:
            return _engine.decrypt(value)
        except Exception:
            logger.error(f'Failed to decrypt EncryptedCharField value.')
            return None  # Corrupted data — None return করো

    def to_python(self, value) -> Optional[str]:
        if value is None:
            return None
        if self._is_already_encrypted(value):
            return _engine.decrypt(value)
        return value

    @staticmethod
    def _is_already_encrypted(value: str) -> bool:
        """Fernet encrypted token দেখতে এমন।"""
        try:
            decoded = base64.urlsafe_b64decode(value + '==')
            return len(decoded) > 32
        except Exception:
            return False


class EncryptedJSONField(models.TextField):
    """
    Transparent encrypted JSONField।
    DB তে encrypted blob, Python এ dict/list।
    """

    def get_prep_value(self, value) -> str:
        if value is None:
            return None
        return _engine.encrypt_json(value)

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return {}
        try:
            return _engine.decrypt_json(value)
        except Exception:
            logger.error('Failed to decrypt EncryptedJSONField.')
            return {}

    def to_python(self, value):
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return _engine.decrypt_json(value)


# =============================================================================
# ── SECURE DATA VAULT ─────────────────────────────────────────────────────────
# =============================================================================

class SecureDataVault:
    """
    Application-level secure data storage।
    Model field encryption ছাড়াও standalone encrypt/decrypt ব্যবহার করা যাবে।

    Usage:
        vault = SecureDataVault()
        encrypted = vault.store('1234-5678-9012-3456')  # credit card
        original  = vault.retrieve(encrypted)
    """

    def __init__(self, engine: FernetEngine = None):
        self._engine = engine or _engine

    def store(self, sensitive_data: str) -> str:
        """Sensitive data encrypt করে।"""
        return self._engine.encrypt(sensitive_data)

    def retrieve(self, encrypted_data: str) -> str:
        """Encrypted data decrypt করে।"""
        return self._engine.decrypt(encrypted_data)

    def store_dict(self, data: dict) -> str:
        return self._engine.encrypt_json(data)

    def retrieve_dict(self, encrypted: str) -> dict:
        return self._engine.decrypt_json(encrypted)

    def blind_index(self, value: str) -> str:
        """
        Encrypted field এ search করার জন্য deterministic hash।
        Full decryption ছাড়াই equality search সম্ভব।
        Note: এটি one-way — original value recover করা যাবে না।

        Usage:
            # Model সংজ্ঞায়:
            national_id       = EncryptedCharField()
            national_id_index = models.CharField(max_length=64, db_index=True)

            # Save করার সময়:
            profile.national_id       = vault.store(nid)
            profile.national_id_index = vault.blind_index(nid)

            # Search করার সময়:
            UserProfile.objects.filter(national_id_index=vault.blind_index(search_nid))
        """
        secret = getattr(settings, 'BLIND_INDEX_SECRET', settings.SECRET_KEY)
        return hashlib.sha256(
            f'{secret}:{value.strip().lower()}'.encode('utf-8')
        ).hexdigest()

    def mask(self, value: str, visible_chars: int = 4, mask_char: str = '*') -> str:
        """
        Sensitive data mask করে display এর জন্য।
        Example: '1234567890' → '******7890'
        """
        if not value or len(value) <= visible_chars:
            return mask_char * len(value)
        masked_len = len(value) - visible_chars
        return mask_char * masked_len + value[-visible_chars:]

    def rotate_encryption(self, encrypted_value: str) -> str:
        """Key rotation — নতুন key দিয়ে re-encrypt করে।"""
        return self._engine.rotate_key(encrypted_value)


# =============================================================================
# ── PII ANONYMIZER ────────────────────────────────────────────────────────────
# =============================================================================

class PIIAnonymizer:
    """
    Personal Identifiable Information (PII) anonymize করার utility।
    GDPR right-to-erasure comply করতে — user data আসল data মুছে anonymized রাখে।
    """

    def anonymize_email(self, email: str) -> str:
        """john.doe@example.com → j***@e***.com"""
        if not email or '@' not in email:
            return '***@***'
        local, domain = email.split('@', 1)
        domain_parts  = domain.rsplit('.', 1)
        anon_local     = local[0] + '***' if local else '***'
        anon_domain    = domain_parts[0][0] + '***' + '.' + domain_parts[-1] if domain_parts else '***'
        return f'{anon_local}@{anon_domain}'

    def anonymize_phone(self, phone: str) -> str:
        """01712345678 → 017*****678"""
        digits = re.sub(r'\D', '', phone) if phone else ''
        if len(digits) < 7:
            return '***'
        return digits[:3] + '*' * (len(digits) - 6) + digits[-3:]

    def anonymize_name(self, name: str) -> str:
        """John Doe → J*** D***"""
        if not name:
            return '***'
        parts = name.split()
        return ' '.join(p[0] + '***' for p in parts if p)

    def anonymize_ip(self, ip: str) -> str:
        """192.168.1.100 → 192.168.1.0"""
        if not ip:
            return '0.0.0.0'
        parts = ip.split('.')
        if len(parts) == 4:
            parts[-1] = '0'
            return '.'.join(parts)
        # IPv6 — last group zero করো
        return ip.rsplit(':', 1)[0] + ':0'

    def anonymize_user_data(self, user_data: dict) -> dict:
        """User data dict এর সব PII fields anonymize করে।"""
        import re
        result = user_data.copy()
        field_handlers = {
            'email':    self.anonymize_email,
            'phone':    self.anonymize_phone,
            'username': lambda x: x[0] + '***' if x else '***',
            'name':     self.anonymize_name,
            'ip':       self.anonymize_ip,
            'ip_address': self.anonymize_ip,
        }
        for field, handler in field_handlers.items():
            if field in result and result[field]:
                result[field] = handler(str(result[field]))
        return result


# =============================================================================
# ── KEY MANAGEMENT ────────────────────────────────────────────────────────────
# =============================================================================

class KeyManager:
    """
    Encryption key management utility।
    Key rotation process guide করে।
    """

    @staticmethod
    def generate_key() -> str:
        """নতুন Fernet key generate করে।"""
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()

    @staticmethod
    def validate_key(key: str) -> bool:
        """Key valid কিনা check করে।"""
        try:
            from cryptography.fernet import Fernet
            Fernet(key.encode() if isinstance(key, str) else key)
            return True
        except Exception:
            return False

    @staticmethod
    def bulk_rotate(model_class, encrypted_field_name: str, batch_size: int = 100) -> dict:
        """
        Database এর সব encrypted records এর key rotate করে।

        Usage:
            from .models import UserProfile
            result = KeyManager.bulk_rotate(UserProfile, 'national_id')
        """
        vault         = SecureDataVault()
        total         = 0
        failed        = 0
        qs            = model_class.objects.exclude(**{f'{encrypted_field_name}__exact': ''})

        for obj in qs.iterator(chunk_size=batch_size):
            try:
                old_encrypted = getattr(obj, encrypted_field_name)
                if old_encrypted:
                    # Decrypt with old key, encrypt with new key
                    new_encrypted = vault.rotate_encryption(old_encrypted)
                    setattr(obj, encrypted_field_name, new_encrypted)
                    obj.save(update_fields=[encrypted_field_name])
                    total += 1
            except Exception as e:
                logger.exception(f'Key rotation failed for {model_class.__name__} #{obj.pk}: {e}')
                failed += 1

        logger.info(f'Key rotation complete: {total} records rotated, {failed} failed.')
        return {'rotated': total, 'failed': failed}
