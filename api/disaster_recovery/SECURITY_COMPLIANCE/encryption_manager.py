"""
Encryption Manager — Central encryption/decryption orchestrator for the DR system.
Coordinates between key management, backup encryption, and storage encryption.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Central encryption management for the DR system.
    Provides a unified API for:
    - File encryption/decryption (AES-256-GCM)
    - Key retrieval and rotation coordination
    - Encryption health reporting
    - KMS integration (AWS KMS, Azure Key Vault, GCP KMS)
    - Envelope encryption for large data sets
    """

    def __init__(self, config: dict):
        self.config = config
        self.master_key = config.get("master_key", "")
        self.kms_provider = config.get("kms_provider", "local")  # local, aws, azure, gcp
        self.kms_key_id = config.get("kms_key_id", "")
        self.key_rotation_days = config.get("key_rotation_days", 90)
        self._key_cache: Dict[str, bytes] = {}
        self._encryptor = None

    @property
    def encryptor(self):
        """Lazy-initialize the backup encryptor."""
        if not self._encryptor:
            from ..BACKUP_MANAGEMENT.backup_encryptor import BackupEncryptor
            self._encryptor = BackupEncryptor(self.master_key)
        return self._encryptor

    def encrypt_file(self, source_path: str, output_path: str = None) -> dict:
        """Encrypt a file using the configured encryption backend."""
        logger.info(f"Encrypting file: {source_path}")
        if self.kms_provider != "local" and self.kms_key_id:
            return self._encrypt_with_kms(source_path, output_path)
        return self.encryptor.encrypt_file(source_path, output_path)

    def decrypt_file(self, source_path: str, output_path: str) -> str:
        """Decrypt a file using the configured encryption backend."""
        logger.info(f"Decrypting file: {source_path}")
        if self.kms_provider != "local" and self.kms_key_id:
            return self._decrypt_with_kms(source_path, output_path)
        return self.encryptor.decrypt_file(source_path, output_path)

    def is_encrypted(self, file_path: str) -> bool:
        """Check if a file is encrypted by this system."""
        return self.encryptor.is_encrypted(file_path)

    def verify_encryption(self, file_path: str) -> dict:
        """Verify a file's encryption status and integrity."""
        from ..DATA_STORAGE.storage_encryption import StorageEncryption
        se = StorageEncryption(self.config)
        return se.verify_encryption(file_path)

    def rotate_master_key(self, new_key: str,
                           files_to_reencrypt: list = None) -> dict:
        """
        Rotate the master encryption key.
        Re-encrypts all specified files with the new key.
        """
        logger.warning(f"KEY ROTATION: Rotating master encryption key")
        old_key = self.master_key
        reencrypted = 0
        failed = 0
        if files_to_reencrypt:
            from ..DATA_STORAGE.storage_encryption import StorageEncryption
            old_se = StorageEncryption({**self.config, "master_key": old_key})
            for file_path in files_to_reencrypt:
                try:
                    old_se.rotate_encryption_key(file_path, new_key)
                    reencrypted += 1
                except Exception as e:
                    logger.error(f"Re-encryption failed for {file_path}: {e}")
                    failed += 1
        # Update current key
        self.master_key = new_key
        self._encryptor = None  # Force re-init with new key
        self._key_cache.clear()
        logger.info(
            f"Key rotation complete: {reencrypted} files re-encrypted, "
            f"{failed} failed"
        )
        return {
            "success": failed == 0,
            "reencrypted": reencrypted,
            "failed": failed,
            "rotated_at": datetime.utcnow().isoformat(),
            "next_rotation": (datetime.utcnow() + timedelta(days=self.key_rotation_days)).isoformat(),
        }

    def get_encryption_health(self) -> dict:
        """Return encryption health status for monitoring."""
        return {
            "encryption_enabled": bool(self.master_key or self.kms_key_id),
            "algorithm": "AES-256-GCM",
            "kms_provider": self.kms_provider,
            "kms_configured": bool(self.kms_key_id),
            "key_rotation_days": self.key_rotation_days,
            "status": "healthy" if (self.master_key or self.kms_key_id) else "not_configured",
        }

    def generate_data_encryption_key(self) -> dict:
        """Generate a fresh Data Encryption Key (DEK) for envelope encryption."""
        if self.kms_provider == "aws" and self.kms_key_id:
            return self._aws_kms_generate_dek()
        elif self.kms_provider == "azure":
            return self._azure_kv_generate_dek()
        # Local fallback
        dek = os.urandom(32)
        import base64
        key_id = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
        return {
            "key_id": key_id,
            "plaintext_key": dek,
            "provider": "local",
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _encrypt_with_kms(self, source_path: str, output_path: str = None) -> dict:
        """Encrypt using KMS-generated data key (envelope encryption)."""
        from ..DATA_STORAGE.storage_encryption import StorageEncryption
        se = StorageEncryption({**self.config, "kms_key_id": self.kms_key_id})
        return se.encrypt_file(source_path, output_path)

    def _decrypt_with_kms(self, source_path: str, output_path: str) -> str:
        """Decrypt using KMS-stored key."""
        from ..DATA_STORAGE.storage_encryption import StorageEncryption
        se = StorageEncryption({**self.config, "kms_key_id": self.kms_key_id})
        result = se.decrypt_file(source_path, output_path)
        return result.get("output_path", output_path)

    def _aws_kms_generate_dek(self) -> dict:
        """Generate DEK using AWS KMS."""
        import boto3
        kms = boto3.client("kms", region_name=self.config.get("region", "us-east-1"))
        response = kms.generate_data_key(KeyId=self.kms_key_id, KeySpec="AES_256")
        return {
            "key_id": self.kms_key_id,
            "plaintext_key": response["Plaintext"],
            "encrypted_key": response["CiphertextBlob"],
            "provider": "aws_kms",
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _azure_kv_generate_dek(self) -> dict:
        """Generate DEK using Azure Key Vault."""
        return {
            "key_id": self.kms_key_id,
            "provider": "azure_key_vault",
            "generated_at": datetime.utcnow().isoformat(),
            "note": "Azure Key Vault DEK generation requires azure-keyvault-keys SDK",
        }
