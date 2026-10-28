# =============================================================================
# fraud_detection/encryption.py
# =============================================================================
"""
Advanced Encryption Layer for Fraud Detection System.

Provides AES-256 encryption for sensitive user data including IP addresses,
device IDs, and other personally identifiable information (PII).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from typing import Any, Dict, Optional, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from api.fraud_detection.exceptions import EncryptionError
from api.fraud_detection.constants import HASH_ALGORITHM


logger = logging.getLogger(__name__)


class AESEncryption:
    """
    AES-256 encryption service for sensitive data protection.
    
    Provides encryption/decryption capabilities using AES-256-CBC with
    PKCS7 padding for maximum security compliance.
    """
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize AES encryption with encryption key.
        
        Args:
            key: 32-byte encryption key. If None, uses settings.FRAUD_ENCRYPTION_KEY
        
        Raises:
            ImproperlyConfigured: If encryption key is not properly configured
        """
        self.key = key or self._get_encryption_key()
        self.backend = default_backend()
        
        if not self.key or len(self.key) != 32:
            raise ImproperlyConfigured(
                "Encryption key must be exactly 32 bytes for AES-256"
            )
    
    def _get_encryption_key(self) -> bytes:
        """
        Get encryption key from Django settings.
        
        Returns:
            32-byte encryption key
            
        Raises:
            ImproperlyConfigured: If key is not found or invalid
        """
        key_str = getattr(settings, 'FRAUD_ENCRYPTION_KEY', None)
        if not key_str:
            raise ImproperlyConfigured(
                "FRAUD_ENCRYPTION_KEY must be set in Django settings"
            )
        
        # Convert hex string to bytes or use string directly
        try:
            if key_str.startswith('hex:'):
                return bytes.fromhex(key_str[4:])
            elif key_str.startswith('base64:'):
                return base64.b64decode(key_str[7:])
            else:
                # Use SHA-256 to ensure 32-byte key from any string
                return hashlib.sha256(key_str.encode()).digest()
        except (ValueError, TypeError) as e:
            raise ImproperlyConfigured(f"Invalid encryption key format: {e}")
    
    def encrypt(self, data: Union[str, bytes, Dict, Any]) -> str:
        """
        Encrypt sensitive data using AES-256-CBC.
        
        Args:
            data: Data to encrypt (string, bytes, dict, or any JSON-serializable object)
            
        Returns:
            Base64-encoded encrypted string
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Convert data to JSON string if it's not already a string/bytes
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
            elif isinstance(data, str):
                data_str = data
            elif isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                data_str = str(data)
            
            # Convert to bytes
            data_bytes = data_str.encode('utf-8')
            
            # Generate random IV
            iv = os.urandom(16)
            
            # Apply PKCS7 padding
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data_bytes) + padder.finalize()
            
            # Encrypt using AES-256-CBC
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Combine IV and encrypted data, then encode as base64
            combined = iv + encrypted_data
            encrypted_b64 = base64.b64encode(combined).decode('utf-8')
            
            logger.debug(f"Successfully encrypted data (length: {len(data_str)})")
            return encrypted_b64
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt AES-256-CBC encrypted data.
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted string
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            # Decode from base64
            combined = base64.b64decode(encrypted_data)
            
            # Extract IV and encrypted data
            iv = combined[:16]
            encrypted_bytes = combined[16:]
            
            # Decrypt using AES-256-CBC
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
            
            # Remove PKCS7 padding
            unpadder = padding.PKCS7(128).unpadder()
            data_bytes = unpadder.update(padded_data) + unpadder.finalize()
            
            # Convert to string
            data_str = data_bytes.decode('utf-8')
            
            logger.debug(f"Successfully decrypted data (length: {len(data_str)})")
            return data_str
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}")
    
    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """
        Encrypt JSON data and return encrypted string.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Base64-encoded encrypted JSON string
        """
        return self.encrypt(data)
    
    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt encrypted JSON data and return dictionary.
        
        Args:
            encrypted_data: Base64-encoded encrypted JSON string
            
        Returns:
            Decrypted dictionary
            
        Raises:
            EncryptionError: If decryption or JSON parsing fails
        """
        try:
            decrypted_str = self.decrypt(encrypted_data)
            return json.loads(decrypted_str)
        except json.JSONDecodeError as e:
            raise EncryptionError(f"Failed to parse decrypted JSON: {e}")
    
    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a single field value for database storage.
        
        Args:
            value: Field value to encrypt
            
        Returns:
            Encrypted value with prefix to identify encrypted fields
        """
        if not value:
            return value
        
        encrypted = self.encrypt(value)
        return f"enc:{encrypted}"
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a single field value from database storage.
        
        Args:
            encrypted_value: Encrypted field value (with or without prefix)
            
        Returns:
            Decrypted field value
        """
        if not encrypted_value or not encrypted_value.startswith('enc:'):
            return encrypted_value
        
        encrypted_data = encrypted_value[4:]  # Remove 'enc:' prefix
        return self.decrypt(encrypted_data)
    
    def generate_data_hash(self, data: Union[str, bytes, Dict]) -> str:
        """
        Generate SHA-256 hash of data for integrity verification.
        
        Args:
            data: Data to hash
            
        Returns:
            Hexadecimal SHA-256 hash
        """
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        elif isinstance(data, str):
            data_str = data
        elif isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = str(data)
        
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
    
    def verify_integrity(self, data: Union[str, bytes, Dict], expected_hash: str) -> bool:
        """
        Verify data integrity using SHA-256 hash.
        
        Args:
            data: Data to verify
            expected_hash: Expected SHA-256 hash
            
        Returns:
            True if integrity verified, False otherwise
        """
        actual_hash = self.generate_data_hash(data)
        return actual_hash == expected_hash


