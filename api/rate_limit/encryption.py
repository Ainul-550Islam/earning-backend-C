# api/rate_limit/encryption.py
import json
"""
Encryption utilities for rate limit module.

Provides secure data encryption and decryption capabilities.
"""

import logging
import base64
import hashlib
import hmac
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import serialization
import os

logger = logging.getLogger(__name__)


class EncryptionAlgorithm:
    """Enumeration of encryption algorithms."""
    
    AES_256_GCM = 'aes_256_gcm'
    AES_256_CBC = 'aes_256_cbc'
    FERNET = 'fernet'
    HMAC_SHA256 = 'hmac_sha256'
    
    CHOICES = [
        (AES_256_GCM, 'AES-256-GCM'),
        (AES_256_CBC, 'AES-256-CBC'),
        (FERNET, 'Fernet'),
        (HMAC_SHA256, 'HMAC-SHA256'),
    ]


class EncryptionManager:
    """
    Manages encryption and decryption operations.
    """
    
    def __init__(self, algorithm: str = EncryptionAlgorithm.FERNET):
        self.algorithm = algorithm
        self.backend = default_backend()
        self._initialize_keys()
    
    def _initialize_keys(self):
        """Initialize encryption keys."""
        # Get encryption key from settings or generate one
        encryption_key = getattr(settings, 'RATE_LIMIT_ENCRYPTION_KEY', None)
        
        if encryption_key:
            self.key = self._decode_key(encryption_key)
        else:
            # Generate a new key (in production, this should be stored securely)
            self.key = Fernet.generate_key()
            logger.warning("No encryption key found in settings. Generated temporary key.")
        
        # Initialize cipher based on algorithm
        if self.algorithm == EncryptionAlgorithm.FERNET:
            self.cipher = Fernet(self.key)
        elif self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            self.cipher = self._get_aes_cipher()
        elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
            self.cipher = self._get_aes_cipher()
        else:
            raise ValueError(f"Unsupported encryption algorithm: {self.algorithm}")

    def _decode_key(self, key_string: str) -> bytes:
        """Decode encryption key from string."""
        import base64
        if isinstance(key_string, bytes):
            # Already bytes - try as Fernet key directly
            try:
                from cryptography.fernet import Fernet
                Fernet(key_string)
                return key_string
            except Exception:
                pass
        key_bytes = key_string.encode() if isinstance(key_string, str) else key_string
        # Try as Fernet key directly (already base64url encoded)
        try:
            from cryptography.fernet import Fernet
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            pass
        # Try as hex
        try:
            raw = bytes.fromhex(key_string if isinstance(key_string, str) else key_string.decode())
            if len(raw) == 32:
                return base64.urlsafe_b64encode(raw)
        except Exception:
            pass
        # Try as base64
        try:
            decoded = base64.urlsafe_b64decode(key_string + '==')
            if len(decoded) == 32:
                return base64.urlsafe_b64encode(decoded)
        except Exception:
            pass
        # Generate fresh key as last resort
        import logging
        logging.getLogger(__name__).warning("Could not decode encryption key, generating new one")
        from cryptography.fernet import Fernet
        return Fernet.generate_key()

    def _get_aes_cipher(self) -> Dict[str, Any]:
        """Get AES cipher configuration."""
        # Generate a random IV for each encryption
        return {
            'algorithm': algorithms.AES(self.key[:32]),  # Use first 32 bytes for AES-256
            'mode': modes.GCM(os.urandom(12)) if self.algorithm == EncryptionAlgorithm.AES_256_GCM else None
        }
    
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
                data = self._serialize_data(data)
            elif isinstance(data, str):
                data = data.encode()
            
            if self.algorithm == EncryptionAlgorithm.FERNET:
                encrypted_data = self.cipher.encrypt(data)
            elif self.algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                encrypted_data = self._encrypt_aes(data)
            else:
                raise ValueError(f"Unsupported encryption algorithm: {self.algorithm}")
            
            # Return as base64 string
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: str) -> Union[str, bytes, Dict[str, Any]]:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            
            if self.algorithm == EncryptionAlgorithm.FERNET:
                decrypted_data = self.cipher.decrypt(encrypted_bytes)
            elif self.algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                decrypted_data = self._decrypt_aes(encrypted_bytes)
            else:
                raise ValueError(f"Unsupported encryption algorithm: {self.algorithm}")
            
            # Try to deserialize as JSON first
            try:
                return self._deserialize_data(decrypted_data)
            except:
                # Return as string if not JSON
                return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise
    
    def _encrypt_aes(self, data: bytes) -> bytes:
        """Encrypt data using AES."""
        if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            # AES-GCM encryption
            iv = os.urandom(12)
            cipher = Cipher(
                algorithms.AES(self.key[:32]),
                modes.GCM(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Pad data
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # Encrypt
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            # Return IV + ciphertext + tag
            return iv + ciphertext + encryptor.tag
            
        elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
            # AES-CBC encryption
            iv = os.urandom(16)
            cipher = Cipher(
                algorithms.AES(self.key[:32]),
                modes.CBC(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Pad data
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # Encrypt
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            # Return IV + ciphertext
            return iv + ciphertext
        
        else:
            raise ValueError(f"Unsupported AES mode: {self.algorithm}")
    
    def _decrypt_aes(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using AES."""
        if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            # AES-GCM decryption
            if len(encrypted_data) < 28:  # 12 bytes IV + 16 bytes tag minimum
                raise ValueError("Invalid encrypted data length")
            
            iv = encrypted_data[:12]
            tag = encrypted_data[-16:]
            ciphertext = encrypted_data[12:-16]
            
            cipher = Cipher(
                algorithms.AES(self.key[:32]),
                modes.GCM(iv, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data
            
        elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
            # AES-CBC decryption
            if len(encrypted_data) < 16:  # Minimum IV length
                raise ValueError("Invalid encrypted data length")
            
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            cipher = Cipher(
                algorithms.AES(self.key[:32]),
                modes.CBC(iv),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data
        
        else:
            raise ValueError(f"Unsupported AES mode: {self.algorithm}")
    
    def _serialize_data(self, data: Dict[str, Any]) -> bytes:
        """Serialize data to bytes."""
        import json
        return json.dumps(data, cls=CustomJSONEncoder).encode()
    
    def _deserialize_data(self, data: bytes) -> Union[str, Dict[str, Any]]:
        """Deserialize data from bytes."""
        import json
        try:
            return json.loads(data.decode())
        except json.JSONDecodeError:
            return data.decode()
    
    def generate_hash(self, data: Union[str, bytes], salt: bytes = None) -> str:
        """
        Generate hash of data.
        
        Args:
            data: Data to hash
            salt: Salt for hashing
            
        Returns:
            Hexadecimal hash
        """
        try:
            if isinstance(data, str):
                data = data.encode()
            
            if salt is None:
                salt = self.key[:16]  # Use part of encryption key as salt
            
            # Use PBKDF2 with SHA256
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=self.backend
            )
            
            hash_bytes = kdf.derive(data)
            return hash_bytes.hex()
            
        except Exception as e:
            logger.error(f"Hash generation failed: {str(e)}")
            raise
    
    def verify_hash(self, data: Union[str, bytes], hash_value: str, salt: bytes = None) -> bool:
        """
        Verify hash against data.
        
        Args:
            data: Original data
            hash_value: Hash to verify
            salt: Salt used for hashing
            
        Returns:
            True if hash matches
        """
        try:
            computed_hash = self.generate_hash(data, salt)
            return hmac.compare_digest(computed_hash, hash_value)
        except Exception as e:
            logger.error(f"Hash verification failed: {str(e)}")
            return False
    
    def generate_hmac(self, data: Union[str, bytes], key: bytes = None) -> str:
        """
        Generate HMAC signature.
        
        Args:
            data: Data to sign
            key: Key for HMAC
            
        Returns:
            Hexadecimal HMAC signature
        """
        try:
            if isinstance(data, str):
                data = data.encode()
            
            if key is None:
                key = self.key
            
            # Generate HMAC using SHA256
            hmac_signature = hmac.new(key, data, hashlib.sha256).hexdigest()
            return hmac_signature
            
        except Exception as e:
            logger.error(f"HMAC generation failed: {str(e)}")
            raise
    
    def verify_hmac(self, data: Union[str, bytes], signature: str, key: bytes = None) -> bool:
        """
        Verify HMAC signature.
        
        Args:
            data: Original data
            signature: HMAC signature to verify
            key: Key for HMAC
            
        Returns:
            True if signature is valid
        """
        try:
            computed_signature = self.generate_hmac(data, key)
            return hmac.compare_digest(computed_signature, signature)
        except Exception as e:
            logger.error(f"HMAC verification failed: {str(e)}")
            return False


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for special types."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


class SecureTokenManager:
    """
    Manages secure tokens for rate limiting operations.
    """
    
    def __init__(self, encryption_manager: EncryptionManager = None):
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.token_ttl = getattr(settings, 'RATE_LIMIT_TOKEN_TTL', 3600)  # 1 hour
    
    def generate_token(self, user_id: int = None, ip_address: str = None, 
                      metadata: Dict[str, Any] = None) -> str:
        """
        Generate secure token.
        
        Args:
            user_id: User ID
            ip_address: IP address
            metadata: Additional metadata
            
        Returns:
            Secure token
        """
        try:
            # Create token data
            token_data = {
                'user_id': user_id,
                'ip_address': ip_address,
                'created_at': timezone.now().isoformat(),
                'expires_at': (timezone.now() + timedelta(seconds=self.token_ttl)).isoformat(),
                'metadata': metadata or {}
            }
            
            # Add random nonce
            token_data['nonce'] = os.urandom(16).hex()
            
            # Encrypt token data
            encrypted_token = self.encryption_manager.encrypt(token_data)
            
            # Add signature
            signature = self.encryption_manager.generate_hmac(encrypted_token.encode())
            
            # Combine token and signature
            full_token = f"{encrypted_token}.{signature}"
            
            return full_token
            
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode secure token.
        
        Args:
            token: Secure token
            
        Returns:
            Decoded token data
        """
        try:
            # Split token and signature
            parts = token.split('.')
            if len(parts) != 2:
                raise ValueError("Invalid token format")
            
            encrypted_token, signature = parts
            
            # Verify signature
            if not self.encryption_manager.verify_hmac(encrypted_token.encode(), signature):
                raise ValueError("Invalid token signature")
            
            # Decrypt token data
            token_data = self.encryption_manager.decrypt(encrypted_token)
            
            if not isinstance(token_data, dict):
                raise ValueError("Invalid token data")
            
            # Check expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if timezone.now() > expires_at:
                raise ValueError("Token has expired")
            
            return token_data
            
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise
    
    def is_token_valid(self, token: str) -> bool:
        """
        Check if token is valid.
        
        Args:
            token: Secure token
            
        Returns:
            True if token is valid
        """
        try:
            self.verify_token(token)
            return True
        except Exception:
            return False
    
    def refresh_token(self, token: str) -> str:
        """
        Refresh existing token.
        
        Args:
            token: Existing token
            
        Returns:
            New token
        """
        try:
            # Verify and decode existing token
            token_data = self.verify_token(token)
            
            # Generate new token with same data
            return self.generate_token(
                user_id=token_data.get('user_id'),
                ip_address=token_data.get('ip_address'),
                metadata=token_data.get('metadata')
            )
            
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise


class DataProtectionManager:
    """
    Manages data protection and privacy for rate limiting.
    """
    
    def __init__(self, encryption_manager: EncryptionManager = None):
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        self.pseudonymization_salt = os.urandom(32)
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in data.
        
        Args:
            data: Data dictionary
            
        Returns:
            Data with encrypted sensitive fields
        """
        try:
            encrypted_data = data.copy()
            
            for field in self.sensitive_fields:
                if field in data and data[field]:
                    encrypted_value = self.encryption_manager.encrypt(str(data[field]))
                    encrypted_data[f"{field}_encrypted"] = encrypted_value
                    # Remove original field for privacy
                    del encrypted_data[field]
            
            return encrypted_data
            
        except Exception as e:
            logger.error(f"Sensitive data encryption failed: {str(e)}")
            return data
    
    def decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in data.
        
        Args:
            data: Data dictionary with encrypted fields
            
        Returns:
            Data with decrypted sensitive fields
        """
        try:
            decrypted_data = data.copy()
            
            for field in self.sensitive_fields:
                encrypted_field = f"{field}_encrypted"
                if encrypted_field in data:
                    decrypted_value = self.encryption_manager.decrypt(data[encrypted_field])
                    decrypted_data[field] = decrypted_value
                    # Remove encrypted field
                    del decrypted_data[encrypted_field]
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Sensitive data decryption failed: {str(e)}")
            return data
    
    def pseudonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pseudonymize sensitive data for analytics.
        
        Args:
            data: Data dictionary
            
        Returns:
            Pseudonymized data
        """
        try:
            pseudonymized_data = data.copy()
            
            for field in self.sensitive_fields:
                if field in data and data[field]:
                    # Generate consistent pseudonym
                    pseudonym = self.encryption_manager.generate_hash(
                        str(data[field]), 
                        self.pseudonymization_salt
                    )
                    pseudonymized_data[f"{field}_pseudonym"] = pseudonym
                    # Remove original field
                    del pseudonymized_data[field]
            
            return pseudonymized_data
            
        except Exception as e:
            logger.error(f"Data pseudonymization failed: {str(e)}")
            return data
    
    def anonymize_logs(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Anonymize log data for long-term storage.
        
        Args:
            logs: List of log dictionaries
            
        Returns:
            Anonymized logs
        """
        try:
            anonymized_logs = []
            
            for log in logs:
                anonymized_log = log.copy()
                
                # Remove or hash sensitive fields
                if 'ip_address' in log:
                    anonymized_log['ip_address_hash'] = self.encryption_manager.generate_hash(
                        log['ip_address'], 
                        self.pseudonymization_salt
                    )
                    del anonymized_log['ip_address']
                
                if 'user_agent' in log:
                    del anonymized_log['user_agent']
                
                if 'user' in log and log['user']:
                    anonymized_log['user_id_hash'] = self.encryption_manager.generate_hash(
                        str(log['user']), 
                        self.pseudonymization_salt
                    )
                    del anonymized_log['user']
                
                anonymized_logs.append(anonymized_log)
            
            return anonymized_logs
            
        except Exception as e:
            logger.error(f"Log anonymization failed: {str(e)}")
            return logs


# Global instances
encryption_manager = EncryptionManager()
secure_token_manager = SecureTokenManager(encryption_manager)
data_protection_manager = DataProtectionManager(encryption_manager)


# Export classes and functions
__all__ = [
    'EncryptionAlgorithm',
    'EncryptionManager',
    'SecureTokenManager',
    'DataProtectionManager',
    'encryption_manager',
    'secure_token_manager',
    'data_protection_manager'
]


class RateLimitEncryptionService:
    """
    Unified encryption service for rate_limit module.
    encrypt_data()  -> str  (JSON envelope with embedded ciphertext + key)
    decrypt_data()  -> original type (str, bytes, dict, list, etc.)
    """

    def __init__(self):
        from api.rate_limit.encryption import EncryptionManager, DataProtectionManager
        self._manager = EncryptionManager()
        self._protection = DataProtectionManager()
        self._key = None
        self._key_store: dict = {}
        self._audit_logs: list = []

    # ------------------------------------------------------------------ #
    # Key generation                                                       #
    # ------------------------------------------------------------------ #
    def generate_key(self) -> bytes:
        from cryptography.fernet import Fernet
        self._key = Fernet.generate_key()
        return self._key

    def generate_aes_key(self, key_size: int = 256) -> bytes:
        import os
        return os.urandom(key_size // 8)

    def generate_secure_random_bytes(self, length: int = 32) -> bytes:
        import os
        return os.urandom(length)

    def generate_secure_random_int(self, min_val: int = 0, max_val: int = 2**32) -> int:
        import secrets
        return secrets.randbelow(max_val - min_val) + min_val

    def generate_secure_token(self, length: int = 32) -> str:
        import secrets
        return secrets.token_hex(length)  # length bytes -> length*2 hex chars

    # ------------------------------------------------------------------ #
    # Key store                                                            #
    # ------------------------------------------------------------------ #
    def store_encryption_key(self, key_id: str, key: bytes) -> None:
        self._key_store[key_id] = key

    def get_encryption_key(self, key_id: str) -> bytes:
        if key_id not in self._key_store:
            raise KeyError(f"Key not found: {key_id}")
        return self._key_store[key_id]

    def delete_encryption_key(self, key_id: str) -> None:
        if key_id not in self._key_store:
            raise KeyError(f"Key not found: {key_id}")
        del self._key_store[key_id]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #
    def _active_key(self, key=None) -> bytes:
        from cryptography.fernet import Fernet
        k = key or self._key
        if k is None:
            k = Fernet.generate_key()
            self._key = k
        return k if isinstance(k, bytes) else k.encode()

    def _serialise(self, data) -> tuple:
        """Return (bytes, type_tag) for any Python value."""
        if isinstance(data, bytes):
            return data, "bytes"
        if isinstance(data, str):
            return data.encode("utf-8"), "str"
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False).encode("utf-8"), "json"
        return str(data).encode("utf-8"), "str"

    def _deserialise(self, raw: bytes, type_tag: str):
        if type_tag == "bytes":
            return raw
        if type_tag == "json":
            return json.loads(raw.decode("utf-8"))
        return raw.decode("utf-8")

    # ------------------------------------------------------------------ #
    # Core Fernet encrypt / decrypt                                        #
    # ------------------------------------------------------------------ #
    def encrypt_data(self, data, key: bytes = None, key_type: str = "fernet") -> str:
        """Encrypt *data* and return a str JSON envelope."""
        import base64
        from cryptography.fernet import Fernet
        k = self._active_key(key)
        raw, type_tag = self._serialise(data)
        token = Fernet(k).encrypt(raw)
        envelope = json.dumps({
            "ciphertext": token.decode("utf-8"),
            "key": base64.b64encode(k).decode("utf-8"),
            "type": type_tag,
        })
        self._audit_logs.append({"operation": "encrypt",
                                  "timestamp": timezone.now().isoformat()})
        return envelope

    def decrypt_data(self, encrypted_data, key: bytes = None, key_type: str = "fernet"):
        """Decrypt a str envelope and return the original typed value."""
        import base64
        from cryptography.fernet import Fernet

        if isinstance(encrypted_data, str):
            try:
                env = json.loads(encrypted_data)
            except json.JSONDecodeError:
                raise ValueError("Invalid encrypted data: not a JSON envelope")
        elif isinstance(encrypted_data, dict):
            env = encrypted_data
        else:
            raise TypeError(f"Unsupported type: {type(encrypted_data)}")

        # Resolve key: explicit arg > envelope > service key
        if key is not None:
            k = key if isinstance(key, bytes) else key.encode()
        elif "key" in env:
            raw_k = env["key"]
            try:
                k = base64.b64decode(raw_k)
            except Exception:
                k = raw_k.encode() if isinstance(raw_k, str) else raw_k
        elif self._key:
            k = self._key
        else:
            raise ValueError("No decryption key available")

        token = env["ciphertext"]
        if isinstance(token, str):
            token = token.encode("utf-8")

        plain = Fernet(k).decrypt(token)
        self._audit_logs.append({"operation": "decrypt",
                                  "timestamp": timezone.now().isoformat()})
        return self._deserialise(plain, env.get("type", "str"))

    # ------------------------------------------------------------------ #
    # Key rotation                                                         #
    # ------------------------------------------------------------------ #
    def rotate_key(self, old_key: bytes = None) -> bytes:
        self._key = self.generate_key()
        return self._key

    def rotate_encryption(self, encrypted_data=None, old_key: bytes = None,
                          new_key: bytes = None, **kwargs) -> str:
        """Decrypt with old_key, re-encrypt with new_key."""
        plaintext = self.decrypt_data(encrypted_data, key=old_key)
        if new_key is not None:
            self._key = new_key if isinstance(new_key, bytes) else new_key.encode()
        return self.encrypt_data(plaintext, key=new_key)

    def re_encrypt_data(self, encrypted_data, new_key: bytes = None):
        """Re-encrypt with a fresh (or supplied) key."""
        plaintext = self.decrypt_data(encrypted_data)
        k = new_key or self.rotate_key()
        return self.encrypt_data(plaintext, key=k)

    # ------------------------------------------------------------------ #
    # AES-GCM                                                             #
    # ------------------------------------------------------------------ #
    def encrypt_data_aes_gcm(self, data, key: bytes = None) -> dict:
        import os
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        k = key or os.urandom(32)
        nonce = os.urandom(12)
        raw, type_tag = self._serialise(data)
        ct_with_tag = AESGCM(k).encrypt(nonce, raw, None)
        ct, tag = ct_with_tag[:-16], ct_with_tag[-16:]
        return {
            "encrypted_data": ct.hex(),
            "nonce": nonce.hex(),
            "tag": tag.hex(),
            "key": k.hex(),
            "type": type_tag,
        }

    def decrypt_data_aes_gcm(self, encrypted_data_hex: str, nonce_hex: str,
                              tag_hex: str, key: bytes = None, key_hex: str = None) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if key is None:
            key = bytes.fromhex(key_hex) if key_hex else None
        if key is None:
            raise ValueError("key or key_hex required")
        ct = bytes.fromhex(encrypted_data_hex) + bytes.fromhex(tag_hex)
        return AESGCM(key).decrypt(bytes.fromhex(nonce_hex), ct, None).decode("utf-8")

    # ------------------------------------------------------------------ #
    # ChaCha20-Poly1305                                                   #
    # ------------------------------------------------------------------ #
    def encrypt_data_chacha20(self, data, key: bytes = None) -> dict:
        import os
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        k = key or os.urandom(32)
        nonce = os.urandom(12)
        raw, type_tag = self._serialise(data)
        ct_with_tag = ChaCha20Poly1305(k).encrypt(nonce, raw, None)
        ct, tag = ct_with_tag[:-16], ct_with_tag[-16:]
        return {
            "encrypted_data": ct.hex(),
            "nonce": nonce.hex(),
            "tag": tag.hex(),
            "key": k.hex(),
            "type": type_tag,
        }

    def decrypt_data_chacha20(self, encrypted_data_hex: str, nonce_hex: str,
                               tag_hex: str, key: bytes = None, key_hex: str = None) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        if key is None:
            key = bytes.fromhex(key_hex) if key_hex else None
        if key is None:
            raise ValueError("key or key_hex required")
        ct = bytes.fromhex(encrypted_data_hex) + bytes.fromhex(tag_hex)
        return ChaCha20Poly1305(key).decrypt(bytes.fromhex(nonce_hex), ct, None).decode("utf-8")

    # ------------------------------------------------------------------ #
    # Key derivation                                                       #
    # ------------------------------------------------------------------ #
    def derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        import os
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        s = salt if salt is not None else os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=s,
                         iterations=100000, backend=default_backend())
        return kdf.derive(password.encode("utf-8"))

    # ------------------------------------------------------------------ #
    # Sensitive field helpers                                              #
    # ------------------------------------------------------------------ #
    def encrypt_sensitive_fields(self, data: dict, sensitive_fields: list = None) -> dict:
        fields = sensitive_fields or ["ip_address", "user_agent", "email"]
        result = dict(data)
        for f in fields:
            if f in result:
                result[f] = self.encrypt_data(result[f])
        return result

    def decrypt_sensitive_fields(self, data: dict, sensitive_fields: list = None) -> dict:
        fields = sensitive_fields or ["ip_address", "user_agent", "email"]
        result = dict(data)
        for f in fields:
            if f in result and isinstance(result[f], str):
                try:
                    result[f] = self.decrypt_data(result[f])
                except Exception:
                    pass
        return result

    # ------------------------------------------------------------------ #
    # Metadata-enhanced encryption                                        #
    # ------------------------------------------------------------------ #
    def encrypt_data_with_metadata(self, data, algorithm: str = "fernet",
                                   key_id: str = None, version: str = "1.0",
                                   metadata: dict = None, key: bytes = None,
                                   **kwargs) -> dict:
        import hashlib as _hashlib
        raw, _ = self._serialise(data)
        data_hash = _hashlib.sha256(raw).hexdigest()
        enc = self.encrypt_data(data, key=key)
        meta = {
            "algorithm": algorithm,
            "key_id": key_id or "",
            "version": version,
            "timestamp": timezone.now().isoformat(),
            "data_hash": data_hash,
        }
        if metadata:
            meta.update(metadata)
        # Accept extra kwargs (e.g. algorithm=, key_id=, version=) already handled above
        for k2, v in kwargs.items():
            meta[k2] = v
        return {"encrypted_data": enc, "metadata": meta}

    # ------------------------------------------------------------------ #
    # Batch operations                                                     #
    # ------------------------------------------------------------------ #
    def encrypt_batch(self, data_list: list, key: bytes = None) -> list:
        return [self.encrypt_data_with_metadata(d, key=key) for d in data_list]

    def decrypt_batch(self, encrypted_list: list) -> list:
        results = []
        for item in encrypted_list:
            if isinstance(item, dict) and "encrypted_data" in item:
                results.append(self.decrypt_data(item["encrypted_data"]))
            else:
                results.append(self.decrypt_data(item))
        return results

    # ------------------------------------------------------------------ #
    # Password hashing                                                    #
    # ------------------------------------------------------------------ #
    def hash_password(self, password: str) -> str:
        from django.contrib.auth.hashers import make_password
        return make_password(password)

    def verify_password(self, password: str, hashed: str) -> bool:
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed)

    # ------------------------------------------------------------------ #
    # Audit log                                                           #
    # ------------------------------------------------------------------ #
    def get_encryption_audit_logs(self) -> list:
        return list(self._audit_logs)
