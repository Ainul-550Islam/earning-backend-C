"""
encryption.py – Encryption system for postback module.

Provides comprehensive encryption functionality including:
- Data encryption and decryption
- Key management
- Secure hashing
- Data masking and tokenization
"""
import json
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import hashlib
import hmac
import secrets
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """Encryption algorithm enumeration."""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    FERNET = "fernet"


class HashAlgorithm(Enum):
    """Hash algorithm enumeration."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    MD5 = "md5"


class MaskingType(Enum):
    """Data masking type enumeration."""
    FULL = "full"
    PARTIAL = "partial"
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    CUSTOM = "custom"


@dataclass
class EncryptionKey:
    """Encryption key data structure."""
    id: str
    algorithm: EncryptionAlgorithm
    key_data: bytes
    salt: bytes
    created_at: datetime = field(default_factory=timezone.now)
    expires_at: Optional[datetime] = None
    usage_count: int = 0
    max_usage: int = 1000000
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def is_usage_exceeded(self) -> bool:
        """Check if key usage is exceeded."""
        return self.usage_count >= self.max_usage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without sensitive data)."""
        return {
            'id': self.id,
            'algorithm': self.algorithm.value,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'usage_count': self.usage_count,
            'max_usage': self.max_usage,
            'metadata': self.metadata,
        }


@dataclass
class EncryptedData:
    """Encrypted data structure."""
    data: bytes
    algorithm: EncryptionAlgorithm
    key_id: str
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_base64(self) -> str:
        """Convert to base64 string."""
        data_dict = {
            'data': base64.b64encode(self.data).decode(),
            'algorithm': self.algorithm.value,
            'key_id': self.key_id,
            'iv': base64.b64encode(self.iv).decode() if self.iv else None,
            'tag': base64.b64encode(self.tag).decode() if self.tag else None,
            'metadata': self.metadata,
        }
        return base64.b64encode(json.dumps(data_dict).encode()).decode()
    
    @classmethod
    def from_base64(cls, data_str: str) -> 'EncryptedData':
        """Create from base64 string."""
        data_dict = json.loads(base64.b64decode(data_str.encode()).decode())
        return cls(
            data=base64.b64decode(data_dict['data'].encode()),
            algorithm=EncryptionAlgorithm(data_dict['algorithm']),
            key_id=data_dict['key_id'],
            iv=base64.b64decode(data_dict['iv'].encode()) if data_dict.get('iv') else None,
            tag=base64.b64decode(data_dict['tag'].encode()) if data_dict.get('tag') else None,
            metadata=data_dict.get('metadata', {})
        )


