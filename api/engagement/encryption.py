# engagement/encryption.py
"""
Encryption system for engagement gamification.
Provides secure data encryption and decryption capabilities.
"""
from django.core.cache import cache
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import logging
import base64
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionProvider(ABC):
    """Base encryption provider class."""
    
    @abstractmethod
    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        pass
    
    @abstractmethod
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        pass
    
    @abstractmethod
    def generate_key(self) -> str:
        """Generate encryption key."""
        pass


class FernetProvider(EncryptionProvider):
    """Fernet encryption provider."""
    
    def __init__(self, key: str = None):
        self.key = key or self._get_or_generate_key()
        self.fernet = Fernet(self.key.encode())
    
    def encrypt(self, data: str) -> str:
        """Encrypt data using Fernet."""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            encrypted_data = self.fernet.encrypt(data)
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as exc:
            logger.error(f"Failed to encrypt data: {exc}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet."""
        try:
            if isinstance(encrypted_data, str):
                encrypted_data = base64.b64decode(encrypted_data.encode())
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return decrypted_data.decode()
            
        except Exception as exc:
            logger.error(f"Failed to decrypt data: {exc}")
            raise
    
    def generate_key(self) -> str:
        """Generate new Fernet key."""
        return Fernet.generate_key().decode()
    
    def _get_or_generate_key(self) -> str:
        """Get existing key or generate new one."""
        # Try to get from settings
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if key:
            return key
        
        # Try to get from environment
        key = os.environ.get('ENCRYPTION_KEY')
        if key:
            return key
        
        # Generate new key
        logger.warning("No encryption key found, generating new key")
        return self.generate_key()


class AESSProvider(EncryptionProvider):
    """AES encryption provider."""
    
    def __init__(self, key: str = None):
        self.key = key or self._get_or_generate_key()
        self.backend = default_backend()
    
    def encrypt(self, data: str) -> str:
        """Encrypt data using AES."""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            # Convert key to bytes
            key_bytes = self.key.encode()
            
            # Generate IV
            iv = os.urandom(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key_bytes),
                modes.CBC(iv),
                backend=self.backend
            )
            
            # Pad data
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data.encode()) + padder.finalize()
            
            # Encrypt
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Combine IV and encrypted data
            combined = iv + encrypted_data
            
            return base64.b64encode(combined).decode()
            
        except Exception as exc:
            logger.error(f"Failed to encrypt data with AES: {exc}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data using AES."""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            # Decode and split
            combined = base64.b64decode(encrypted_data.encode())
            iv = combined[:16]
            encrypted_data_bytes = combined[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key.encode()),
                modes.CBC(iv),
                backend=self.backend
            )
            
            # Decrypt
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_data_bytes) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data.decode()
            
        except Exception as exc:
            logger.error(f"Failed to decrypt data with AES: {exc}")
            raise
    
    def generate_key(self) -> str:
        """Generate new AES key."""
        return os.urandom(32).hex()
    
    def _get_or_generate_key(self) -> str:
        """Get existing key or generate new one."""
        # Try to get from settings
        key = getattr(settings, 'AES_ENCRYPTION_KEY', None)
        if key:
            return key
        
        # Try to get from environment
        key = os.environ.get('AES_ENCRYPTION_KEY')
        if key:
            return key
        
        # Generate new key
        logger.warning("No AES encryption key found, generating new key")
        return self.generate_key()


