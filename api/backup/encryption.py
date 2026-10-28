"""
🔐 Backup Encryption Module

This module provides comprehensive encryption capabilities for the backup system.
It includes multiple encryption algorithms, key management, secure storage,
and encryption utilities to ensure data security and compliance.

Features:
- Multiple encryption algorithms (AES-256-GCM, ChaCha20-Poly1305, Fernet)
- Secure key generation and management
- Key derivation and rotation
- Encryption metadata tracking
- Secure key storage
- Encryption performance monitoring
- Compliance-ready encryption
"""

import logging
import os
import base64
import secrets
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import models

# Import backup models
from .models import Backup, BackupEncryption

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """Enumeration of supported encryption algorithms."""
    AES_256_GCM = "AES-256-GCM"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"
    FERNET = "Fernet"


class KeyDerivationMethod(Enum):
    """Enumeration of key derivation methods."""
    PBKDF2 = "PBKDF2"
    HKDF = "HKDF"
    DIRECT = "DIRECT"


class EncryptionMode(Enum):
    """Enumeration of encryption modes."""
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


@dataclass
class EncryptionConfig:
    """Configuration for encryption operations."""
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_derivation: KeyDerivationMethod = KeyDerivationMethod.PBKDF2
    iterations: int = 100000  # PBKDF2 iterations
    salt_length: int = 32
    iv_length: int = 12  # GCM recommended IV length
    tag_length: int = 16  # GCM authentication tag length
    compress_before: bool = True
    delete_original: bool = False
    backup_keys: bool = True
    key_rotation_days: int = 90


@dataclass
class EncryptionResult:
    """Result of encryption operation."""
    success: bool
    encrypted_data: Optional[bytes] = None
    encryption_key: Optional[bytes] = None
    salt: Optional[bytes] = None
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    algorithm: Optional[EncryptionAlgorithm] = None
    original_size: int = 0
    encrypted_size: int = 0
    compression_ratio: float = 0.0
    encryption_time_ms: float = 0.0
    error: Optional[Exception] = None


@dataclass
class DecryptionResult:
    """Result of decryption operation."""
    success: bool
    decrypted_data: Optional[bytes] = None
    original_size: int = 0
    decrypted_size: int = 0
    decryption_time_ms: float = 0.0
    integrity_verified: bool = False
    error: Optional[Exception] = None


