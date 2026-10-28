"""
Gamification Encryption — Data encryption and security utilities.

This module provides encryption capabilities for the gamification system,
including data protection, secure hashing, and cryptographic operations.
"""

from __future__ import annotations
import json

import hashlib
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class EncryptionProvider:
    """Base class for encryption providers."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def encrypt(self, data: str, key: Optional[str] = None) -> str:
        """Encrypt data."""
        raise NotImplementedError("Subclasses must implement encrypt method")
    
    def decrypt(self, encrypted_data: str, key: Optional[str] = None) -> str:
        """Decrypt data."""
        raise NotImplementedError("Subclasses must implement decrypt method")
    
    def generate_key(self) -> str:
        """Generate encryption key."""
        raise NotImplementedError("Subclasses must implement generate_key method")


class AESEncryptionProvider(EncryptionProvider):
    """AES encryption provider using Fernet (symmetric encryption)."""
    
    def __init__(self, key: Optional[str] = None):
        super().__init__("aes")
        self.key = key or self._get_or_generate_key()
        self._validate_key()
        
        try:
            from cryptography.fernet import Fernet
            self.cipher = Fernet(self.key.encode())
        except ImportError:
            raise ImproperlyConfigured("cryptography package is required for AES encryption")
    
    def _get_or_generate_key(self) -> str:
        """Get encryption key from settings or generate a new one."""
        # Try to get from settings
        encryption_key = getattr(settings, 'GAMIFICATION_ENCRYPTION_KEY', None)
        
        if encryption_key:
            return encryption_key
        
        # Generate a new key
        key = self.generate_key()
        self.logger.warning("No encryption key found in settings. Generated a new key.")
        self.logger.warning("GAMIFICATION_ENCRYPTION_KEY is not set - using a temporary key. Set it in .env")
        
        return key
    
    def _validate_key(self) -> None:
        """Validate encryption key format."""
        try:
            from cryptography.fernet import Fernet
            Fernet(self.key.encode())
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid encryption key: {e}")
    
    def encrypt(self, data: str, key: Optional[str] = None) -> str:
        """Encrypt data using AES."""
        try:
            cipher = self._get_cipher(key)
            encrypted_data = cipher.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Error encrypting data: {e}")
            raise GamificationServiceError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str, key: Optional[str] = None) -> str:
        """Decrypt data using AES."""
        try:
            cipher = self._get_cipher(key)
            decrypted_data = cipher.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Error decrypting data: {e}")
            raise GamificationServiceError(f"Failed to decrypt data: {e}")
    
    def generate_key(self) -> str:
        """Generate a new AES encryption key."""
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            return key.decode()
        except Exception as e:
            self.logger.error(f"Error generating encryption key: {e}")
            raise GamificationServiceError(f"Failed to generate encryption key: {e}")
    
    def _get_cipher(self, key: Optional[str] = None) -> Any:
        """Get cipher instance."""
        from cryptography.fernet import Fernet
        cipher_key = key or self.key
        return Fernet(cipher_key.encode())


class HashProvider:
    """Hash provider for secure hashing operations."""
    
    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm
        self.logger = logging.getLogger(__name__)
    
    def hash(self, data: str, salt: Optional[str] = None) -> str:
        """Hash data with optional salt."""
        try:
            if salt:
                data = f"{salt}{data}"
            
            if self.algorithm == "sha256":
                return hashlib.sha256(data.encode()).hexdigest()
            elif self.algorithm == "sha512":
                return hashlib.sha512(data.encode()).hexdigest()
            elif self.algorithm == "md5":
                return hashlib.md5(data.encode()).hexdigest()
            else:
                raise ValueError(f"Unsupported hash algorithm: {self.algorithm}")
                
        except Exception as e:
            self.logger.error(f"Error hashing data: {e}")
            raise GamificationServiceError(f"Failed to hash data: {e}")
    
    def hash_with_salt(self, data: str, salt_length: int = 32) -> Tuple[str, str]:
        """Hash data with generated salt."""
        salt = self.generate_salt(salt_length)
        hash_value = self.hash(data, salt)
        return hash_value, salt
    
    def verify_hash(self, data: str, hash_value: str, salt: Optional[str] = None) -> bool:
        """Verify hash against data."""
        try:
            computed_hash = self.hash(data, salt)
            return secrets.compare_digest(computed_hash, hash_value)
        except Exception as e:
            self.logger.error(f"Error verifying hash: {e}")
            return False
    
    def generate_salt(self, length: int = 32) -> str:
        """Generate random salt."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class TokenGenerator:
    """Secure token generator for various purposes."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_api_token(self, length: int = 64) -> str:
        """Generate secure API token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def generate_session_token(self, user_id: str, expires_in: int = 3600) -> str:
        """Generate session token with expiration."""
        timestamp = str(int(timezone.now().timestamp()))
        expires_at = str(int(timezone.now().timestamp()) + expires_in)
        
        # Create token components
        components = [
            user_id,
            timestamp,
            expires_at,
            secrets.token_hex(16)  # Random signature
        ]
        
        # Hash the components
        hash_provider = HashProvider()
        token_hash = hash_provider.hash('|'.join(components))
        
        # Combine hash and signature
        token = f"{token_hash}.{secrets.token_hex(8)}"
        
        return token
    
    def generate_webhook_secret(self, length: int = 32) -> str:
        """Generate webhook secret."""
        return secrets.token_urlsafe(length)
    
    def generate_verification_code(self, length: int = 6) -> str:
        """Generate verification code."""
        return ''.join(secrets.choice('0123456789') for _ in range(length))
    
    def generate_referral_code(self, length: int = 8) -> str:
        """Generate referral code."""
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def generate_contest_code(self, length: int = 12) -> str:
        """Generate contest access code."""
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class SecureDataHandler:
    """Handler for secure data operations."""
    
    def __init__(self, encryption_provider: Optional[EncryptionProvider] = None):
        self.encryption_provider = encryption_provider or AESEncryptionProvider()
        self.hash_provider = HashProvider()
        self.token_generator = TokenGenerator()
        self.logger = logging.getLogger(__name__)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return self.encryption_provider.encrypt(data)
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return self.encryption_provider.decrypt(encrypted_data)
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash password with salt."""
        return self.hash_provider.hash_with_salt(password, salt_length=32)
    
    def verify_password(self, password: str, hash_value: str, salt: str) -> bool:
        """Verify password against hash."""
        return self.hash_provider.verify_hash(password, hash_value, salt)
    
    def hash_integrity_chain(self, data: Any, previous_hash: Optional[str] = None) -> str:
        """Create hash integrity chain for data."""
        try:
            # Convert data to string representation
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, sort_keys=True)
            else:
                data_str = str(data)
            
            # Include previous hash in chain if provided
            if previous_hash:
                data_str = f"{previous_hash}|{data_str}"
            
            # Hash the combined data
            hash_value = self.hash_provider.hash(data_str)
            
            return hash_value
            
        except Exception as e:
            self.logger.error(f"Error creating integrity chain: {e}")
            raise GamificationServiceError(f"Failed to create integrity chain: {e}")
    
    def verify_integrity_chain(self, data: Any, hash_value: str, previous_hash: Optional[str] = None) -> bool:
        """Verify integrity chain for data."""
        try:
            computed_hash = self.hash_integrity_chain(data, previous_hash)
            return secrets.compare_digest(computed_hash, hash_value)
        except Exception as e:
            self.logger.error(f"Error verifying integrity chain: {e}")
            return False
    
    def generate_secure_token(self, token_type: str = "api", **kwargs) -> str:
        """Generate secure token based on type."""
        if token_type == "api":
            return self.token_generator.generate_api_token(kwargs.get('length', 64))
        elif token_type == "session":
            return self.token_generator.generate_session_token(
                kwargs.get('user_id', ''),
                kwargs.get('expires_in', 3600)
            )
        elif token_type == "webhook":
            return self.token_generator.generate_webhook_secret(kwargs.get('length', 32))
        elif token_type == "verification":
            return self.token_generator.generate_verification_code(kwargs.get('length', 6))
        elif token_type == "referral":
            return self.token_generator.generate_referral_code(kwargs.get('length', 8))
        elif token_type == "contest":
            return self.token_generator.generate_contest_code(kwargs.get('length', 12))
        else:
            raise ValueError(f"Unknown token type: {token_type}")


class DataMasking:
    """Data masking utilities for sensitive information."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def mask_email(self, email: str) -> str:
        """Mask email address."""
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
            self.logger.error(f"Error masking email: {e}")
            return email
    
    def mask_phone(self, phone: str) -> str:
        """Mask phone number."""
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, phone))
            
            if len(digits) <= 4:
                return '*' * len(phone)
            
            # Keep first 2 and last 2 digits
            return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"
            
        except Exception as e:
            self.logger.error(f"Error masking phone: {e}")
            return phone
    
    def mask_credit_card(self, card_number: str) -> str:
        """Mask credit card number."""
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, card_number))
            
            if len(digits) != 16:
                return '*' * len(card_number)
            
            # Show only last 4 digits
            return f"{'*' * 12}{digits[-4:]}"
            
        except Exception as e:
            self.logger.error(f"Error masking credit card: {e}")
            return card_number
    
    def mask_ssn(self, ssn: str) -> str:
        """Mask Social Security Number."""
        try:
            # Remove non-digit characters
            digits = ''.join(filter(str.isdigit, ssn))
            
            if len(digits) != 9:
                return '*' * len(ssn)
            
            # Show only last 4 digits
            return f"{'*' * 5}{digits[-4:]}"
            
        except Exception as e:
            self.logger.error(f"Error masking SSN: {e}")
            return ssn
    
    def mask_general(self, data: str, visible_chars: int = 4, mask_char: str = '*') -> str:
        """General purpose masking."""
        try:
            if len(data) <= visible_chars:
                return mask_char * len(data)
            
            return data[:visible_chars] + mask_char * (len(data) - visible_chars)
            
        except Exception as e:
            self.logger.error(f"Error masking general data: {e}")
            return data