class EncryptionManager:
    """Manager for encryption operations."""
    
    def __init__(self, provider: EncryptionProvider = None):
        self.provider = provider or FernetProvider()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        if not data:
            return data
        
        try:
            return self.provider.encrypt(data)
        except Exception as exc:
            self.logger.error(f"Encryption failed: {exc}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        if not encrypted_data:
            return encrypted_data
        
        try:
            return self.provider.decrypt(encrypted_data)
        except Exception as exc:
            self.logger.error(f"Decryption failed: {exc}")
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt dictionary values."""
        encrypted_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    encrypted_data[key] = self.encrypt(value)
                except Exception:
                    encrypted_data[key] = value  # Fallback to original value
            else:
                encrypted_data[key] = value
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt dictionary values."""
        decrypted_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    decrypted_data[key] = self.decrypt(value)
                except Exception:
                    decrypted_data[key] = value  # Fallback to original value
            else:
                decrypted_data[key] = value
        
        return decrypted_data
    
    def encrypt_sensitive_fields(self, data: Dict[str, Any], 
                                 sensitive_fields: List[str]) -> Dict[str, Any]:
        """Encrypt only specified sensitive fields."""
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and isinstance(encrypted_data[field], str):
                try:
                    encrypted_data[field] = self.encrypt(encrypted_data[field])
                except Exception as exc:
                    self.logger.error(f"Failed to encrypt field {field}: {exc}")
        
        return encrypted_data
    
    def decrypt_sensitive_fields(self, data: Dict[str, Any], 
                                 sensitive_fields: List[str]) -> Dict[str, Any]:
        """Decrypt only specified sensitive fields."""
        decrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in decrypted_data and isinstance(decrypted_data[field], str):
                try:
                    decrypted_data[field] = self.decrypt(decrypted_data[field])
                except Exception as exc:
                    self.logger.error(f"Failed to decrypt field {field}: {exc}")
        
        return decrypted_data
    
    def generate_key(self) -> str:
        """Generate new encryption key."""
        return self.provider.generate_key()
    
    def rotate_key(self, old_key: str, new_key: str) -> bool:
        """Rotate encryption key."""
        try:
            # Create new provider with new key
            new_provider = self.provider.__class__(new_key)
            
            # Test new provider
            test_data = "test_data"
            encrypted = new_provider.encrypt(test_data)
            decrypted = new_provider.decrypt(encrypted)
            
            if decrypted == test_data:
                self.provider = new_provider
                return True
            else:
                return False
                
        except Exception as exc:
            self.logger.error(f"Key rotation failed: {exc}")
            return False


# Global encryption manager instance
encryption_manager = EncryptionManager()


# ── Encryption Utilities ─────────────────────────────────────────────────────

class EncryptionUtils:
    """Utility functions for encryption."""
    
    @staticmethod
    def hash_password(password: str, salt: str = None) -> str:
        """Hash password with salt."""
        try:
            if salt is None:
                salt = os.urandom(16).hex()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
                backend=default_backend()
            )
            
            hashed = kdf.derive(password.encode())
            return f"{salt}:{base64.b64encode(hashed).decode()}"
            
        except Exception as exc:
            logger.error(f"Password hashing failed: {exc}")
            raise
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            salt, hashed = hashed_password.split(':', 1)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
                backend=default_backend()
            )
            
            try:
                kdf.verify(password.encode(), base64.b64decode(hashed))
                return True
            except Exception:
                return False
                
        except Exception as exc:
            logger.error(f"Password verification failed: {exc}")
            return False
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate secure random token."""
        return base64.b64encode(os.urandom(length)).decode()
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
        """Mask sensitive data for logging."""
        if not data or len(data) <= visible_chars:
            return data
        
        visible_start = data[:visible_chars // 2]
        visible_end = data[-(visible_chars // 2):]
        masked_middle = mask_char * (len(data) - visible_chars)
        
        return visible_start + masked_middle + visible_end
    
    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """Secure string comparison to prevent timing attacks."""
        try:
            import hmac
            return hmac.compare_digest(a.encode(), b.encode())
        except Exception:
            return a == b


# ── Encryption Decorators ─────────────────────────────────────────────────────

def encrypt_field(field_name: str):
    """Decorator to encrypt field data."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, dict) and field_name in result:
                try:
                    result[field_name] = encryption_manager.encrypt(result[field_name])
                except Exception as exc:
                    logger.error(f"Failed to encrypt field {field_name}: {exc}")
            
            return result
        return wrapper
    return decorator


def decrypt_field(field_name: str):
    """Decorator to decrypt field data."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, dict) and field_name in result:
                try:
                    result[field_name] = encryption_manager.decrypt(result[field_name])
                except Exception as exc:
                    logger.error(f"Failed to decrypt field {field_name}: {exc}")
            
            return result
        return wrapper
    return decorator


def encrypt_sensitive_data(sensitive_fields: List[str]):
    """Decorator to encrypt multiple sensitive fields."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, dict):
                try:
                    result = encryption_manager.encrypt_sensitive_fields(result, sensitive_fields)
                except Exception as exc:
                    logger.error(f"Failed to encrypt sensitive fields: {exc}")
            
            return result
        return wrapper
    return decorator