class SensitiveDataHandler:
    """
    Handler for encrypting/decrypting sensitive fraud detection data.
    
    Provides specialized methods for common sensitive data types
    like IP addresses, device IDs, and user identifiers.
    """
    
    def __init__(self, encryption_service: Optional[AESEncryption] = None):
        """
        Initialize sensitive data handler.
        
        Args:
            encryption_service: AES encryption service instance
        """
        self.encryption = encryption_service or AESEncryption()
    
    def encrypt_ip_address(self, ip_address: str) -> str:
        """
        Encrypt IP address for secure storage.
        
        Args:
            ip_address: IP address to encrypt
            
        Returns:
            Encrypted IP address with type prefix
        """
        if not ip_address:
            return ip_address
        
        encrypted = self.encryption.encrypt(ip_address)
        return f"ip_enc:{encrypted}"
    
    def decrypt_ip_address(self, encrypted_ip: str) -> str:
        """
        Decrypt encrypted IP address.
        
        Args:
            encrypted_ip: Encrypted IP address with type prefix
            
        Returns:
            Decrypted IP address
        """
        if not encrypted_ip or not encrypted_ip.startswith('ip_enc:'):
            return encrypted_ip
        
        encrypted_data = encrypted_ip[7:]  # Remove 'ip_enc:' prefix
        return self.encryption.decrypt(encrypted_data)
    
    def encrypt_device_id(self, device_id: str) -> str:
        """
        Encrypt device ID for secure storage.
        
        Args:
            device_id: Device ID to encrypt
            
        Returns:
            Encrypted device ID with type prefix
        """
        if not device_id:
            return device_id
        
        encrypted = self.encryption.encrypt(device_id)
        return f"dev_enc:{encrypted}"
    
    def decrypt_device_id(self, encrypted_device_id: str) -> str:
        """
        Decrypt encrypted device ID.
        
        Args:
            encrypted_device_id: Encrypted device ID with type prefix
            
        Returns:
            Decrypted device ID
        """
        if not encrypted_device_id or not encrypted_device_id.startswith('dev_enc:'):
            return encrypted_device_id
        
        encrypted_data = encrypted_device_id[8:]  # Remove 'dev_enc:' prefix
        return self.encryption.decrypt(encrypted_data)
    
    def encrypt_user_fingerprint(self, fingerprint_data: Dict[str, Any]) -> str:
        """
        Encrypt user fingerprint data.
        
        Args:
            fingerprint_data: Fingerprint data dictionary
            
        Returns:
            Encrypted fingerprint data with type prefix
        """
        if not fingerprint_data:
            return ""
        
        encrypted = self.encryption.encrypt_json(fingerprint_data)
        return f"fp_enc:{encrypted}"
    
    def decrypt_user_fingerprint(self, encrypted_fingerprint: str) -> Dict[str, Any]:
        """
        Decrypt encrypted user fingerprint data.
        
        Args:
            encrypted_fingerprint: Encrypted fingerprint data with type prefix
            
        Returns:
            Decrypted fingerprint data dictionary
        """
        if not encrypted_fingerprint or not encrypted_fingerprint.startswith('fp_enc:'):
            return {}
        
        encrypted_data = encrypted_fingerprint[7:]  # Remove 'fp_enc:' prefix
        return self.encryption.decrypt_json(encrypted_data)
    
    def encrypt_sensitive_dict(self, data: Dict[str, Any], sensitive_keys: list[str]) -> Dict[str, Any]:
        """
        Encrypt specific keys in a dictionary.
        
        Args:
            data: Dictionary to process
            sensitive_keys: List of keys to encrypt
            
        Returns:
            Dictionary with sensitive values encrypted
        """
        result = data.copy()
        
        for key in sensitive_keys:
            if key in result and result[key]:
                if isinstance(result[key], (dict, list)):
                    result[key] = self.encryption.encrypt_json(result[key])
                else:
                    result[key] = self.encryption.encrypt_field(str(result[key]))
        
        return result
    
    def decrypt_sensitive_dict(self, data: Dict[str, Any], encrypted_keys: list[str]) -> Dict[str, Any]:
        """
        Decrypt specific keys in a dictionary.
        
        Args:
            data: Dictionary to process
            encrypted_keys: List of keys to decrypt
            
        Returns:
            Dictionary with encrypted values decrypted
        """
        result = data.copy()
        
        for key in encrypted_keys:
            if key in result and result[key]:
                if isinstance(result[key], str) and result[key].startswith('enc:'):
                    result[key] = self.encryption.decrypt_field(result[key])
                elif isinstance(result[key], str) and result[key].startswith('fp_enc:'):
                    result[key] = self.decrypt_user_fingerprint(result[key])
                elif isinstance(result[key], str) and result[key].startswith('ip_enc:'):
                    result[key] = self.decrypt_ip_address(result[key])
                elif isinstance(result[key], str) and result[key].startswith('dev_enc:'):
                    result[key] = self.decrypt_device_id(result[key])
        
        return result


