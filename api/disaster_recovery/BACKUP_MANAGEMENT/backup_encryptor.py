"""
Backup Encryptor — AES-256-GCM encryption for backup files
"""
import logging
import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

logger = logging.getLogger(__name__)

MAGIC = b"DRENC1"       # File magic bytes to identify encrypted backups
NONCE_SIZE = 12
SALT_SIZE = 32
KEY_SIZE = 32            # 256-bit


class BackupEncryptor:
    """
    AES-256-GCM authenticated encryption for backup files.
    File format: MAGIC(6) | SALT(32) | NONCE(12) | CIPHERTEXT+TAG
    """

    def __init__(self, master_key: str):
        self.master_key = master_key.encode() if isinstance(master_key, str) else master_key

    def encrypt_file(self, source_path: str, output_path: str = None) -> dict:
        if not output_path:
            output_path = source_path + ".enc"
        salt = os.urandom(SALT_SIZE)
        nonce = os.urandom(NONCE_SIZE)
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)
        with open(source_path, "rb") as f:
            plaintext = f.read()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        with open(output_path, "wb") as f:
            f.write(MAGIC)
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
        original_size = len(plaintext)
        encrypted_size = os.path.getsize(output_path)
        logger.info(f"Encrypted: {source_path} -> {output_path} ({original_size} bytes)")
        return {
            "output_path": output_path,
            "original_size_bytes": original_size,
            "encrypted_size_bytes": encrypted_size,
            "algorithm": "AES-256-GCM",
        }

    def decrypt_file(self, source_path: str, output_path: str) -> str:
        with open(source_path, "rb") as f:
            magic = f.read(len(MAGIC))
            if magic != MAGIC:
                raise ValueError("Not a valid DR encrypted file")
            salt = f.read(SALT_SIZE)
            nonce = f.read(NONCE_SIZE)
            ciphertext = f.read()
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        with open(output_path, "wb") as f:
            f.write(plaintext)
        logger.info(f"Decrypted: {source_path} -> {output_path}")
        return output_path

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(self.master_key)

    def is_encrypted(self, path: str) -> bool:
        try:
            with open(path, "rb") as f:
                return f.read(len(MAGIC)) == MAGIC
        except Exception:
            return False