@dataclass
class EncryptionKey:
    """Encryption key with metadata."""
    key_id: str
    key_bytes: bytes
    algorithm: EncryptionAlgorithm
    created_at: datetime = field(default_factory=timezone.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class KeyManager:
    """Manages encryption keys with secure storage and rotation."""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        self.config = config or EncryptionConfig()
        self.keys: Dict[str, EncryptionKey] = {}
        self.key_storage_path = getattr(settings, 'BACKUP_KEY_STORAGE_PATH', '/tmp/backup_keys')
        self.master_key = self._get_or_create_master_key()
        
        # Ensure key storage directory exists
        os.makedirs(self.key_storage_path, exist_ok=True)
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master key for key encryption."""
        master_key_file = os.path.join(self.key_storage_path, 'master.key')
        
        if os.path.exists(master_key_file):
            try:
                with open(master_key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read master key: {e}")
        
        # Create new master key
        master_key = os.urandom(32)  # 256-bit master key
        
        try:
            with open(master_key_file, 'wb') as f:
                f.write(master_key)
            # Set secure permissions
            os.chmod(master_key_file, 0o600)
        except Exception as e:
            logger.error(f"Failed to save master key: {e}")
        
        return master_key
    
    def generate_key(self, algorithm: Optional[EncryptionAlgorithm] = None) -> EncryptionKey:
        """Generate a new encryption key."""
        algorithm = algorithm or self.config.algorithm
        
        # Generate key based on algorithm
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            key_bytes = os.urandom(32)  # 256-bit key
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            key_bytes = os.urandom(32)  # 256-bit key
        elif algorithm == EncryptionAlgorithm.FERNET:
            key_bytes = Fernet.generate_key()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Create key object
        key_id = secrets.token_urlsafe(16)
        expires_at = timezone.now() + timedelta(days=self.config.key_rotation_days)
        
        encryption_key = EncryptionKey(
            key_id=key_id,
            key_bytes=key_bytes,
            algorithm=algorithm,
            expires_at=expires_at
        )
        
        # Store key
        self.keys[key_id] = encryption_key
        
        # Persist key if backup is enabled
        if self.config.backup_keys:
            self._store_key(encryption_key)
        
        return encryption_key
    
    def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Get encryption key by ID."""
        if key_id in self.keys:
            return self.keys[key_id]
        
        # Try to load from storage
        key = self._load_key(key_id)
        if key:
            self.keys[key_id] = key
        
        return key
    
    def rotate_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Rotate an encryption key."""
        old_key = self.get_key(key_id)
        if not old_key:
            return None
        
        # Generate new key
        new_key = self.generate_key(old_key.algorithm)
        
        # Mark old key as inactive
        old_key.is_active = False
        old_key.expires_at = timezone.now()
        
        # Update metadata
        new_key.metadata['rotated_from'] = key_id
        new_key.metadata['rotation_reason'] = 'scheduled'
        
        return new_key
    
    def _store_key(self, key: EncryptionKey) -> bool:
        """Store encrypted key to file."""
        try:
            key_file = os.path.join(self.key_storage_path, f"{key.key_id}.key")
            
            # Encrypt key with master key
            fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
            encrypted_key = fernet.encrypt(key.key_bytes)
            
            # Store key data
            key_data = {
                'key_id': key.key_id,
                'algorithm': key.algorithm.value,
                'created_at': key.created_at.isoformat(),
                'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                'is_active': key.is_active,
                'usage_count': key.usage_count,
                'last_used': key.last_used.isoformat() if key.last_used else None,
                'metadata': key.metadata,
                'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8')
            }
            
            with open(key_file, 'w') as f:
                import json
                json.dump(key_data, f, indent=2)
            
            # Set secure permissions
            os.chmod(key_file, 0o600)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store key {key.key_id}: {e}")
            return False
    
    def _load_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Load encrypted key from file."""
        try:
            key_file = os.path.join(self.key_storage_path, f"{key_id}.key")
            
            if not os.path.exists(key_file):
                return None
            
            with open(key_file, 'r') as f:
                import json
                key_data = json.load(f)
            
            # Decrypt key
            fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
            encrypted_key = base64.b64decode(key_data['encrypted_key'].encode('utf-8'))
            key_bytes = fernet.decrypt(encrypted_key)
            
            # Reconstruct key object
            encryption_key = EncryptionKey(
                key_id=key_data['key_id'],
                key_bytes=key_bytes,
                algorithm=EncryptionAlgorithm(key_data['algorithm']),
                created_at=datetime.fromisoformat(key_data['created_at']),
                expires_at=datetime.fromisoformat(key_data['expires_at']) if key_data['expires_at'] else None,
                is_active=key_data['is_active'],
                usage_count=key_data['usage_count'],
                last_used=datetime.fromisoformat(key_data['last_used']) if key_data['last_used'] else None,
                metadata=key_data['metadata']
            )
            
            return encryption_key
            
        except Exception as e:
            logger.error(f"Failed to load key {key_id}: {e}")
            return None
    
    def cleanup_expired_keys(self) -> int:
        """Clean up expired keys."""
        expired_count = 0
        now = timezone.now()
        
        for key_id, key in list(self.keys.items()):
            if key.expires_at and key.expires_at < now:
                # Remove from memory
                del self.keys[key_id]
                
                # Remove from storage
                key_file = os.path.join(self.key_storage_path, f"{key_id}.key")
                if os.path.exists(key_file):
                    os.remove(key_file)
                
                expired_count += 1
        
        return expired_count
    
    def get_active_keys(self) -> List[EncryptionKey]:
        """Get all active keys."""
        return [key for key in self.keys.values() if key.is_active]


class BackupEncryptor:
    """Main backup encryption engine."""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        self.config = config or EncryptionConfig()
        self.key_manager = KeyManager(self.config)
        self.backend = default_backend()
    
    def encrypt_data(self, data: Union[bytes, str], 
                    key: Optional[EncryptionKey] = None) -> EncryptionResult:
        """Encrypt data with specified algorithm."""
        start_time = timezone.now()
        
        try:
            # Convert string to bytes if needed
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            original_size = len(data)
            
            # Generate key if not provided
            if key is None:
                key = self.key_manager.generate_key()
            
            # Compress data if configured
            if self.config.compress_before:
                import gzip
                compressed_data = gzip.compress(data)
                compression_ratio = (1 - len(compressed_data) / len(data)) * 100
            else:
                compressed_data = data
                compression_ratio = 0.0
            
            # Encrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                result = self._encrypt_aes_gcm(compressed_data, key)
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                result = self._encrypt_chacha20(compressed_data, key)
            elif key.algorithm == EncryptionAlgorithm.FERNET:
                result = self._encrypt_fernet(compressed_data, key)
            else:
                raise ValueError(f"Unsupported algorithm: {key.algorithm}")
            
            # Update result metadata
            if result.success:
                result.original_size = original_size
                result.encrypted_size = len(result.encrypted_data) if result.encrypted_data else 0
                result.compression_ratio = compression_ratio
                result.algorithm = key.algorithm
                
                # Update key usage
                key.usage_count += 1
                key.last_used = timezone.now()
            
            # Calculate encryption time
            encryption_time = (timezone.now() - start_time).total_seconds() * 1000
            result.encryption_time_ms = encryption_time
            
            return result
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return EncryptionResult(
                success=False,
                error=e,
                original_size=len(data) if isinstance(data, bytes) else len(data.encode('utf-8')),
                encryption_time_ms=(timezone.now() - start_time).total_seconds() * 1000
            )
    
    def decrypt_data(self, encrypted_data: bytes, key: EncryptionKey,
                    iv: Optional[bytes] = None, tag: Optional[bytes] = None) -> DecryptionResult:
        """Decrypt data with specified key."""
        start_time = timezone.now()
        
        try:
            # Decrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                result = self._decrypt_aes_gcm(encrypted_data, key, iv, tag)
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                result = self._decrypt_chacha20(encrypted_data, key, iv, tag)
            elif key.algorithm == EncryptionAlgorithm.FERNET:
                result = self._decrypt_fernet(encrypted_data, key)
            else:
                raise ValueError(f"Unsupported algorithm: {key.algorithm}")
            
            # Update result metadata
            if result.success:
                # Decompress if needed
                if self.config.compress_before:
                    try:
                        import gzip
                        result.decrypted_data = gzip.decompress(result.decrypted_data)
                    except Exception:
                        pass  # Data might not be compressed
                
                result.decrypted_size = len(result.decrypted_data) if result.decrypted_data else 0
                result.integrity_verified = True
                
                # Update key usage
                key.usage_count += 1
                key.last_used = timezone.now()
            
            # Calculate decryption time
            decryption_time = (timezone.now() - start_time).total_seconds() * 1000
            result.decryption_time_ms = decryption_time
            
            return result
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return DecryptionResult(
                success=False,
                error=e,
                decryption_time_ms=(timezone.now() - start_time).total_seconds() * 1000
            )
    
    def _encrypt_aes_gcm(self, data: bytes, key: EncryptionKey) -> EncryptionResult:
        """Encrypt data using AES-256-GCM."""
        try:
            # Generate IV
            iv = os.urandom(self.config.iv_length)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key.key_bytes),
                modes.GCM(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Encrypt data
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            
            # Get authentication tag
            tag = encryptor.tag
            
            return EncryptionResult(
                success=True,
                encrypted_data=encrypted_data,
                iv=iv,
                tag=tag
            )
            
        except Exception as e:
            return EncryptionResult(success=False, error=e)
    
    def _decrypt_aes_gcm(self, encrypted_data: bytes, key: EncryptionKey,
                        iv: Optional[bytes], tag: Optional[bytes]) -> DecryptionResult:
        """Decrypt data using AES-256-GCM."""
        try:
            if not iv or not tag:
                raise ValueError("IV and tag are required for AES-GCM decryption")
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key.key_bytes),
                modes.GCM(iv, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt data
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            return DecryptionResult(
                success=True,
                decrypted_data=decrypted_data
            )
            
        except Exception as e:
            return DecryptionResult(success=False, error=e)
    
    def _encrypt_chacha20(self, data: bytes, key: EncryptionKey) -> EncryptionResult:
        """Encrypt data using ChaCha20-Poly1305."""
        try:
            # Generate nonce
            nonce = os.urandom(12)  # ChaCha20 requires 12-byte nonce
            
            # Create cipher
            cipher = Cipher(
                algorithms.ChaCha20(key.key_bytes, nonce),
                modes.Poly1305(b''),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Encrypt data
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            
            # Get tag
            tag = encryptor.tag
            
            return EncryptionResult(
                success=True,
                encrypted_data=encrypted_data,
                iv=nonce,  # Store nonce as IV
                tag=tag
            )
            
        except Exception as e:
            return EncryptionResult(success=False, error=e)
    
    def _decrypt_chacha20(self, encrypted_data: bytes, key: EncryptionKey,
                         iv: Optional[bytes], tag: Optional[bytes]) -> DecryptionResult:
        """Decrypt data using ChaCha20-Poly1305."""
        try:
            if not iv or not tag:
                raise ValueError("Nonce and tag are required for ChaCha20-Poly1305 decryption")
            
            # Create cipher
            cipher = Cipher(
                algorithms.ChaCha20(key.key_bytes, iv),
                modes.Poly1305(tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt data
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            return DecryptionResult(
                success=True,
                decrypted_data=decrypted_data
            )
            
        except Exception as e:
            return DecryptionResult(success=False, error=e)
    
    def _encrypt_fernet(self, data: bytes, key: EncryptionKey) -> EncryptionResult:
        """Encrypt data using Fernet."""
        try:
            fernet = Fernet(key.key_bytes)
            encrypted_data = fernet.encrypt(data)
            
            return EncryptionResult(
                success=True,
                encrypted_data=encrypted_data
            )
            
        except Exception as e:
            return EncryptionResult(success=False, error=e)
    
    def _decrypt_fernet(self, encrypted_data: bytes, key: EncryptionKey) -> DecryptionResult:
        """Decrypt data using Fernet."""
        try:
            fernet = Fernet(key.key_bytes)
            decrypted_data = fernet.decrypt(encrypted_data)
            
            return DecryptionResult(
                success=True,
                decrypted_data=decrypted_data
            )
            
        except Exception as e:
            return DecryptionResult(success=False, error=e)
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None,
                    key: Optional[EncryptionKey] = None) -> EncryptionResult:
        """Encrypt a file."""
        try:
            # Read file
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Encrypt data
            result = self.encrypt_data(data, key)
            
            if result.success and output_path:
                # Write encrypted file
                with open(output_path, 'wb') as f:
                    f.write(result.encrypted_data)
                
                # Delete original if configured
                if self.config.delete_original:
                    os.remove(file_path)
            
            return result
            
        except Exception as e:
            return EncryptionResult(success=False, error=e)
    
    def decrypt_file(self, encrypted_file_path: str, output_path: str,
                    key: EncryptionKey, iv: Optional[bytes] = None,
                    tag: Optional[bytes] = None) -> DecryptionResult:
        """Decrypt a file."""
        try:
            # Read encrypted file
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt data
            result = self.decrypt_data(encrypted_data, key, iv, tag)
            
            if result.success:
                # Write decrypted file
                with open(output_path, 'wb') as f:
                    f.write(result.decrypted_data)
            
            return result
            
        except Exception as e:
            return DecryptionResult(success=False, error=e)
    
    def encrypt_backup(self, backup: Backup) -> bool:
        """Encrypt a backup and update the model."""
        try:
            # Get backup file
            if not backup.file_path or not os.path.exists(backup.file_path):
                logger.error(f"Backup file not found: {backup.file_path}")
                return False
            
            # Generate encryption key
            key = self.key_manager.generate_key()
            
            # Encrypt file
            encrypted_path = f"{backup.file_path}.enc"
            result = self.encrypt_file(backup.file_path, encrypted_path, key)
            
            if result.success:
                # Update backup model
                backup.is_encrypted = True
                backup.file_path = encrypted_path
                backup.original_size = result.original_size
                backup.file_size = result.encrypted_size
                backup.encryption_method = key.algorithm.value
                backup.encryption_time = timezone.now()
                backup.save()
                
                # Create encryption record
                BackupEncryption.objects.create(
                    backup=backup,
                    algorithm=key.algorithm.value,
                    key_hash=hashlib.sha256(key.key_bytes).hexdigest(),
                    is_encrypted=True,
                    encryption_key=base64.b64encode(key.key_bytes).decode('utf-8'),
                    salt=result.salt,
                    iv=result.iv,
                    tag=result.tag
                )
                
                logger.info(f"Successfully encrypted backup {backup.backup_id}")
                return True
            else:
                logger.error(f"Failed to encrypt backup {backup.backup_id}: {result.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error encrypting backup {backup.backup_id}: {e}")
            return False
    
    def decrypt_backup(self, backup: Backup, output_path: Optional[str] = None) -> bool:
        """Decrypt a backup."""
        try:
            # Get encryption record
            encryption_info = BackupEncryption.objects.filter(backup=backup).first()
            if not encryption_info:
                logger.error(f"No encryption info found for backup {backup.backup_id}")
                return False
            
            # Get key
            key = self.key_manager.get_key(encryption_info.key_hash)
            if not key:
                logger.error(f"Encryption key not found for backup {backup.backup_id}")
                return False
            
            # Determine output path
            if not output_path:
                output_path = backup.file_path.replace('.enc', '')
            
            # Decrypt file
            iv = encryption_info.iv
            tag = encryption_info.tag
            result = self.decrypt_file(backup.file_path, output_path, key, 
                                    iv.encode('utf-8') if iv else None,
                                    tag.encode('utf-8') if tag else None)
            
            if result.success:
                logger.info(f"Successfully decrypted backup {backup.backup_id}")
                return True
            else:
                logger.error(f"Failed to decrypt backup {backup.backup_id}: {result.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error decrypting backup {backup.backup_id}: {e}")
            return False
    
    def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption statistics."""
        active_keys = self.key_manager.get_active_keys()
        
        # Get encryption records
        total_encrypted = BackupEncryption.objects.filter(is_encrypted=True).count()
        
        # Algorithm distribution
        algo_dist = {}
        for encryption in BackupEncryption.objects.all():
            algo = encryption.algorithm
            algo_dist[algo] = algo_dist.get(algo, 0) + 1
        
        return {
            'active_keys': len(active_keys),
            'total_encrypted_backups': total_encrypted,
            'algorithm_distribution': algo_dist,
            'key_rotation_days': self.config.key_rotation_days,
            'compression_enabled': self.config.compress_before,
            'backup_keys_enabled': self.config.backup_keys
        }


class EncryptionValidator:
    """Validates encryption configuration and operations."""
    
    @staticmethod
    def validate_algorithm(algorithm: EncryptionAlgorithm) -> bool:
        """Validate encryption algorithm."""
        return algorithm in EncryptionAlgorithm
    
    @staticmethod
    def validate_key_length(key: bytes, algorithm: EncryptionAlgorithm) -> bool:
        """Validate key length for algorithm."""
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            return len(key) == 32
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            return len(key) == 32
        elif algorithm == EncryptionAlgorithm.FERNET:
            return len(key) == 44  # Fernet key is base64 encoded
        return False
    
    @staticmethod
    def validate_encryption_integrity(original_data: bytes, 
                                     decrypted_data: bytes) -> bool:
        """Validate encryption/decryption integrity."""
        return original_data == decrypted_data
    
    @staticmethod
    def validate_key_strength(key: bytes) -> Dict[str, Any]:
        """Validate key strength."""
        strength_score = 0
        issues = []
        
        # Check length
        if len(key) >= 32:
            strength_score += 40
        elif len(key) >= 24:
            strength_score += 30
        elif len(key) >= 16:
            strength_score += 20
        else:
            issues.append("Key length is too short")
        
        # Check entropy (simplified)
        entropy = len(set(key)) / len(key) * 100
        if entropy >= 80:
            strength_score += 30
        elif entropy >= 60:
            strength_score += 20
        elif entropy >= 40:
            strength_score += 10
        else:
            issues.append("Key has low entropy")
        
        # Check for patterns (simplified)
        if len(set(key[:8])) < 4:
            issues.append("Key contains repetitive patterns")
        
        # Determine strength level
        if strength_score >= 70:
            strength_level = "strong"
        elif strength_score >= 50:
            strength_level = "medium"
        else:
            strength_level = "weak"
        
        return {
            "strength_score": strength_score,
            "strength_level": strength_level,
            "entropy_percentage": entropy,
            "issues": issues
        }


# Global encryptor instance
_encryptor: Optional[BackupEncryptor] = None


def get_backup_encryptor() -> BackupEncryptor:
    """Get the global backup encryptor instance."""
    global _encryptor
    if _encryptor is None:
        _encryptor = BackupEncryptor()
    return _encryptor


def encrypt_data(data: Union[bytes, str], 
                algorithm: Optional[EncryptionAlgorithm] = None) -> EncryptionResult:
    """Convenience function to encrypt data."""
    encryptor = get_backup_encryptor()
    return encryptor.encrypt_data(data)


def decrypt_data(encrypted_data: bytes, key: EncryptionKey,
                iv: Optional[bytes] = None, tag: Optional[bytes] = None) -> DecryptionResult:
    """Convenience function to decrypt data."""
    encryptor = get_backup_encryptor()
    return encryptor.decrypt_data(encrypted_data, key, iv, tag)


def encrypt_backup(backup: Backup) -> bool:
    """Convenience function to encrypt a backup."""
    encryptor = get_backup_encryptor()
    return encryptor.encrypt_backup(backup)


def decrypt_backup(backup: Backup, output_path: Optional[str] = None) -> bool:
    """Convenience function to decrypt a backup."""
    encryptor = get_backup_encryptor()
    return encryptor.decrypt_backup(backup, output_path)


def get_encryption_stats() -> Dict[str, Any]:
    """Convenience function to get encryption statistics."""
    encryptor = get_backup_encryptor()
    return encryptor.get_encryption_stats()
