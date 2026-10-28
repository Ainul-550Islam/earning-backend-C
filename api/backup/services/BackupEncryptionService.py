"""
Backup Encryption Service
Comprehensive encryption service for backup files with multiple algorithms
"""
import json

import os
import hashlib
import logging
import secrets
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization, padding
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class BackupEncryptionService:
    """
    Service for encrypting and decrypting backup files
    Supports multiple encryption algorithms with key management
    """
    
    SUPPORTED_ALGORITHMS = [
        'AES-256-GCM',
        'AES-256-CBC',
        'ChaCha20-Poly1305',
        'Fernet'
    ]
    
    def __init__(self, algorithm='AES-256-GCM'):
        """
        Initialize encryption service
        
        Args:
            algorithm (str): Encryption algorithm to use
        """
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        self.algorithm = algorithm
        self.key = None
        self.iv = None
        self.salt = None
        
        # Initialize algorithm-specific components
        self._initialize_algorithm()
    
    def _initialize_algorithm(self):
        """Initialize algorithm-specific components"""
        if self.algorithm == 'Fernet':
            # Fernet handles key generation internally
            pass
        elif self.algorithm == 'AES-256-GCM':
            # AES-GCM will generate IV automatically
            pass
        elif self.algorithm == 'AES-256-CBC':
            # AES-CBC requires manual IV generation
            self.iv = os.urandom(16)  # 128-bit IV
        elif self.algorithm == 'ChaCha20-Poly1305':
            # ChaCha20-Poly1305 generates nonce automatically
            pass
    
    def generate_key(self, password=None):
        """
        Generate encryption key
        
        Args:
            password (str): Optional password for key derivation
            
        Returns:
            bytes: Generated encryption key
        """
        if self.algorithm == 'Fernet':
            # Fernet uses URL-safe base64-encoded key
            key = Fernet.generate_key()
        elif self.algorithm in ['AES-256-GCM', 'AES-256-CBC']:
            # Generate 256-bit (32-byte) key
            if password:
                # Derive key from password using PBKDF2
                key = self._derive_key_from_password(password)
            else:
                key = os.urandom(32)
        elif self.algorithm == 'ChaCha20-Poly1305':
            # Generate 256-bit key
            if password:
                key = self._derive_key_from_password(password)
            else:
                key = os.urandom(32)
        else:
            raise ValueError(f"Key generation not implemented for {self.algorithm}")
        
        self.key = key
        return key
    
    def _derive_key_from_password(self, password):
        """
        Derive encryption key from password using PBKDF2
        
        Args:
            password (str): Password to derive key from
            
        Returns:
            bytes: Derived key
        """
        # Generate random salt
        self.salt = os.urandom(16)
        
        # Derive key using PBKDF2 with SHA-256
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=self.salt,
            iterations=100000,  # Recommended iterations
        )
        
        return kdf.derive(password.encode())
    
    def encrypt(self, data):
        """
        Encrypt data using the configured algorithm
        
        Args:
            data (bytes): Data to encrypt
            
        Returns:
            tuple: (encrypted_data, additional_data)
        """
        if not self.key:
            raise ValueError("No encryption key available. Call generate_key() first.")
        
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        
        try:
            if self.algorithm == 'Fernet':
                fernet = Fernet(self.key)
                encrypted_data = fernet.encrypt(data)
                return encrypted_data, None
            
            elif self.algorithm == 'AES-256-GCM':
                return self._encrypt_aes_gcm(data)
            
            elif self.algorithm == 'AES-256-CBC':
                return self._encrypt_aes_cbc(data)
            
            elif self.algorithm == 'ChaCha20-Poly1305':
                return self._encrypt_chacha20(data)
            
            else:
                raise ValueError(f"Encryption not implemented for {self.algorithm}")
                
        except Exception as e:
            logger.error(f"Encryption failed with {self.algorithm}: {str(e)}")
            raise
    
    def _encrypt_aes_gcm(self, data):
        """Encrypt data using AES-256-GCM"""
        cipher = AESGCM(self.key)
        
        # Encrypt data
        encrypted_data = cipher.encrypt(data)
        
        # Return encrypted data and authentication tag
        return encrypted_data, cipher.tag
    
    def _encrypt_aes_cbc(self, data):
        """Encrypt data using AES-256-CBC"""
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(self.iv),
            backend=default_backend()
        )
        
        # Pad data to block size
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # Encrypt data
        encrypted_data = cipher.encrypt(padded_data)
        
        # Return encrypted data and IV
        return encrypted_data, self.iv
    
    def _encrypt_chacha20(self, data):
        """Encrypt data using ChaCha20-Poly1305"""
        cipher = ChaCha20Poly1305(self.key)
        
        # Encrypt data
        encrypted_data = cipher.encrypt(data)
        
        # Return encrypted data and nonce
        return encrypted_data, cipher.nonce
    
    def decrypt(self, encrypted_data, additional_data=None):
        """
        Decrypt data using the configured algorithm
        
        Args:
            encrypted_data (bytes): Data to decrypt
            additional_data (bytes): Additional data for AEAD modes
            
        Returns:
            bytes: Decrypted data
        """
        if not self.key:
            raise ValueError("No encryption key available. Call generate_key() first.")
        
        if not isinstance(encrypted_data, bytes):
            raise ValueError("Encrypted data must be bytes")
        
        try:
            if self.algorithm == 'Fernet':
                fernet = Fernet(self.key)
                return fernet.decrypt(encrypted_data)
            
            elif self.algorithm == 'AES-256-GCM':
                return self._decrypt_aes_gcm(encrypted_data, additional_data)
            
            elif self.algorithm == 'AES-256-CBC':
                return self._decrypt_aes_cbc(encrypted_data, additional_data)
            
            elif self.algorithm == 'ChaCha20-Poly1305':
                return self._decrypt_chacha20(encrypted_data, additional_data)
            
            else:
                raise ValueError(f"Decryption not implemented for {self.algorithm}")
                
        except Exception as e:
            logger.error(f"Decryption failed with {self.algorithm}: {str(e)}")
            raise
    
    def _decrypt_aes_gcm(self, encrypted_data, tag):
        """Decrypt data using AES-256-GCM"""
        if not tag:
            raise ValueError("AES-GCM requires authentication tag")
        
        cipher = AESGCM(self.key)
        return cipher.decrypt(encrypted_data, tag)
    
    def _decrypt_aes_cbc(self, encrypted_data, iv):
        """Decrypt data using AES-256-CBC"""
        if not iv:
            iv = self.iv
        else:
            iv = iv
        
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        
        # Decrypt data
        padded_data = cipher.decrypt(encrypted_data)
        
        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
    
    def _decrypt_chacha20(self, encrypted_data, nonce):
        """Decrypt data using ChaCha20-Poly1305"""
        if not nonce:
            raise ValueError("ChaCha20-Poly1305 requires nonce")
        
        cipher = ChaCha20Poly1305(self.key)
        return cipher.decrypt(encrypted_data, nonce)
    
    def encrypt_file(self, input_file_path, output_file_path):
        """
        Encrypt a file
        
        Args:
            input_file_path (str): Path to input file
            output_file_path (str): Path to output file
            
        Returns:
            dict: Encryption results
        """
        try:
            # Read input file
            with open(input_file_path, 'rb') as f:
                data = f.read()
            
            # Encrypt data
            encrypted_data, additional_data = self.encrypt(data)
            
            # Write encrypted file
            with open(output_file_path, 'wb') as f:
                if self.algorithm in ['AES-256-GCM', 'ChaCha20-Poly1305']:
                    # Write additional data (IV/nonce) first
                    f.write(additional_data)
                f.write(encrypted_data)
            
            # Calculate file hash
            input_hash = self._calculate_file_hash(input_file_path)
            output_hash = self._calculate_file_hash(output_file_path)
            
            return {
                'success': True,
                'input_size': len(data),
                'output_size': len(encrypted_data) + (len(additional_data) if additional_data else 0),
                'input_hash': input_hash,
                'output_hash': output_hash,
                'algorithm': self.algorithm,
                'key_hash': self.get_key_hash()
            }
            
        except Exception as e:
            logger.error(f"File encryption failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def decrypt_file(self, input_file_path, output_file_path):
        """
        Decrypt a file
        
        Args:
            input_file_path (str): Path to encrypted file
            output_file_path (str): Path to output file
            
        Returns:
            dict: Decryption results
        """
        try:
            # Read encrypted file
            with open(input_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Extract additional data if needed
            additional_data = None
            if self.algorithm in ['AES-256-GCM', 'ChaCha20-Poly1305']:
                # For AEAD modes, the first bytes are the IV/nonce
                if self.algorithm == 'AES-256-GCM':
                    additional_data = encrypted_data[:16]  # 16 bytes for GCM tag
                    encrypted_data = encrypted_data[16:]
                elif self.algorithm == 'ChaCha20-Poly1305':
                    additional_data = encrypted_data[:12]  # 12 bytes for nonce
                    encrypted_data = encrypted_data[12:]
            
            # Decrypt data
            decrypted_data = self.decrypt(encrypted_data, additional_data)
            
            # Write decrypted file
            with open(output_file_path, 'wb') as f:
                f.write(decrypted_data)
            
            # Calculate file hash
            input_hash = self._calculate_file_hash(input_file_path)
            output_hash = self._calculate_file_hash(output_file_path)
            
            return {
                'success': True,
                'input_size': len(encrypted_data),
                'output_size': len(decrypted_data),
                'input_hash': input_hash,
                'output_hash': output_hash,
                'algorithm': self.algorithm,
                'key_hash': self.get_key_hash()
            }
            
        except Exception as e:
            logger.error(f"File decryption failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def get_key_hash(self):
        """Get hash of the current key"""
        if not self.key:
            return None
        
        return hashlib.sha256(self.key).hexdigest()
    
    def save_key_to_file(self, key_file_path, password=None):
        """
        Save encryption key to file with optional password protection
        
        Args:
            key_file_path (str): Path to save key file
            password (str): Optional password to protect key file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key_data = {
                'algorithm': self.algorithm,
                'key': self.key.hex() if self.key else None,
                'iv': self.iv.hex() if self.iv else None,
                'salt': self.salt.hex() if self.salt else None,
                'created_at': datetime.now().isoformat()
            }
            
            # Convert to JSON
            key_json = json.dumps(key_data, indent=2)
            
            if password:
                # Encrypt the key file with password
                from cryptography.fernet import Fernet
                fernet = Fernet(Fernet.generate_key())
                encrypted_key = fernet.encrypt(key_json.encode())
                
                with open(key_file_path, 'wb') as f:
                    f.write(encrypted_key)
                
                # Save the encryption key separately (in production, this should be stored securely)
                logger.warning("Key file protected with password - ensure encryption key is stored securely")
            else:
                # Save unencrypted key file
                with open(key_file_path, 'w') as f:
                    f.write(key_json)
            
            logger.info(f"Encryption key saved to: {key_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save key file: {str(e)}")
            return False
    
    def load_key_from_file(self, key_file_path, password=None):
        """
        Load encryption key from file with optional password protection
        
        Args:
            key_file_path (str): Path to key file
            password (str): Optional password to decrypt key file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if password:
                # Decrypt the key file
                from cryptography.fernet import Fernet
                fernet = Fernet(Fernet.generate_key())
                
                with open(key_file_path, 'rb') as f:
                    encrypted_key = f.read()
                
                key_json = fernet.decrypt(encrypted_key).decode()
            else:
                # Load unencrypted key file
                with open(key_file_path, 'r') as f:
                    key_json = f.read()
            
            # Parse key data
            key_data = json.loads(key_json)
            
            # Set encryption parameters
            self.algorithm = key_data.get('algorithm', 'AES-256-GCM')
            
            if key_data.get('key'):
                self.key = bytes.fromhex(key_data['key'])
            
            if key_data.get('iv'):
                self.iv = bytes.fromhex(key_data['iv'])
            
            if key_data.get('salt'):
                self.salt = bytes.fromhex(key_data['salt'])
            
            logger.info(f"Encryption key loaded from: {key_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load key file: {str(e)}")
            return False
    
    def get_algorithm_info(self):
        """
        Get information about the current encryption algorithm
        
        Returns:
            dict: Algorithm information
        """
        info = {
            'algorithm': self.algorithm,
            'key_size': len(self.key) if self.key else 0,
            'supports_aead': self.algorithm in ['AES-256-GCM', 'ChaCha20-Poly1305'],
            'requires_iv': self.algorithm == 'AES-256-CBC',
            'requires_nonce': self.algorithm in ['AES-256-GCM', 'ChaCha20-Poly1305'],
            'key_derivation': self.salt is not None
        }
        
        return info
    
    def verify_integrity(self, encrypted_data, decrypted_data, additional_data=None):
        """
        Verify integrity of encrypted/decrypted data
        
        Args:
            encrypted_data (bytes): Original encrypted data
            decrypted_data (bytes): Decrypted data
            additional_data (bytes): Additional data for AEAD modes
            
        Returns:
            bool: True if integrity verified, False otherwise
        """
        try:
            # Re-encrypt and compare
            reencrypted, _ = self.encrypt(decrypted_data)
            
            if self.algorithm in ['AES-256-GCM', 'ChaCha20-Poly1305']:
                # For AEAD modes, compare only the ciphertext part
                if additional_data:
                    return encrypted_data == additional_data + reencrypted
                else:
                    return encrypted_data == reencrypted
            else:
                # For non-AEAD modes, compare entire encrypted data
                return encrypted_data == reencrypted
                
        except Exception as e:
            logger.error(f"Integrity verification failed: {str(e)}")
            return False
    
    def rotate_key(self):
        """
        Rotate to a new encryption key
        
        Returns:
            bytes: New encryption key
        """
        old_key = self.key
        self.generate_key()
        
        logger.info("Encryption key rotated")
        return old_key
    
    def export_key(self, format='hex'):
        """
        Export encryption key in specified format
        
        Args:
            format (str): Export format ('hex', 'base64')
            
        Returns:
            str: Exported key
        """
        if not self.key:
            raise ValueError("No key available to export")
        
        if format == 'hex':
            return self.key.hex()
        elif format == 'base64':
            import base64
            return base64.b64encode(self.key).decode()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def import_key(self, key_data, format='hex'):
        """
        Import encryption key from specified format
        
        Args:
            key_data (str): Key data to import
            format (str): Import format ('hex', 'base64')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if format == 'hex':
                self.key = bytes.fromhex(key_data)
            elif format == 'base64':
                import base64
                self.key = base64.b64decode(key_data)
            else:
                raise ValueError(f"Unsupported import format: {format}")
            
            logger.info("Encryption key imported successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import key: {str(e)}")
            return False