class SecurityAuditLogger:
    """Security audit logger for gamification system."""
    
    def __init__(self):
        self.logger = logging.getLogger("gamification.security")
    
    def log_encryption_event(self, event_type: str, user_id: Optional[str] = None,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """Log encryption-related events."""
        audit_data = {
            'event_type': f"encryption_{event_type}",
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        self.logger.info(f"Security Audit: {json.dumps(audit_data)}")
    
    def log_authentication_event(self, event_type: str, user_id: str,
                             ip_address: Optional[str] = None,
                             user_agent: Optional[str] = None,
                             success: bool = True) -> None:
        """Log authentication events."""
        audit_data = {
            'event_type': f"auth_{event_type}",
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'timestamp': timezone.now().isoformat()
        }
        
        if success:
            self.logger.info(f"Security Audit: {json.dumps(audit_data)}")
        else:
            self.logger.warning(f"Security Audit: {json.dumps(audit_data)}")
    
    def log_data_access_event(self, event_type: str, user_id: Optional[str] = None,
                           resource_type: Optional[str] = None,
                           resource_id: Optional[str] = None,
                           action: str = "read") -> None:
        """Log data access events."""
        audit_data = {
            'event_type': f"data_access_{event_type}",
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
            'timestamp': timezone.now().isoformat()
        }
        
        self.logger.info(f"Security Audit: {json.dumps(audit_data)}")
    
    def log_permission_event(self, event_type: str, user_id: str,
                           permission: str, resource: str,
                           granted: bool) -> None:
        """Log permission check events."""
        audit_data = {
            'event_type': f"permission_{event_type}",
            'user_id': user_id,
            'permission': permission,
            'resource': resource,
            'granted': granted,
            'timestamp': timezone.now().isoformat()
        }
        
        if granted:
            self.logger.info(f"Security Audit: {json.dumps(audit_data)}")
        else:
            self.logger.warning(f"Security Audit: {json.dumps(audit_data)}")
    
    def log_violation_event(self, violation_type: str, user_id: Optional[str] = None,
                           severity: str = "medium", details: Optional[Dict[str, Any]] = None) -> None:
        """Log security violation events."""
        audit_data = {
            'event_type': f"violation_{violation_type}",
            'user_id': user_id,
            'severity': severity,
            'details': details or {},
            'timestamp': timezone.now().isoformat()
        }
        
        if severity in ['high', 'critical']:
            self.logger.error(f"Security Audit: {json.dumps(audit_data)}")
        else:
            self.logger.warning(f"Security Audit: {json.dumps(audit_data)}")


class ComplianceChecker:
    """Compliance checker for data protection regulations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.audit_logger = SecurityAuditLogger()
    
    def check_gdpr_compliance(self, data_type: str, user_id: str,
                             consent: Optional[bool] = None) -> Dict[str, Any]:
        """Check GDPR compliance for data operations."""
        compliance_result = {
            'compliant': True,
            'violations': [],
            'recommendations': [],
            'data_type': data_type,
            'user_id': user_id,
            'timestamp': timezone.now().isoformat()
        }
        
        # Check for consent
        if consent is None:
            compliance_result['violations'].append("No consent recorded")
            compliance_result['recommendations'].append("Obtain explicit user consent")
            compliance_result['compliant'] = False
        
        # Check data minimization
        if data_type in ['email', 'phone', 'address']:
            if not consent:
                compliance_result['violations'].append(f"Processing {data_type} without consent")
                compliance_result['compliant'] = False
        
        # Log compliance check
        self.audit_logger.log_data_access_event(
            "gdpr_check",
            user_id,
            data_type,
            None,
            "compliance_check"
        )
        
        return compliance_result
    
    def check_data_retention(self, data_type: str, created_at: datetime,
                           max_retention_days: int = 365) -> Dict[str, Any]:
        """Check data retention compliance."""
        compliance_result = {
            'compliant': True,
            'violations': [],
            'recommendations': [],
            'data_type': data_type,
            'created_at': created_at.isoformat(),
            'max_retention_days': max_retention_days,
            'timestamp': timezone.now().isoformat()
        }
        
        # Check if data exceeds retention period
        retention_date = created_at + timedelta(days=max_retention_days)
        if timezone.now() > retention_date:
            compliance_result['violations'].append("Data exceeds retention period")
            compliance_result['recommendations'].append("Delete or anonymize expired data")
            compliance_result['compliant'] = False
        
        return compliance_result
    
    def anonymize_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize user data for privacy compliance."""
        anonymized_data = {}
        
        for key, value in user_data.items():
            if key in ['email', 'phone', 'address', 'name', 'ssn']:
                # Mask sensitive fields
                masking = DataMasking()
                
                if key == 'email':
                    anonymized_data[key] = masking.mask_email(str(value))
                elif key == 'phone':
                    anonymized_data[key] = masking.mask_phone(str(value))
                elif key == 'name':
                    anonymized_data[key] = masking.mask_general(str(value), 2)
                else:
                    anonymized_data[key] = masking.mask_general(str(value))
            else:
                # Keep non-sensitive fields
                anonymized_data[key] = value
        
        return anonymized_data


# Global instances
encryption_provider = AESEncryptionProvider()
hash_provider = HashProvider()
token_generator = TokenGenerator()
secure_data_handler = SecureDataHandler(encryption_provider)
data_masking = DataMasking()
security_audit_logger = SecurityAuditLogger()
compliance_checker = ComplianceChecker()


# Convenience functions
def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """Encrypt data using AES."""
    return encryption_provider.encrypt(data, key)


def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
    """Decrypt data using AES."""
    return encryption_provider.decrypt(encrypted_data, key)


def hash_data(data: str, salt: Optional[str] = None) -> str:
    """Hash data using SHA-256."""
    return hash_provider.hash(data, salt)


def hash_with_salt(data: str, salt_length: int = 32) -> Tuple[str, str]:
    """Hash data with generated salt."""
    return hash_provider.hash_with_salt(data, salt_length)


def verify_hash(data: str, hash_value: str, salt: Optional[str] = None) -> bool:
    """Verify hash against data."""
    return hash_provider.verify_hash(data, hash_value, salt)


def generate_token(token_type: str = "api", **kwargs) -> str:
    """Generate secure token."""
    return secure_data_handler.generate_secure_token(token_type, **kwargs)


def create_integrity_hash(data: Any, previous_hash: Optional[str] = None) -> str:
    """Create integrity hash for data."""
    return secure_data_handler.hash_integrity_chain(data, previous_hash)


def verify_integrity_hash(data: Any, hash_value: str, previous_hash: Optional[str] = None) -> bool:
    """Verify integrity hash for data."""
    return secure_data_handler.verify_integrity_chain(data, hash_value, previous_hash)


def mask_sensitive_data(data: str, data_type: str = "general") -> str:
    """Mask sensitive data."""
    masking = DataMasking()
    
    if data_type == "email":
        return masking.mask_email(data)
    elif data_type == "phone":
        return masking.mask_phone(data)
    elif data_type == "credit_card":
        return masking.mask_credit_card(data)
    elif data_type == "ssn":
        return masking.mask_ssn(data)
    else:
        return masking.mask_general(data)


def log_security_event(event_type: str, **kwargs) -> None:
    """Log security event."""
    if event_type.startswith("encryption"):
        security_audit_logger.log_encryption_event(event_type, **kwargs)
    elif event_type.startswith("auth"):
        security_audit_logger.log_authentication_event(event_type, **kwargs)
    elif event_type.startswith("data_access"):
        security_audit_logger.log_data_access_event(event_type, **kwargs)
    elif event_type.startswith("permission"):
        security_audit_logger.log_permission_event(event_type, **kwargs)
    elif event_type.startswith("violation"):
        security_audit_logger.log_violation_event(event_type, **kwargs)


def check_gdpr_compliance(data_type: str, user_id: str, consent: Optional[bool] = None) -> Dict[str, Any]:
    """Check GDPR compliance."""
    return compliance_checker.check_gdpr_compliance(data_type, user_id, consent)


def anonymize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Anonymize user data."""
    return compliance_checker.anonymize_user_data(user_data)
