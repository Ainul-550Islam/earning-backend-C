# =============================================================================
# auto_mod/encryption.py
# =============================================================================

"""
Encryption and security utilities for auto moderation system.
Provides data encryption, secure hashing, and security utilities.
"""
import json

import logging
import os
import base64
import hashlib
import secrets
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Manager for encryption and decryption operations.
    """
    
    def __init__(self, key: bytes = None):
        self.key = key or self._get_or_generate_key()
        self.fernet = Fernet(self.key)
        self.backend = default_backend()
    
    def _get_or_generate_key(self) -> bytes:
        """Get or generate encryption key."""
        try:
            # Try to get key from settings
            key = getattr(settings, 'AUTO_MOD_ENCRYPTION_KEY', None)
            if key:
                if isinstance(key, str):
                    key = key.encode()
                return base64.urlsafe_b64decode(key)
            
            # Try to get from environment
            key = os.environ.get('AUTO_MOD_ENCRYPTION_KEY')
            if key:
                if isinstance(key, str):
                    key = key.encode()
                return base64.urlsafe_b64decode(key)
            
            # Generate new key
            key = Fernet.generate_key()
            logger.warning("Generated new encryption key. Please set AUTO_MOD_ENCRYPTION_KEY in settings.")
            return key
            
        except Exception as exc:
            logger.error(f"Get encryption key failed: {exc}")
            # Fallback to generated key
            return Fernet.generate_key()
    
    def encrypt(self, data: Union[str, bytes, Dict[str, Any]]) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        try:
            if isinstance(data, dict):
                data = self._serialize_dict(data)
            elif isinstance(data, str):
                data = data.encode()
            
            encrypted = self.fernet.encrypt(data)
            return base64.b64encode(encrypted).decode()
            
        except Exception as exc:
            logger.error(f"Encryption failed: {exc}")
            raise ModerationError(f"Failed to encrypt data: {exc}")
    
    def decrypt(self, encrypted_data: str) -> Union[str, Dict[str, Any]]:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            
            # Try to parse as JSON first
            try:
                return self._deserialize_dict(decrypted)
            except (json.JSONDecodeError, ValueError):
                return decrypted.decode()
                
        except Exception as exc:
            logger.error(f"Decryption failed: {exc}")
            raise ModerationError(f"Failed to decrypt data: {exc}")
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt dictionary data."""
        return self.encrypt(data)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt dictionary data."""
        result = self.decrypt(encrypted_data)
        if isinstance(result, dict):
            return result
        else:
            raise ValueError("Decrypted data is not a dictionary")
    
    def _serialize_dict(self, data: Dict[str, Any]) -> bytes:
        """Serialize dictionary to bytes."""
        import json
        return json.dumps(data).encode()
    
    def _deserialize_dict(self, data: bytes) -> Dict[str, Any]:
        """Deserialize dictionary from bytes."""
        import json
        return json.loads(data.decode())


class HashManager:
    """
    Manager for secure hashing operations.
    """
    
    def __init__(self):
        self.backend = default_backend()
    
    def hash_password(self, password: str, salt: str = None) -> Dict[str, str]:
        """
        Hash password with salt.
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Dictionary with hash and salt
        """
        try:
            if salt is None:
                salt = secrets.token_hex(32)
            
            # Use PBKDF2 for password hashing
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
                backend=self.backend
            )
            
            password_hash = kdf.derive(password.encode())
            hash_b64 = base64.b64encode(password_hash).decode()
            
            return {
                'hash': hash_b64,
                'salt': salt,
                'algorithm': 'pbkdf2_sha256',
                'iterations': 100000
            }
            
        except Exception as exc:
            logger.error(f"Password hashing failed: {exc}")
            raise ModerationError(f"Failed to hash password: {exc}")
    
    def verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """
        Verify password against stored hash.
        
        Args:
            password: Password to verify
            stored_hash: Stored hash
            salt: Salt used for hashing
            
        Returns:
            True if password matches
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
                backend=self.backend
            )
            
            password_hash = kdf.derive(password.encode())
            hash_b64 = base64.b64encode(password_hash).decode()
            
            return secrets.compare_digest(hash_b64, stored_hash)
            
        except Exception as exc:
            logger.error(f"Password verification failed: {exc}")
            return False
    
    def hash_data(self, data: str, algorithm: str = 'sha256') -> str:
        """
        Hash data using specified algorithm.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (sha256, sha512, md5)
            
        Returns:
            Hash as hex string
        """
        try:
            if algorithm == 'sha256':
                hash_obj = hashlib.sha256(data.encode())
            elif algorithm == 'sha512':
                hash_obj = hashlib.sha512(data.encode())
            elif algorithm == 'md5':
                hash_obj = hashlib.md5(data.encode())
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            return hash_obj.hexdigest()
            
        except Exception as exc:
            logger.error(f"Data hashing failed: {exc}")
            raise ModerationError(f"Failed to hash data: {exc}")
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate secure random token.
        
        Args:
            length: Token length in bytes
            
        Returns:
            Secure token as hex string
        """
        try:
            return secrets.token_hex(length)
        except Exception as exc:
            logger.error(f"Token generation failed: {exc}")
            raise ModerationError(f"Failed to generate token: {exc}")
    
    def generate_api_key(self, prefix: str = "am") -> str:
        """
        Generate API key with prefix.
        
        Args:
            prefix: Key prefix
            
        Returns:
            API key
        """
        try:
            token = secrets.token_urlsafe(32)
            return f"{prefix}_{token}"
        except Exception as exc:
            logger.error(f"API key generation failed: {exc}")
            raise ModerationError(f"Failed to generate API key: {exc}")


class SecureTokenManager:
    """
    Manager for secure tokens with expiration.
    """
    
    def __init__(self):
        self.hash_manager = HashManager()
        self.tokens = {}  # In production, use database or cache
    
    def generate_token(self, user_id: Union[str, int], purpose: str, 
                      expires_in_hours: int = 24) -> Dict[str, Any]:
        """
        Generate secure token.
        
        Args:
            user_id: User ID
            purpose: Token purpose
            expires_in_hours: Expiration time in hours
            
        Returns:
            Token data
        """
        try:
            token = self.hash_manager.generate_secure_token(32)
            expires_at = timezone.now() + timedelta(hours=expires_in_hours)
            
            token_data = {
                'token': token,
                'user_id': str(user_id),
                'purpose': purpose,
                'created_at': timezone.now().isoformat(),
                'expires_at': expires_at.isoformat(),
                'is_active': True
            }
            
            # Store token (in production, use database)
            self.tokens[token] = token_data
            
            return token_data
            
        except Exception as exc:
            logger.error(f"Token generation failed: {exc}")
            raise ModerationError(f"Failed to generate token: {exc}")
    
    def validate_token(self, token: str, purpose: str = None) -> Optional[Dict[str, Any]]:
        """
        Validate token.
        
        Args:
            token: Token to validate
            purpose: Expected purpose (optional)
            
        Returns:
            Token data if valid, None otherwise
        """
        try:
            token_data = self.tokens.get(token)
            if not token_data:
                return None
            
            # Check if token is active
            if not token_data.get('is_active'):
                return None
            
            # Check purpose if specified
            if purpose and token_data.get('purpose') != purpose:
                return None
            
            # Check expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if timezone.now() > expires_at:
                # Mark as inactive
                token_data['is_active'] = False
                return None
            
            return token_data
            
        except Exception as exc:
            logger.error(f"Token validation failed: {exc}")
            return None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke token.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revoked
        """
        try:
            token_data = self.tokens.get(token)
            if token_data:
                token_data['is_active'] = False
                return True
            return False
        except Exception as exc:
            logger.error(f"Token revocation failed: {exc}")
            return False
    
    def revoke_user_tokens(self, user_id: Union[str, int]) -> int:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of tokens revoked
        """
        try:
            revoked_count = 0
            user_id_str = str(user_id)
            
            for token, token_data in self.tokens.items():
                if token_data.get('user_id') == user_id_str and token_data.get('is_active'):
                    token_data['is_active'] = False
                    revoked_count += 1
            
            return revoked_count
            
        except Exception as exc:
            logger.error(f"Revoke user tokens failed: {exc}")
            return 0
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            cleaned_count = 0
            current_time = timezone.now()
            
            for token, token_data in list(self.tokens.items()):
                if token_data.get('is_active'):
                    expires_at = datetime.fromisoformat(token_data['expires_at'])
                    if current_time > expires_at:
                        token_data['is_active'] = False
                        cleaned_count += 1
            
            return cleaned_count
            
        except Exception as exc:
            logger.error(f"Cleanup expired tokens failed: {exc}")
            return 0


class DataMasking:
    """
    Data masking utilities for sensitive information.
    """
    
    @staticmethod
    def mask_email(email: str, show_chars: int = 2) -> str:
        """
        Mask email address.
        
        Args:
            email: Email to mask
            show_chars: Number of characters to show at start
            
        Returns:
            Masked email
        """
        try:
            if '@' not in email:
                return email
            
            local, domain = email.split('@', 1)
            
            if len(local) <= show_chars:
                masked_local = local[0] + '*' * (len(local) - 1)
            else:
                masked_local = local[:show_chars] + '*' * (len(local) - show_chars)
            
            return f"{masked_local}@{domain}"
            
        except Exception as exc:
            logger.error(f"Email masking failed: {exc}")
            return email
    
    @staticmethod
    def mask_phone(phone: str, show_digits: int = 4) -> str:
        """
        Mask phone number.
        
        Args:
            phone: Phone number to mask
            show_digits: Number of digits to show at end
            
        Returns:
            Masked phone
        """
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, phone))
            
            if len(digits) <= show_digits:
                return phone
            
            masked = '*' * (len(digits) - show_digits) + digits[-show_digits:]
            
            # Format phone number
            if len(digits) == 10:
                return f"***-***-{masked[-4:]}"
            else:
                return masked
                
        except Exception as exc:
            logger.error(f"Phone masking failed: {exc}")
            return phone
    
    @staticmethod
    def mask_credit_card(card_number: str) -> str:
        """
        Mask credit card number.
        
        Args:
            card_number: Card number to mask
            
        Returns:
            Masked card number
        """
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, card_number))
            
            if len(digits) < 4:
                return card_number
            
            return '*' * (len(digits) - 4) + digits[-4:]
            
        except Exception as exc:
            logger.error(f"Credit card masking failed: {exc}")
            return card_number
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*') -> str:
        """
        Mask sensitive data completely.
        
        Args:
            data: Data to mask
            mask_char: Character to use for masking
            
        Returns:
            Masked data
        """
        try:
            if not data:
                return data
            
            return mask_char * len(data)
            
        except Exception as exc:
            logger.error(f"Data masking failed: {exc}")
            return data


class SecurityAuditLogger:
    """
    Security audit logging.
    """
    
    def __init__(self):
        self.log_file = getattr(settings, 'SECURITY_LOG_FILE', 'security_audit.log')
    
    def log_security_event(self, event_type: str, user_id: Union[str, int] = None,
                          details: Dict[str, Any] = None, severity: str = 'INFO') -> None:
        """
        Log security event.
        
        Args:
            event_type: Type of security event
            user_id: User ID (optional)
            details: Event details
            severity: Log severity
        """
        try:
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'event_type': event_type,
                'user_id': str(user_id) if user_id else None,
                'details': details or {},
                'severity': severity,
            }
            
            # Log to file
            logger.info(f"SECURITY_AUDIT: {log_data}")
            
            # In production, also log to secure audit system
            # self._write_to_audit_log(log_data)
            
        except Exception as exc:
            logger.error(f"Security audit logging failed: {exc}")
    
    def log_encryption_event(self, operation: str, data_type: str, user_id: Union[str, int] = None) -> None:
        """Log encryption/decryption event."""
        self.log_security_event(
            event_type='encryption_operation',
            user_id=user_id,
            details={
                'operation': operation,
                'data_type': data_type,
            },
            severity='INFO'
        )
    
    def log_authentication_event(self, event_type: str, user_id: Union[str, int], 
                              success: bool, ip_address: str = None) -> None:
        """Log authentication event."""
        self.log_security_event(
            event_type='authentication',
            user_id=user_id,
            details={
                'auth_event_type': event_type,
                'success': success,
                'ip_address': ip_address,
            },
            severity='INFO' if success else 'WARNING'
        )
    
    def log_data_access_event(self, resource_type: str, resource_id: str, 
                             user_id: Union[str, int], action: str) -> None:
        """Log data access event."""
        self.log_security_event(
            event_type='data_access',
            user_id=user_id,
            details={
                'resource_type': resource_type,
                'resource_id': resource_id,
                'action': action,
            },
            severity='INFO'
        )


# Global instances
encryption_manager = EncryptionManager()
hash_manager = HashManager()
token_manager = SecureTokenManager()
data_masking = DataMasking()
security_logger = SecurityAuditLogger()


# Utility functions
def encrypt_sensitive_data(data: Union[str, Dict[str, Any]]) -> str:
    """Encrypt sensitive data."""
    return encryption_manager.encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> Union[str, Dict[str, Any]]:
    """Decrypt sensitive data."""
    return encryption_manager.decrypt(encrypted_data)


def hash_password(password: str, salt: str = None) -> Dict[str, str]:
    """Hash password."""
    return hash_manager.hash_password(password, salt)


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify password."""
    return hash_manager.verify_password(password, stored_hash, salt)


def generate_secure_token(length: int = 32) -> str:
    """Generate secure token."""
    return hash_manager.generate_secure_token(length)


def generate_api_key(prefix: str = "am") -> str:
    """Generate API key."""
    return hash_manager.generate_api_key(prefix)


def mask_sensitive_info(data: str, data_type: str = 'general') -> str:
    """Mask sensitive information."""
    if data_type == 'email':
        return data_masking.mask_email(data)
    elif data_type == 'phone':
        return data_masking.mask_phone(data)
    elif data_type == 'credit_card':
        return data_masking.mask_credit_card(data)
    else:
        return data_masking.mask_sensitive_data(data)


# Initialize logging
logger.info("Encryption module initialized with security utilities")