def decrypt_sensitive_data(sensitive_fields: List[str]):
    """Decorator to decrypt multiple sensitive fields."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, dict):
                try:
                    result = encryption_manager.decrypt_sensitive_fields(result, sensitive_fields)
                except Exception as exc:
                    logger.error(f"Failed to decrypt sensitive fields: {exc}")
            
            return result
        return wrapper
    return decorator


# ── Database Field Encryption ─────────────────────────────────────────────────────

class EncryptedFieldMixin:
    """Mixin for encrypted database fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._encrypted_fields = getattr(self, '_encrypted_fields', [])
    
    def save(self, *args, **kwargs):
        """Encrypt sensitive fields before saving."""
        # Encrypt fields before saving
        for field in self._encrypted_fields:
            if hasattr(self, field):
                original_value = getattr(self, field)
                if isinstance(original_value, str):
                    try:
                        setattr(self, f"_{field}_original", original_value)
                        setattr(self, field, encryption_manager.encrypt(original_value))
                    except Exception as exc:
                        logger.error(f"Failed to encrypt field {field}: {exc}")
        
        super().save(*args, **kwargs)
        
        # Restore original values
        for field in self._encrypted_fields:
            if hasattr(self, f"_{field}_original"):
                setattr(self, field, getattr(self, f"_{field}_original"))
                delattr(self, f"_{field}_original")
    
    def __getattr__(self, name):
        """Get attribute, decrypting if it's an encrypted field."""
        if name in self._encrypted_fields:
            encrypted_value = super().__getattribute__(name)
            if isinstance(encrypted_value, str):
                try:
                    return encryption_manager.decrypt(encrypted_value)
                except Exception:
                    return encrypted_value
        
        return super().__getattribute__(name)


# ── Security Utilities ─────────────────────────────────────────────────────

class SecurityUtils:
    """Security utility functions."""
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate secure API key."""
        return base64.b64encode(os.urandom(length)).decode()
    
    @staticmethod
    def generate_session_token(length: int = 32) -> str:
        """Generate secure session token."""
        return base64.b64encode(os.urandom(length)).decode()
    
    @staticmethod
    def generate_webhook_secret(length: int = 32) -> str:
        """Generate webhook secret."""
        return base64.b64encode(os.urandom(length)).decode()
    
    @staticmethod
    def validate_api_key(api_key: str, expected_key: str) -> bool:
        """Validate API key."""
        return EncryptionUtils.secure_compare(api_key, expected_key)
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token."""
        return base64.b64encode(os.urandom(32)).decode()
    
    @staticmethod
    def sanitize_input(input_data: str) -> str:
        """Sanitize user input."""
        import re
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', input_data)
        
        # Limit length
        max_length = 1000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format."""
        import re
        pattern = r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def check_rate_limit(identifier: str, limit: int, window: int) -> bool:
        """Check rate limit for identifier."""
        cache_key = f"rate_limit:{identifier}"
        
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, timeout=window)
        return True
    
    @staticmethod
    def log_security_event(event_type: str, user_id: int = None, 
                           ip_address: str = None, details: Dict[str, Any] = None):
        """Log security event."""
        event_data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'user_id': user_id,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        logger.info(f"Security event: {event_type} - {event_data}")
        
        # This could also send to a security monitoring system
        # For now, it's just logged
    
    @staticmethod
    def detect_suspicious_activity(user_id: int, activity_data: Dict[str, Any]) -> bool:
        """Detect suspicious activity patterns."""
        suspicious_indicators = []
        
        # Check for rapid successive actions
        if activity_data.get('action_frequency', 0) > 100:  # More than 100 actions per minute
            suspicious_indicators.append('high_frequency')
        
        # Check for unusual timing patterns
        if activity_data.get('night_activity', False):
            suspicious_indicators.append('night_activity')
        
        # Check for multiple IP addresses
        if len(activity_data.get('ip_addresses', [])) > 5:
            suspicious_indicators.append('multiple_ips')
        
        # Check for failed login attempts
        if activity_data.get('failed_attempts', 0) > 10:
            suspicious_indicators.append('high_failed_attempts')
        
        if suspicious_indicators:
            SecurityUtils.log_security_event(
                'suspicious_activity_detected',
                user_id=user_id,
                details={'indicators': suspicious_indicators}
            )
            return True
        
        return False
