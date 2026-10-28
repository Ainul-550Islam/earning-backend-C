"""
Security Encryption Module
Advanced encryption and cryptographic operations
"""
import json

import logging
import os
import base64
import secrets
from typing import Dict, List, Any, Optional, Type, Union, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.encryption')


class EncryptionAlgorithm:
    """Encryption algorithms"""
    AES_256_GCM = 'aes_256_gcm'
    AES_256_CBC = 'aes_256_cbc'
    FERNET = 'fernet'
    RSA_OAEP = 'rsa_oaep'


class EncryptionKey:
    """Encryption key model"""
    
    def __init__(self, key_id: str, algorithm: str, key_data: bytes, 
                 created_at: datetime = None, expires_at: datetime = None):
        self.key_id = key_id
        self.algorithm = algorithm
        self.key_data = key_data
        self.created_at = created_at or timezone.now()
        self.expires_at = expires_at
    
    def is_expired(self) -> bool:
        """Check if key is expired"""
        if self.expires_at and self.expires_at <= timezone.now():
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'key_id': self.key_id,
            'algorithm': self.algorithm,
            'key_data': base64.b64encode(self.key_data).decode(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptionKey':
        """Create from dictionary"""
        return cls(
            key_id=data['key_id'],
            algorithm=data['algorithm'],
            key_data=base64.b64decode(data['key_data']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None
        )


class KeyManager:
    """Key management system"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.key_rotation_days = getattr(settings, 'SECURITY_KEY_ROTATION_DAYS', 90)
        self.master_key = self._get_or_create_master_key()
        self.current_key = None
        self.key_cache = {}
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master key"""
        cache_key = "encryption_master_key"
        master_key = cache.get(cache_key)
        
        if not master_key:
            # Generate new master key
            master_key = os.urandom(32)  # 256-bit key
            cache.set(cache_key, master_key, timeout=None)  # Never expire
            
            # Store in settings if needed (in production, use secure key storage)
            if not hasattr(settings, 'SECURITY_MASTER_KEY'):
                settings.SECURITY_MASTER_KEY = base64.b64encode(master_key).decode()
        
        return master_key
    
    def generate_key(self, algorithm: str = EncryptionAlgorithm.FERNET) -> EncryptionKey:
        """Generate new encryption key"""
        key_id = SecurityUtils.generate_uuid()
        
        if algorithm == EncryptionAlgorithm.FERNET:
            key_data = Fernet.generate_key()
        elif algorithm == EncryptionAlgorithm.AES_256_GCM:
            key_data = os.urandom(32)  # 256-bit key
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            key_data = os.urandom(32)  # 256-bit key
        elif algorithm == EncryptionAlgorithm.RSA_OAEP:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            key_data = private_key
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        expires_at = timezone.now() + timedelta(days=self.key_rotation_days)
        
        key = EncryptionKey(key_id, algorithm, key_data, expires_at=expires_at)
        
        # Cache the key
        self.key_cache[key_id] = key
        
        logger.info(f"Generated encryption key: {key_id}")
        return key
    
    def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Get encryption key by ID"""
        # Try cache first
        if key_id in self.key_cache:
            key = self.key_cache[key_id]
            if not key.is_expired():
                return key
            else:
                # Remove expired key from cache
                del self.key_cache[key_id]
        
        # Try to load from persistent storage
        key_data = self._load_key_from_storage(key_id)
        if key_data:
            key = EncryptionKey.from_dict(key_data)
            if not key.is_expired():
                self.key_cache[key_id] = key
                return key
        
        return None
    
    def get_current_key(self, algorithm: str = EncryptionAlgorithm.FERNET) -> EncryptionKey:
        """Get current encryption key"""
        cache_key = f"current_key_{algorithm}"
        current_key_id = cache.get(cache_key)
        
        if current_key_id:
            key = self.get_key(current_key_id)
            if key and not key.is_expired():
                return key
        
        # Generate new key
        key = self.generate_key(algorithm)
        cache.set(cache_key, key.key_id, timeout=self.cache_timeout)
        return key
    
    def rotate_key(self, algorithm: str = EncryptionAlgorithm.FERNET) -> EncryptionKey:
        """Rotate encryption key"""
        # Generate new key
        new_key = self.generate_key(algorithm)
        
        # Update current key
        cache_key = f"current_key_{algorithm}"
        cache.set(cache_key, new_key.key_id, timeout=self.cache_timeout)
        
        logger.info(f"Rotated encryption key for {algorithm}")
        return new_key
    
    def _load_key_from_storage(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Load key from persistent storage"""
        # This would typically load from database or secure storage
        # For now, return None (keys are cached only)
        return None
    
    def _store_key_to_storage(self, key: EncryptionKey):
        """Store key to persistent storage"""
        # This would typically store to database or secure storage
        # For now, just cache
        pass
    
    def cleanup_expired_keys(self):
        """Clean up expired keys"""
        expired_keys = []
        
        for key_id, key in self.key_cache.items():
            if key.is_expired():
                expired_keys.append(key_id)
        
        for key_id in expired_keys:
            del self.key_cache[key_id]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired keys")
        return len(expired_keys)


class AESEncryption:
    """AES encryption implementation"""
    
    def __init__(self, key: bytes, algorithm: str = EncryptionAlgorithm.AES_256_GCM):
        self.key = key
        self.algorithm = algorithm
        self.backend = default_backend()
    
    def encrypt(self, plaintext: bytes) -> Dict[str, Any]:
        """Encrypt data"""
        if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._encrypt_gcm(plaintext)
        elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self._encrypt_cbc(plaintext)
        else:
            raise ValueError(f"Unsupported AES algorithm: {self.algorithm}")
    
    def decrypt(self, ciphertext: bytes, iv: bytes, tag: bytes = None) -> bytes:
        """Decrypt data"""
        if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._decrypt_gcm(ciphertext, iv, tag)
        elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self._decrypt_cbc(ciphertext, iv)
        else:
            raise ValueError(f"Unsupported AES algorithm: {self.algorithm}")
    
    def _encrypt_gcm(self, plaintext: bytes) -> Dict[str, Any]:
        """Encrypt using AES-GCM"""
        iv = os.urandom(12)  # 96-bit IV for GCM
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'iv': base64.b64encode(iv).decode(),
            'tag': base64.b64encode(encryptor.tag).decode()
        }
    
    def _decrypt_gcm(self, ciphertext: bytes, iv: bytes, tag: bytes) -> bytes:
        """Decrypt using AES-GCM"""
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(iv, tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext
    
    def _encrypt_cbc(self, plaintext: bytes) -> Dict[str, Any]:
        """Encrypt using AES-CBC"""
        iv = os.urandom(16)  # 128-bit IV for CBC
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        
        # Pad plaintext
        pad_length = 16 - (len(plaintext) % 16)
        padded_plaintext = plaintext + bytes([pad_length] * pad_length)
        
        ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()
        
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'iv': base64.b64encode(iv).decode()
        }
    
    def _decrypt_cbc(self, ciphertext: bytes, iv: bytes) -> bytes:
        """Decrypt using AES-CBC"""
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding
        pad_length = padded_plaintext[-1]
        plaintext = padded_plaintext[:-pad_length]
        
        return plaintext


class RSAEncryption:
    """RSA encryption implementation"""
    
    def __init__(self, private_key=None, public_key=None):
        self.backend = default_backend()
        self.private_key = private_key
        self.public_key = public_key
        
        # Generate key pair if not provided
        if not self.private_key and not self.public_key:
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=self.backend
            )
            self.public_key = self.private_key.public_key()
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt with public key"""
        if not self.public_key:
            raise ValueError("Public key not available")
        
        ciphertext = self.public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return base64.b64encode(ciphertext)
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt with private key"""
        if not self.private_key:
            raise ValueError("Private key not available")
        
        ciphertext = base64.b64decode(ciphertext)
        
        plaintext = self.private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return plaintext
    
    def sign(self, data: bytes) -> bytes:
        """Sign data with private key"""
        if not self.private_key:
            raise ValueError("Private key not available")
        
        signature = self.private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature)
    
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature with public key"""
        if not self.public_key:
            raise ValueError("Public key not available")
        
        try:
            signature = base64.b64decode(signature)
            
            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
        except Exception:
            return False
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format"""
        if not self.public_key:
            raise ValueError("Public key not available")
        
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return pem.decode()
    
    def get_private_key_pem(self) -> str:
        """Get private key in PEM format"""
        if not self.private_key:
            raise ValueError("Private key not available")
        
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return pem.decode()