# Global instances for easy access
default_encryption = AESEncryption()
sensitive_data_handler = SensitiveDataHandler(default_encryption)


def encrypt_sensitive_data(data: Union[str, Dict, Any]) -> str:
    """
    Convenience function to encrypt sensitive data.
    
    Args:
        data: Data to encrypt
        
    Returns:
        Encrypted data string
    """
    return default_encryption.encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Convenience function to decrypt sensitive data.
    
    Args:
        encrypted_data: Encrypted data string
        
    Returns:
        Decrypted data string
    """
    return default_encryption.decrypt(encrypted_data)


def encrypt_ip_address(ip_address: str) -> str:
    """
    Convenience function to encrypt IP address.
    
    Args:
        ip_address: IP address to encrypt
        
    Returns:
        Encrypted IP address
    """
    return sensitive_data_handler.encrypt_ip_address(ip_address)


def decrypt_ip_address(encrypted_ip: str) -> str:
    """
    Convenience function to decrypt IP address.
    
    Args:
        encrypted_ip: Encrypted IP address
        
    Returns:
        Decrypted IP address
    """
    return sensitive_data_handler.decrypt_ip_address(encrypted_ip)


def generate_integrity_hash(data: Union[str, bytes, Dict]) -> str:
    """
    Convenience function to generate integrity hash.
    
    Args:
        data: Data to hash
        
    Returns:
        SHA-256 hash
    """
    return default_encryption.generate_data_hash(data)


def verify_data_integrity(data: Union[str, bytes, Dict], expected_hash: str) -> bool:
    """
    Convenience function to verify data integrity.
    
    Args:
        data: Data to verify
        expected_hash: Expected hash
        
    Returns:
        True if integrity verified
    """
    return default_encryption.verify_integrity(data, expected_hash)


# Stubs for missing functions
def encrypt_device_id(device_id: str) -> str:
    return encrypt_sensitive_data(device_id)