class KeyManager:
    """
    Encryption key manager.
    
    Handles key generation, rotation, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.keys: Dict[str, EncryptionKey] = {}
        self.current_key_id: Optional[str] = None
        self.key_rotation_interval = getattr(settings, 'ENCRYPTION_KEY_ROTATION_DAYS', 90)
        self.default_algorithm = EncryptionAlgorithm.AES_256_GCM
        self._setup_default_key()
    
    def _setup_default_key(self):
        """Setup default encryption key."""
        try:
            default_key = self.generate_key(self.default_algorithm, "default")
            self.current_key_id = default_key.id
            self.logger.info("Default encryption key created")
        except Exception as e:
            self.logger.error(f"Failed to create default encryption key: {str(e)}")
    
    def generate_key(self, algorithm: EncryptionAlgorithm, key_name: str,
                     expires_in_days: int = None) -> EncryptionKey:
        """
        Generate new encryption key.
        
        Args:
            algorithm: Encryption algorithm
            key_name: Key name/identifier
            expires_in_days: Expiration in days
            
        Returns:
            Generated encryption key
        """
        import uuid
        
        # Generate key based on algorithm
        if algorithm == EncryptionAlgorithm.FERNET:
            key_data = Fernet.generate_key()
        else:
            key_data = os.urandom(32)  # 256-bit key
        
        # Generate salt
        salt = os.urandom(16)
        
        # Set expiration
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        # Create key object
        key = EncryptionKey(
            id=f"{key_name}_{uuid.uuid4().hex[:12]}",
            algorithm=algorithm,
            key_data=key_data,
            salt=salt,
            expires_at=expires_at
        )
        
        # Store key
        self.keys[key.id] = key
        
        self.logger.info(f"Generated encryption key: {key.id} ({algorithm.value})")
        return key
    
    def get_current_key(self) -> Optional[EncryptionKey]:
        """Get current encryption key."""
        if self.current_key_id:
            return self.keys.get(self.current_key_id)
        return None
    
    def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Get encryption key by ID."""
        return self.keys.get(key_id)
    
    def rotate_key(self, key_id: str = None) -> EncryptionKey:
        """
        Rotate encryption key.
        
        Args:
            key_id: Key ID to rotate (None = current key)
            
        Returns:
            New encryption key
        """
        if key_id is None:
            key_id = self.current_key_id
        
        old_key = self.get_key(key_id)
        if not old_key:
            raise IntegrationException(f"Key not found: {key_id}")
        
        # Generate new key
        new_key = self.generate_key(old_key.algorithm, old_key.id.split('_')[0])
        
        # Update current key if rotating current
        if key_id == self.current_key_id:
            self.current_key_id = new_key.id
        
        self.logger.info(f"Rotated encryption key: {key_id} -> {new_key.id}")
        return new_key
    
    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke encryption key.
        
        Args:
            key_id: Key ID to revoke
            
        Returns:
            True if revoked successfully
        """
        if key_id in self.keys:
            del self.keys[key_id]
            
            # Update current key if revoked
            if self.current_key_id == key_id:
                # Find another key or create new one
                if self.keys:
                    self.current_key_id = next(iter(self.keys))
                else:
                    self._setup_default_key()
            
            self.logger.info(f"Revoked encryption key: {key_id}")
            return True
        
        return False
    
    def cleanup_expired_keys(self) -> int:
        """Clean up expired keys."""
        expired_keys = [
            key_id for key_id, key in self.keys.items()
            if key.is_expired()
        ]
        
        for key_id in expired_keys:
            self.revoke_key(key_id)
        
        self.logger.info(f"Cleaned up {len(expired_keys)} expired keys")
        return len(expired_keys)
    
    def get_key_statistics(self) -> Dict[str, Any]:
        """Get key statistics."""
        total_keys = len(self.keys)
        expired_keys = len([k for k in self.keys.values() if k.is_expired()])
        current_algorithm = self.get_current_key().algorithm.value if self.get_current_key() else None
        
        return {
            'total_keys': total_keys,
            'expired_keys': expired_keys,
            'active_keys': total_keys - expired_keys,
            'current_key_id': self.current_key_id,
            'current_algorithm': current_algorithm,
            'rotation_interval_days': self.key_rotation_interval,
        }


class DataEncryptor:
    """
    Data encryptor/decryptor.
    
    Handles encryption and decryption operations.
    """
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def encrypt(self, data: Union[str, bytes, Dict[str, Any]], key_id: str = None) -> EncryptedData:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            key_id: Key ID to use (None = current key)
            
        Returns:
            Encrypted data
        """
        # Get encryption key
        if key_id:
            key = self.key_manager.get_key(key_id)
        else:
            key = self.key_manager.get_current_key()
        
        if not key:
            raise IntegrationException("No encryption key available")
        
        # Convert data to bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, dict):
            data_bytes = json.dumps(data).encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            raise IntegrationException(f"Unsupported data type: {type(data)}")
        
        try:
            # Encrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.FERNET:
                encrypted_data = self._encrypt_fernet(data_bytes, key)
            elif key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                encrypted_data = self._encrypt_aes_gcm(data_bytes, key)
            elif key.algorithm == EncryptionAlgorithm.AES_256_CBC:
                encrypted_data = self._encrypt_aes_cbc(data_bytes, key)
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                encrypted_data = self._encrypt_chacha20(data_bytes, key)
            else:
                raise IntegrationException(f"Unsupported encryption algorithm: {key.algorithm}")
            
            # Update key usage
            key.usage_count += 1
            
            self.logger.debug(f"Encrypted data with key: {key.id}")
            return encrypted_data
        
        except Exception as e:
            self.logger.error(f"Encryption failed: {str(e)}")
            raise IntegrationException(f"Encryption failed: {str(e)}")
    
    def decrypt(self, encrypted_data: EncryptedData) -> Union[str, bytes, Dict[str, Any]]:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted data
            
        Returns:
            Decrypted data
        """
        # Get encryption key
        key = self.key_manager.get_key(encrypted_data.key_id)
        if not key:
            raise IntegrationException(f"Encryption key not found: {encrypted_data.key_id}")
        
        try:
            # Decrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.FERNET:
                decrypted_bytes = self._decrypt_fernet(encrypted_data, key)
            elif key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                decrypted_bytes = self._decrypt_aes_gcm(encrypted_data, key)
            elif key.algorithm == EncryptionAlgorithm.AES_256_CBC:
                decrypted_bytes = self._decrypt_aes_cbc(encrypted_data, key)
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                decrypted_bytes = self._decrypt_chacha20(encrypted_data, key)
            else:
                raise IntegrationException(f"Unsupported encryption algorithm: {key.algorithm}")
            
            # Try to detect data type
            try:
                # Try JSON first
                return json.loads(decrypted_bytes.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Return as string if valid UTF-8
                try:
                    return decrypted_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Return as bytes
                    return decrypted_bytes
        
        except Exception as e:
            self.logger.error(f"Decryption failed: {str(e)}")
            raise IntegrationException(f"Decryption failed: {str(e)}")
    
    def _encrypt_fernet(self, data: bytes, key: EncryptionKey) -> EncryptedData:
        """Encrypt with Fernet."""
        f = Fernet(key.key_data)
        encrypted_data = f.encrypt(data)
        
        return EncryptedData(
            data=encrypted_data,
            algorithm=EncryptionAlgorithm.FERNET,
            key_id=key.id
        )
    
    def _decrypt_fernet(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """Decrypt with Fernet."""
        f = Fernet(key.key_data)
        return f.decrypt(encrypted_data.data)
    
    def _encrypt_aes_gcm(self, data: bytes, key: EncryptionKey) -> EncryptedData:
        """Encrypt with AES-256-GCM."""
        # Generate IV
        iv = os.urandom(12)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_data),
            modes.GCM(iv),
            backend=default_backend()
        )
        
        # Encrypt
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_id=key.id,
            iv=iv,
            tag=encryptor.tag
        )
    
    def _decrypt_aes_gcm(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """Decrypt with AES-256-GCM."""
        cipher = Cipher(
            algorithms.AES(key.key_data),
            modes.GCM(encrypted_data.iv, encrypted_data.tag),
            backend=default_backend()
        )
        
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()
    
    def _encrypt_aes_cbc(self, data: bytes, key: EncryptionKey) -> EncryptedData:
        """Encrypt with AES-256-CBC."""
        # Pad data
        padder = self._get_padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # Generate IV
        iv = os.urandom(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_data),
            modes.CBC(iv),
            backend=default_backend()
        )
        
        # Encrypt
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            algorithm=EncryptionAlgorithm.AES_256_CBC,
            key_id=key.id,
            iv=iv
        )
    
    def _decrypt_aes_cbc(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """Decrypt with AES-256-CBC."""
        cipher = Cipher(
            algorithms.AES(key.key_data),
            modes.CBC(encrypted_data.iv),
            backend=default_backend()
        )
        
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data.data) + decryptor.finalize()
        
        # Unpad data
        unpadder = self._get_unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
    
    def _encrypt_chacha20(self, data: bytes, key: EncryptionKey) -> EncryptedData:
        """Encrypt with ChaCha20-Poly1305."""
        # Generate nonce
        nonce = os.urandom(12)
        
        # Create cipher
        cipher = Cipher(
            algorithms.ChaCha20(key.key_data, nonce),
            modes.Poly1305(nonce),
            backend=default_backend()
        )
        
        # Encrypt
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            algorithm=EncryptionAlgorithm.CHACHA20_POLY1305,
            key_id=key.id,
            iv=nonce,
            tag=encryptor.tag
        )
    
    def _decrypt_chacha20(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """Decrypt with ChaCha20-Poly1305."""
        cipher = Cipher(
            algorithms.ChaCha20(key.key_data, encrypted_data.iv),
            modes.Poly1305(encrypted_data.iv, encrypted_data.tag),
            backend=default_backend()
        )
        
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()
    
    def _get_padder(self):
        """Get PKCS7 padder."""
        from cryptography.hazmat.primitives import padding
        return padding.PKCS7(128).padder()
    
    def _get_unpadder(self):
        """Get PKCS7 unpadder."""
        from cryptography.hazmat.primitives import padding
        return padding.PKCS7(128).unpadder()


class DataHasher:
    """
    Data hasher for secure hashing.
    
    Handles various hash algorithms and HMAC operations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def hash(self, data: Union[str, bytes], algorithm: HashAlgorithm = HashAlgorithm.SHA256,
             salt: bytes = None) -> str:
        """
        Hash data.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm
            salt: Salt for hashing
            
        Returns:
            Hashed data as hex string
        """
        # Convert data to bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
        
        try:
            if algorithm == HashAlgorithm.SHA256:
                hasher = hashes.Hash(hashes.SHA256())
            elif algorithm == HashAlgorithm.SHA512:
                hasher = hashes.Hash(hashes.SHA512())
            elif algorithm == HashAlgorithm.BLAKE2B:
                hasher = hashes.Hash(hashes.BLAKE2b())
            elif algorithm == HashAlgorithm.MD5:
                hasher = hashes.Hash(hashes.MD5())
            else:
                raise IntegrationException(f"Unsupported hash algorithm: {algorithm}")
            
            # Add salt if provided
            if salt:
                hasher.update(salt)
            
            hasher.update(data_bytes)
            return hasher.finalize().hex()
        
        except Exception as e:
            self.logger.error(f"Hashing failed: {str(e)}")
            raise IntegrationException(f"Hashing failed: {str(e)}")
    
    def hmac(self, data: Union[str, bytes], key: Union[str, bytes],
             algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        """
        HMAC data.
        
        Args:
            data: Data to HMAC
            key: HMAC key
            algorithm: Hash algorithm
            
        Returns:
            HMAC as hex string
        """
        # Convert to bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
        
        if isinstance(key, str):
            key_bytes = key.encode('utf-8')
        else:
            key_bytes = key
        
        try:
            if algorithm == HashAlgorithm.SHA256:
                h = hmac.new(key_bytes, data_bytes, hashlib.sha256)
            elif algorithm == HashAlgorithm.SHA512:
                h = hmac.new(key_bytes, data_bytes, hashlib.sha512)
            elif algorithm == HashAlgorithm.BLAKE2B:
                h = hmac.new(key_bytes, data_bytes, hashlib.blake2b)
            elif algorithm == HashAlgorithm.MD5:
                h = hmac.new(key_bytes, data_bytes, hashlib.md5)
            else:
                raise IntegrationException(f"Unsupported HMAC algorithm: {algorithm}")
            
            return h.hexdigest()
        
        except Exception as e:
            self.logger.error(f"HMAC failed: {str(e)}")
            raise IntegrationException(f"HMAC failed: {str(e)}")


class DataMasker:
    """
    Data masker for sensitive data protection.
    
    Handles various data masking techniques.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def mask(self, data: str, masking_type: MaskingType = MaskingType.FULL,
             mask_char: str = '*', visible_chars: int = 4) -> str:
        """
        Mask sensitive data.
        
        Args:
            data: Data to mask
            masking_type: Type of masking
            mask_char: Character to use for masking
            visible_chars: Number of visible characters
            
        Returns:
            Masked data
        """
        if not data:
            return data
        
        try:
            if masking_type == MaskingType.FULL:
                return mask_char * len(data)
            
            elif masking_type == MaskingType.PARTIAL:
                if len(data) <= visible_chars:
                    return data
                return data[:visible_chars] + mask_char * (len(data) - visible_chars)
            
            elif masking_type == MaskingType.EMAIL:
                return self._mask_email(data, mask_char)
            
            elif masking_type == MaskingType.PHONE:
                return self._mask_phone(data, mask_char)
            
            elif masking_type == MaskingType.CREDIT_CARD:
                return self._mask_credit_card(data, mask_char)
            
            else:
                return mask_char * len(data)
        
        except Exception as e:
            self.logger.error(f"Masking failed: {str(e)}")
            return mask_char * len(data)
    
    def _mask_email(self, email: str, mask_char: str) -> str:
        """Mask email address."""
        if '@' not in email:
            return mask_char * len(email)
        
        local, domain = email.split('@', 1)
        
        if len(local) <= 2:
            masked_local = mask_char * len(local)
        else:
            masked_local = local[0] + mask_char * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    def _mask_phone(self, phone: str, mask_char: str) -> str:
        """Mask phone number."""
        # Remove non-digit characters
        digits = ''.join(c for c in phone if c.isdigit())
        
        if len(digits) <= 4:
            return mask_char * len(phone)
        
        # Show last 4 digits
        masked = mask_char * (len(digits) - 4) + digits[-4]
        
        # Reformat with original non-digit characters
        result = ''
        digit_index = 0
        for char in phone:
            if char.isdigit():
                result += masked[digit_index]
                digit_index += 1
            else:
                result += char
        
        return result
    
    def _mask_credit_card(self, card: str, mask_char: str) -> str:
        """Mask credit card number."""
        # Remove non-digit characters
        digits = ''.join(c for c in card if c.isdigit())
        
        if len(digits) != 16:
            return mask_char * len(card)
        
        # Show last 4 digits
        masked = mask_char * 12 + digits[-4]
        
        # Reformat with original non-digit characters
        result = ''
        digit_index = 0
        for char in card:
            if char.isdigit():
                result += masked[digit_index]
                digit_index += 1
            else:
                result += char
        
        return result


class Tokenizer:
    """
    Data tokenizer for tokenization.
    
    Handles tokenization and detokenization operations.
    """
    
    def __init__(self, encryptor: DataEncryptor):
        self.encryptor = encryptor
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def tokenize(self, data: Union[str, bytes], token_type: str = "default") -> str:
        """
        Tokenize data.
        
        Args:
            data: Data to tokenize
            token_type: Token type for classification
            
        Returns:
            Token string
        """
        try:
            # Encrypt data
            encrypted_data = self.encryptor.encrypt(data)
            
            # Create token
            token_data = {
                'type': token_type,
                'encrypted': encrypted_data.to_base64(),
                'created_at': timezone.now().isoformat()
            }
            
            # Encode token
            token = base64.b64encode(json.dumps(token_data).encode()).decode()
            
            self.logger.debug(f"Tokenized data: {token_type}")
            return token
        
        except Exception as e:
            self.logger.error(f"Tokenization failed: {str(e)}")
            raise IntegrationException(f"Tokenization failed: {str(e)}")
    
    def detokenize(self, token: str) -> Union[str, bytes, Dict[str, Any]]:
        """
        Detokenize data.
        
        Args:
            token: Token string
            
        Returns:
            Original data
        """
        try:
            # Decode token
            token_data = json.loads(base64.b64decode(token.encode()).decode())
            
            # Decrypt data
            encrypted_data = EncryptedData.from_base64(token_data['encrypted'])
            return self.encryptor.decrypt(encrypted_data)
        
        except Exception as e:
            self.logger.error(f"Detokenization failed: {str(e)}")
            raise IntegrationException(f"Detokenization failed: {str(e)}")


# Global instances
key_manager = KeyManager()
data_encryptor = DataEncryptor(key_manager)
data_hasher = DataHasher()
data_masker = DataMasker()
tokenizer = Tokenizer(data_encryptor)


# Convenience functions
def encrypt_data(data: Union[str, bytes, Dict[str, Any]], key_id: str = None) -> EncryptedData:
    """Encrypt data."""
    return data_encryptor.encrypt(data, key_id)


def decrypt_data(encrypted_data: EncryptedData) -> Union[str, bytes, Dict[str, Any]]:
    """Decrypt data."""
    return data_encryptor.decrypt(encrypted_data)


def hash_data(data: Union[str, bytes], algorithm: HashAlgorithm = HashAlgorithm.SHA256,
               salt: bytes = None) -> str:
    """Hash data."""
    return data_hasher.hash(data, algorithm, salt)


def hmac_data(data: Union[str, bytes], key: Union[str, bytes],
              algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
    """HMAC data."""
    return data_hasher.hmac(data, key, algorithm)


def mask_sensitive_data(data: str, masking_type: MaskingType = MaskingType.FULL,
                        mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mask sensitive data."""
    return data_masker.mask(data, masking_type, mask_char, visible_chars)


def tokenize_data(data: Union[str, bytes], token_type: str = "default") -> str:
    """Tokenize data."""
    return tokenizer.tokenize(data, token_type)


def detokenize_data(token: str) -> Union[str, bytes, Dict[str, Any]]:
    """Detokenize data."""
    return tokenizer.detokenize(token)


def get_encryption_statistics() -> Dict[str, Any]:
    """Get encryption statistics."""
    return key_manager.get_key_statistics()


def rotate_encryption_key(key_id: str = None) -> EncryptionKey:
    """Rotate encryption key."""
    return key_manager.rotate_key(key_id)