class EncryptionService:
    """Main encryption service"""
    
    def __init__(self):
        self.key_manager = KeyManager()
        self.cache_timeout = 300  # 5 minutes
    
    def encrypt_sensitive_data(self, data: str, algorithm: str = EncryptionAlgorithm.FERNET) -> Dict[str, Any]:
        """Encrypt sensitive data"""
        try:
            # Get current key
            key = self.key_manager.get_current_key(algorithm)
            
            # Convert to bytes
            plaintext = data.encode('utf-8')
            
            # Encrypt based on algorithm
            if algorithm == EncryptionAlgorithm.FERNET:
                fernet = Fernet(key.key_data)
                ciphertext = fernet.encrypt(plaintext)
                
                return {
                    'ciphertext': base64.b64encode(ciphertext).decode(),
                    'key_id': key.key_id,
                    'algorithm': algorithm,
                    'encrypted_at': timezone.now().isoformat()
                }
            
            elif algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                aes = AESEncryption(key.key_data, algorithm)
                result = aes.encrypt(plaintext)
                
                return {
                    'ciphertext': result['ciphertext'],
                    'iv': result['iv'],
                    'tag': result.get('tag'),
                    'key_id': key.key_id,
                    'algorithm': algorithm,
                    'encrypted_at': timezone.now().isoformat()
                }
            
            elif algorithm == EncryptionAlgorithm.RSA_OAEP:
                rsa = RSAEncryption(private_key=key.key_data)
                ciphertext = rsa.encrypt(plaintext)
                
                return {
                    'ciphertext': ciphertext.decode(),
                    'key_id': key.key_id,
                    'algorithm': algorithm,
                    'encrypted_at': timezone.now().isoformat()
                }
            
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: Dict[str, Any]) -> str:
        """Decrypt sensitive data"""
        try:
            # Get key
            key = self.key_manager.get_key(encrypted_data['key_id'])
            if not key:
                raise ValueError(f"Key not found: {encrypted_data['key_id']}")
            
            algorithm = encrypted_data['algorithm']
            ciphertext = base64.b64decode(encrypted_data['ciphertext'])
            
            # Decrypt based on algorithm
            if algorithm == EncryptionAlgorithm.FERNET:
                fernet = Fernet(key.key_data)
                plaintext = fernet.decrypt(ciphertext)
                return plaintext.decode('utf-8')
            
            elif algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                aes = AESEncryption(key.key_data, algorithm)
                iv = base64.b64decode(encrypted_data['iv'])
                tag = base64.b64decode(encrypted_data['tag']) if 'tag' in encrypted_data else None
                
                plaintext = aes.decrypt(ciphertext, iv, tag)
                return plaintext.decode('utf-8')
            
            elif algorithm == EncryptionAlgorithm.RSA_OAEP:
                rsa = RSAEncryption(private_key=key.key_data)
                plaintext = rsa.decrypt(ciphertext)
                return plaintext.decode('utf-8')
            
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def encrypt_field(self, field_value: str, field_name: str = None) -> str:
        """Encrypt a field value (for database storage)"""
        if not field_value:
            return field_value
        
        try:
            encrypted_data = self.encrypt_sensitive_data(field_value)
            
            # Store as JSON string
            return json.dumps(encrypted_data)
        
        except Exception as e:
            logger.error(f"Field encryption error: {e}")
            return field_value
    
    def decrypt_field(self, encrypted_field: str) -> str:
        """Decrypt a field value (from database storage)"""
        if not encrypted_field or not encrypted_field.startswith('{'):
            return encrypted_field
        
        try:
            encrypted_data = json.loads(encrypted_field)
            return self.decrypt_sensitive_data(encrypted_data)
        
        except Exception as e:
            logger.error(f"Field decryption error: {e}")
            return encrypted_field
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """Generate RSA key pair"""
        rsa = RSAEncryption()
        
        return rsa.get_public_key_pem(), rsa.get_private_key_pem()
    
    def sign_data(self, data: str, private_key_pem: str) -> str:
        """Sign data with RSA private key"""
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None,
                backend=default_backend()
            )
            
            rsa = RSAEncryption(private_key=private_key)
            signature = rsa.sign(data.encode('utf-8'))
            
            return signature.decode()
        
        except Exception as e:
            logger.error(f"Data signing error: {e}")
            raise
    
    def verify_signature(self, data: str, signature: str, public_key_pem: str) -> bool:
        """Verify signature with RSA public key"""
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend()
            )
            
            rsa = RSAEncryption(public_key=public_key)
            return rsa.verify(data.encode('utf-8'), signature.encode())
        
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with PBKDF2"""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        hashed_password = kdf.derive(password.encode())
        
        return (
            base64.b64encode(hashed_password).decode(),
            base64.b64encode(salt).decode()
        )
    
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """Verify password hash"""
        try:
            salt_bytes = base64.b64decode(salt)
            hashed_bytes = base64.b64decode(hashed_password)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
                backend=default_backend()
            )
            
            return kdf.verify(password.encode(), hashed_bytes) is None
        
        except Exception:
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate secure random token"""
        return secrets.token_urlsafe(length)
    
    def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption statistics"""
        return {
            'total_keys': len(self.key_manager.key_cache),
            'current_key_fernet': self.key_manager.get_current_key(EncryptionAlgorithm.FERNET).key_id,
            'current_key_aes': self.key_manager.get_current_key(EncryptionAlgorithm.AES_256_GCM).key_id,
            'key_rotation_days': self.key_manager.key_rotation_days
        }


# Global encryption service
encryption_service = EncryptionService()


# Export classes and utilities
__all__ = [
    'EncryptionAlgorithm',
    'EncryptionKey',
    'KeyManager',
    'AESEncryption',
    'RSAEncryption',
    'EncryptionService',
    'encryption_service'
]