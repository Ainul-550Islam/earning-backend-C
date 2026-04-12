"""
Storage Encryption — Manages at-rest encryption for all stored backups.
"""
import os
import logging
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class StorageEncryption:
    """
    Manages encryption at rest for backup storage:
    - AES-256-GCM for file encryption
    - Key management with rotation support
    - Envelope encryption (data key encrypted by master key)
    - HSM integration support
    """

    KEY_ROTATION_DAYS = 90

    def __init__(self, config: dict):
        self.config = config
        self.master_key = config.get("master_key", "")
        self.kms_key_id = config.get("kms_key_id", "")  # AWS KMS key ID
        self.use_kms = bool(self.kms_key_id)
        self._key_cache: Dict[str, bytes] = {}

    def generate_data_key(self) -> dict:
        """
        Generate a data encryption key (DEK).
        If KMS configured: use envelope encryption.
        Otherwise: use local key derivation.
        """
        if self.use_kms:
            return self._generate_kms_data_key()
        else:
            return self._generate_local_data_key()

    def _generate_kms_data_key(self) -> dict:
        """Generate data key using AWS KMS (envelope encryption)."""
        import boto3
        kms = boto3.client("kms", region_name=self.config.get("region", "us-east-1"))
        response = kms.generate_data_key(
            KeyId=self.kms_key_id,
            KeySpec="AES_256",
        )
        plaintext_key = response["Plaintext"]          # Use for encryption
        encrypted_key = response["CiphertextBlob"]     # Store alongside data
        key_id = base64.b64encode(encrypted_key[:8]).decode()
        logger.info(f"KMS data key generated: key_id={key_id}...")
        return {
            "key_id": base64.b64encode(encrypted_key).decode(),
            "plaintext_key": plaintext_key,
            "encrypted_key": encrypted_key,
            "kms_key_id": self.kms_key_id,
            "generated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=self.KEY_ROTATION_DAYS)).isoformat(),
        }

    def _generate_local_data_key(self) -> dict:
        """Generate data key using local master key (PBKDF2)."""
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        salt = os.urandom(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000
        )
        master = self.master_key.encode() if isinstance(self.master_key, str) else self.master_key
        plaintext_key = kdf.derive(master)
        key_id = base64.b64encode(salt).decode()
        return {
            "key_id": key_id,
            "plaintext_key": plaintext_key,
            "salt": base64.b64encode(salt).decode(),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def decrypt_data_key(self, encrypted_key_b64: str) -> bytes:
        """Decrypt an encrypted data key using KMS or local master."""
        if self.use_kms:
            import boto3
            kms = boto3.client("kms", region_name=self.config.get("region", "us-east-1"))
            encrypted_key = base64.b64decode(encrypted_key_b64)
            response = kms.decrypt(CiphertextBlob=encrypted_key)
            return response["Plaintext"]
        else:
            # Derive key from salt stored in key_id
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            salt = base64.b64decode(encrypted_key_b64)
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
            master = self.master_key.encode() if isinstance(self.master_key, str) else self.master_key
            return kdf.derive(master)

    def encrypt_file(self, source_path: str, output_path: str = None) -> dict:
        """Encrypt a file using AES-256-GCM with a freshly generated data key."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if not output_path:
            output_path = source_path + ".enc"
        key_info = self.generate_data_key()
        dek = key_info["plaintext_key"]
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        with open(source_path, "rb") as f:
            plaintext = f.read()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        # Format: MAGIC(8) | KEY_ID_LEN(2) | KEY_ID | NONCE(12) | CIPHERTEXT
        MAGIC = b"DRENC2.0"
        key_id_bytes = key_info["key_id"].encode()
        key_id_len = len(key_id_bytes).to_bytes(2, "big")
        with open(output_path, "wb") as f:
            f.write(MAGIC)
            f.write(key_id_len)
            f.write(key_id_bytes)
            f.write(nonce)
            f.write(ciphertext)
        original_size = len(plaintext)
        encrypted_size = os.path.getsize(output_path)
        logger.info(f"Encrypted: {source_path} -> {output_path} ({original_size:,} bytes)")
        return {
            "output_path": output_path,
            "key_id": key_info["key_id"],
            "original_size_bytes": original_size,
            "encrypted_size_bytes": encrypted_size,
            "algorithm": "AES-256-GCM",
            "encrypted_at": datetime.utcnow().isoformat(),
        }

    def decrypt_file(self, source_path: str, output_path: str) -> dict:
        """Decrypt a file encrypted by encrypt_file."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        MAGIC = b"DRENC2.0"
        with open(source_path, "rb") as f:
            magic = f.read(8)
            if magic != MAGIC:
                raise ValueError("Not a valid DR encrypted file (wrong magic bytes)")
            key_id_len = int.from_bytes(f.read(2), "big")
            key_id = f.read(key_id_len).decode()
            nonce = f.read(12)
            ciphertext = f.read()
        dek = self.decrypt_data_key(key_id)
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(plaintext)
        logger.info(f"Decrypted: {source_path} -> {output_path} ({len(plaintext):,} bytes)")
        return {"output_path": output_path, "size_bytes": len(plaintext)}

    def rotate_encryption_key(self, backup_path: str, new_master_key: str = None) -> dict:
        """Re-encrypt a backup with a new key (key rotation)."""
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_plain = os.path.join(temp_dir, "plain_temp")
        temp_new_enc = backup_path + ".new"
        try:
            self.decrypt_file(backup_path, temp_plain)
            old_key = self.master_key
            if new_master_key:
                self.master_key = new_master_key
            result = self.encrypt_file(temp_plain, temp_new_enc)
            os.replace(temp_new_enc, backup_path)
            logger.info(f"Key rotated for: {backup_path}")
            return {"success": True, "path": backup_path, **result}
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.exists(temp_new_enc):
                os.remove(temp_new_enc)

    def verify_encryption(self, encrypted_path: str) -> dict:
        """Verify an encrypted file has the correct format."""
        MAGIC = b"DRENC2.0"
        try:
            with open(encrypted_path, "rb") as f:
                magic = f.read(8)
            is_encrypted = magic == MAGIC
            size = os.path.getsize(encrypted_path)
            return {
                "path": encrypted_path,
                "is_encrypted": is_encrypted,
                "algorithm": "AES-256-GCM" if is_encrypted else None,
                "size_bytes": size,
            }
        except Exception as e:
            return {"path": encrypted_path, "is_encrypted": False, "error": str(e)}
