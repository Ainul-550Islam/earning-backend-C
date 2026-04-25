"""
api/ad_networks/encryption.py
Encryption and security utilities for ad networks module
SaaS-ready with tenant support
"""

import logging
import os
import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ==================== ENCRYPTION ALGORITHMS ====================

class EncryptionAlgorithm:
    """Supported encryption algorithms"""
    
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    FERNET = "fernet"
    CHACHA20_POLY1305 = "chacha20_poly1305"


# ==================== BASE ENCRYPTION MANAGER ====================

class BaseEncryptionManager:
    """Base encryption manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.backend = default_backend()
    
    def _generate_salt(self, length: int = 32) -> bytes:
        """Generate random salt"""
        return os.urandom(length)
    
    def _derive_key(self, password: str, salt: bytes, iterations: int = 100000) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=self.backend
        )
        return kdf.derive(password.encode())
    
    def _get_encryption_key(self, key_name: str = 'default') -> bytes:
        """Get encryption key from settings"""
        key = getattr(settings, f'ENCRYPTION_KEY_{key_name.upper()}', None)
        
        if not key:
            # Generate and store a new key (in production, this should be stored securely)
            key = Fernet.generate_key().decode()
            logger.warning(f"Generated new encryption key for {key_name}")
        
        if isinstance(key, str):
            key = key.encode()
        
        return key


# ==================== FERNET ENCRYPTION MANAGER ====================

class FernetEncryptionManager(BaseEncryptionManager):
    """Fernet encryption manager (symmetric)"""
    
    def __init__(self, tenant_id: str = 'default', key_name: str = 'default'):
        super().__init__(tenant_id)
        self.key_name = key_name
        self.key = self._get_encryption_key(key_name)
        self.fernet = Fernet(self.key)
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """Encrypt data using Fernet"""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            encrypted_data = self.fernet.encrypt(data)
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Error encrypting data: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Error decrypting data: {str(e)}")
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt dictionary data"""
        import json
        json_data = json.dumps(data, default=str)
        return self.encrypt(json_data)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt dictionary data"""
        import json
        json_data = self.decrypt(encrypted_data)
        return json.loads(json_data)


# ==================== AES ENCRYPTION MANAGER ====================

class AESEncryptionManager(BaseEncryptionManager):
    """AES encryption manager (symmetric)"""
    
    def __init__(self, tenant_id: str = 'default', algorithm: str = EncryptionAlgorithm.AES_256_GCM):
        super().__init__(tenant_id)
        self.algorithm = algorithm
        self.key = self._get_encryption_key('aes')
        
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            self.cipher_algorithm = algorithms.AES(self.key)
            self.mode = modes.GCM
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            self.cipher_algorithm = algorithms.AES(self.key)
            self.mode = modes.CBC
        else:
            raise ValueError(f"Unsupported AES algorithm: {algorithm}")
    
    def encrypt(self, data: Union[str, bytes]) -> Dict[str, str]:
        """Encrypt data using AES"""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            # Generate random IV
            iv = os.urandom(16)
            
            if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
                # AES-GCM mode
                cipher = Cipher(self.cipher_algorithm, self.mode(iv), backend=self.backend)
                encryptor = cipher.encryptor()
                
                ciphertext = encryptor.update(data) + encryptor.finalize()
                tag = encryptor.tag
                
                return {
                    'ciphertext': base64.b64encode(ciphertext).decode(),
                    'iv': base64.b64encode(iv).decode(),
                    'tag': base64.b64encode(tag).decode(),
                    'algorithm': self.algorithm,
                }
            
            else:
                # AES-CBC mode
                # Pad data to block size
                pad_length = 16 - (len(data) % 16)
                padded_data = data + bytes([pad_length] * pad_length)
                
                cipher = Cipher(self.cipher_algorithm, self.mode(iv), backend=self.backend)
                encryptor = cipher.encryptor()
                
                ciphertext = encryptor.update(padded_data) + encryptor.finalize()
                
                return {
                    'ciphertext': base64.b64encode(ciphertext).decode(),
                    'iv': base64.b64encode(iv).decode(),
                    'algorithm': self.algorithm,
                }
                
        except Exception as e:
            logger.error(f"Error encrypting data with AES: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: Dict[str, str]) -> str:
        """Decrypt data using AES"""
        try:
            ciphertext = base64.b64decode(encrypted_data['ciphertext'].encode())
            iv = base64.b64decode(encrypted_data['iv'].encode())
            
            if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
                tag = base64.b64decode(encrypted_data['tag'].encode())
                
                cipher = Cipher(self.cipher_algorithm, self.mode(iv, tag), backend=self.backend)
                decryptor = cipher.decryptor()
                
                decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
                
            else:
                cipher = Cipher(self.cipher_algorithm, self.mode(iv), backend=self.backend)
                decryptor = cipher.decryptor()
                
                padded_data = decryptor.update(ciphertext) + decryptor.finalize()
                
                # Remove padding
                pad_length = padded_data[-1]
                decrypted_data = padded_data[:-pad_length]
            
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Error decrypting data with AES: {str(e)}")
            raise


# ==================== HASHING MANAGER ====================

class HashingManager(BaseEncryptionManager):
    """Hashing manager for one-way hashing"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
    
    def hash_password(self, password: str, salt: bytes = None) -> Tuple[str, bytes]:
        """Hash password with salt"""
        if salt is None:
            salt = self._generate_salt()
        
        # Use PBKDF2 with SHA-256
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        
        return base64.b64encode(hashed).decode(), salt
    
    def verify_password(self, password: str, hashed: str, salt: bytes) -> bool:
        """Verify password against hash"""
        try:
            hashed_bytes = base64.b64decode(hashed.encode())
            computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            
            return hmac.compare_digest(hashed_bytes, computed_hash)
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False
    
    def hash_data(self, data: str, algorithm: str = 'sha256') -> str:
        """Hash data using specified algorithm"""
        try:
            if algorithm == 'sha256':
                return hashlib.sha256(data.encode()).hexdigest()
            elif algorithm == 'md5':
                return hashlib.md5(data.encode()).hexdigest()
            elif algorithm == 'sha1':
                return hashlib.sha1(data.encode()).hexdigest()
            else:
                raise ValueError(f"Unsupported hashing algorithm: {algorithm}")
        except Exception as e:
            logger.error(f"Error hashing data: {str(e)}")
            raise
    
    def generate_token(self, length: int = 32) -> str:
        """Generate secure random token"""
        return base64.b64encode(os.urandom(length)).decode()


# ==================== SECURE TOKEN MANAGER ====================

class SecureTokenManager(BaseEncryptionManager):
    """Secure token manager for JWT-like tokens"""
    
    def __init__(self, tenant_id: str = 'default', secret_key: str = None):
        super().__init__(tenant_id)
        self.secret_key = secret_key or getattr(settings, 'SECRET_KEY', 'default-secret')
        self.algorithm = 'HS256'
        self.fernet_manager = FernetEncryptionManager(tenant_id, 'token')
    
    def generate_token(self, payload: Dict[str, Any], expires_in: int = 3600) -> str:
        """Generate secure token"""
        try:
            # Add expiration time
            payload['exp'] = (timezone.now() + timedelta(seconds=expires_in)).timestamp()
            payload['iat'] = timezone.now().timestamp()
            payload['tenant_id'] = self.tenant_id
            
            # Encrypt payload
            encrypted_payload = self.fernet_manager.encrypt_dict(payload)
            
            # Create signature
            signature = hmac.new(
                self.secret_key.encode(),
                encrypted_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Combine payload and signature
            token = f"{encrypted_payload}.{signature}"
            
            return base64.b64encode(token.encode()).decode()
            
        except Exception as e:
            logger.error(f"Error generating token: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode token"""
        try:
            # Decode token
            decoded_token = base64.b64decode(token.encode()).decode()
            
            # Split payload and signature
            if '.' not in decoded_token:
                return None
            
            encrypted_payload, signature = decoded_token.split('.', 1)
            
            # Verify signature
            expected_signature = hmac.new(
                self.secret_key.encode(),
                encrypted_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return None
            
            # Decrypt payload
            payload = self.fernet_manager.decrypt_dict(encrypted_payload)
            
            # Check expiration
            exp = payload.get('exp')
            if exp and exp < timezone.now().timestamp():
                return None
            
            # Check tenant
            if payload.get('tenant_id') != self.tenant_id:
                return None
            
            return payload
            
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return None
    
    def refresh_token(self, token: str, expires_in: int = 3600) -> Optional[str]:
        """Refresh token"""
        payload = self.verify_token(token)
        
        if payload:
            # Remove expiration and issued at
            payload.pop('exp', None)
            payload.pop('iat', None)
            
            # Generate new token
            return self.generate_token(payload, expires_in)
        
        return None


# ==================== DATA MASKING MANAGER ====================

class DataMaskingManager(BaseEncryptionManager):
    """Data masking manager for sensitive data"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
    
    def mask_email(self, email: str) -> str:
        """Mask email address"""
        try:
            if '@' not in email:
                return email
            
            local, domain = email.split('@', 1)
            
            if len(local) <= 2:
                masked_local = '*' * len(local)
            else:
                masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
            
            return f"{masked_local}@{domain}"
            
        except Exception as e:
            logger.error(f"Error masking email: {str(e)}")
            return email
    
    def mask_phone(self, phone: str) -> str:
        """Mask phone number"""
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, phone))
            
            if len(digits) <= 4:
                return '*' * len(phone)
            
            # Keep last 4 digits visible
            masked = '*' * (len(digits) - 4) + digits[-4:]
            
            # Add back original formatting
            result = ''
            digit_index = 0
            for char in phone:
                if char.isdigit():
                    result += masked[digit_index]
                    digit_index += 1
                else:
                    result += char
            
            return result
            
        except Exception as e:
            logger.error(f"Error masking phone: {str(e)}")
            return phone
    
    def mask_credit_card(self, card_number: str) -> str:
        """Mask credit card number"""
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, card_number))
            
            if len(digits) < 4:
                return '*' * len(card_number)
            
            # Show only last 4 digits
            masked = '*' * (len(digits) - 4) + digits[-4:]
            
            # Add original spacing
            if len(card_number) > 16:  # Likely has spaces
                return f"**** **** **** {digits[-4:]}"
            else:
                return f"{'*' * 12} {digits[-4:]}"
                
        except Exception as e:
            logger.error(f"Error masking credit card: {str(e)}")
            return card_number
    
    def mask_sensitive_data(self, data: str, visible_chars: int = 4, mask_char: str = '*') -> str:
        """Mask sensitive data keeping visible characters"""
        try:
            if len(data) <= visible_chars:
                return mask_char * len(data)
            
            return data[:visible_chars // 2] + mask_char * (len(data) - visible_chars) + data[-(visible_chars // 2):]
            
        except Exception as e:
            logger.error(f"Error masking sensitive data: {str(e)}")
            return data


# ==================== KEY MANAGEMENT ====================

class KeyManager(BaseEncryptionManager):
    """Encryption key management"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.key_store = {}  # In production, use secure key store
    
    def generate_key(self, algorithm: str = 'fernet', key_length: int = 32) -> str:
        """Generate new encryption key"""
        try:
            if algorithm == 'fernet':
                return Fernet.generate_key().decode()
            else:
                return base64.b64encode(os.urandom(key_length)).decode()
                
        except Exception as e:
            logger.error(f"Error generating key: {str(e)}")
            raise
    
    def store_key(self, key_name: str, key: str, metadata: Dict[str, Any] = None) -> bool:
        """Store encryption key"""
        try:
            # In production, store in secure key vault
            self.key_store[key_name] = {
                'key': key,
                'metadata': metadata or {},
                'created_at': timezone.now().isoformat(),
                'tenant_id': self.tenant_id,
            }
            return True
        except Exception as e:
            logger.error(f"Error storing key: {str(e)}")
            return False
    
    def retrieve_key(self, key_name: str) -> Optional[str]:
        """Retrieve encryption key"""
        try:
            key_data = self.key_store.get(key_name)
            return key_data['key'] if key_data else None
        except Exception as e:
            logger.error(f"Error retrieving key: {str(e)}")
            return None
    
    def rotate_key(self, key_name: str, new_key: str = None) -> Optional[str]:
        """Rotate encryption key"""
        try:
            old_key = self.retrieve_key(key_name)
            if not old_key:
                return None
            
            new_key = new_key or self.generate_key()
            
            # Store new key
            self.store_key(key_name, new_key, {'rotated_from': old_key})
            
            # In production, re-encrypt data with new key
            logger.info(f"Key rotated for {key_name}")
            
            return new_key
            
        except Exception as e:
            logger.error(f"Error rotating key: {str(e)}")
            return None
    
    def list_keys(self) -> List[Dict[str, Any]]:
        """List all keys"""
        try:
            return [
                {
                    'name': name,
                    'metadata': data['metadata'],
                    'created_at': data['created_at'],
                }
                for name, data in self.key_store.items()
                if data['tenant_id'] == self.tenant_id
            ]
        except Exception as e:
            logger.error(f"Error listing keys: {str(e)}")
            return []


# ==================== ENCRYPTION SERVICE ====================

class EncryptionService:
    """Main encryption service"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.fernet_manager = FernetEncryptionManager(tenant_id)
        self.aes_manager = AESEncryptionManager(tenant_id)
        self.hashing_manager = HashingManager(tenant_id)
        self.token_manager = SecureTokenManager(tenant_id)
        self.masking_manager = DataMaskingManager(tenant_id)
        self.key_manager = KeyManager(tenant_id)
    
    def encrypt_sensitive_data(self, data: str, algorithm: str = 'fernet') -> Union[str, Dict[str, str]]:
        """Encrypt sensitive data"""
        if algorithm == 'fernet':
            return self.fernet_manager.encrypt(data)
        elif algorithm.startswith('aes'):
            return self.aes_manager.encrypt(data)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
    
    def decrypt_sensitive_data(self, encrypted_data: Union[str, Dict[str, str]], 
                             algorithm: str = 'fernet') -> str:
        """Decrypt sensitive data"""
        if algorithm == 'fernet':
            return self.fernet_manager.decrypt(encrypted_data)
        elif algorithm.startswith('aes'):
            return self.aes_manager.decrypt(encrypted_data)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
    
    def hash_and_salt_password(self, password: str) -> Tuple[str, str]:
        """Hash and salt password"""
        hashed, salt = self.hashing_manager.hash_password(password)
        return hashed, base64.b64encode(salt).decode()
    
    def verify_hashed_password(self, password: str, hashed: str, salt: str) -> bool:
        """Verify hashed password"""
        salt_bytes = base64.b64decode(salt.encode())
        return self.hashing_manager.verify_password(password, hashed, salt_bytes)
    
    def generate_secure_token(self, payload: Dict[str, Any], expires_in: int = 3600) -> str:
        """Generate secure token"""
        return self.token_manager.generate_token(payload, expires_in)
    
    def verify_secure_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify secure token"""
        return self.token_manager.verify_token(token)
    
    def mask_pii_data(self, data: Dict[str, str]) -> Dict[str, str]:
        """Mask personally identifiable information"""
        masked_data = {}
        
        for key, value in data.items():
            if 'email' in key.lower():
                masked_data[key] = self.masking_manager.mask_email(value)
            elif 'phone' in key.lower() or 'mobile' in key.lower():
                masked_data[key] = self.masking_manager.mask_phone(value)
            elif 'card' in key.lower() or 'credit' in key.lower():
                masked_data[key] = self.masking_manager.mask_credit_card(value)
            elif 'ssn' in key.lower() or 'social' in key.lower():
                masked_data[key] = self.masking_manager.mask_sensitive_data(value, visible_chars=4)
            else:
                masked_data[key] = value
        
        return masked_data


# ==================== EXPORTS ====================

__all__ = [
    # Algorithms
    'EncryptionAlgorithm',
    
    # Managers
    'BaseEncryptionManager',
    'FernetEncryptionManager',
    'AESEncryptionManager',
    'HashingManager',
    'SecureTokenManager',
    'DataMaskingManager',
    'KeyManager',
    
    # Service
    'EncryptionService',
]
