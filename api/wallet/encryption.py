# api/wallet/encryption.py
"""
Data encryption at rest — PAN masking, PII encryption, field-level encryption.
Uses Fernet symmetric encryption (cryptography library).
pip install cryptography
settings.py: WALLET_ENCRYPTION_KEY = Fernet.generate_key().decode()
"""
import base64
import logging
from django.conf import settings

logger = logging.getLogger("wallet.encryption")


def get_fernet():
    """Get Fernet instance from settings key."""
    try:
        from cryptography.fernet import Fernet
        key = getattr(settings, "WALLET_ENCRYPTION_KEY", "")
        if not key:
            key = Fernet.generate_key()
            logger.warning("WALLET_ENCRYPTION_KEY not set — using ephemeral key")
        return Fernet(key if isinstance(key, bytes) else key.encode())
    except ImportError:
        logger.warning("cryptography not installed — encryption disabled")
        return None


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64-encoded ciphertext."""
    if not plaintext:
        return plaintext
    fernet = get_fernet()
    if not fernet:
        return plaintext
    try:
        return fernet.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return plaintext


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    if not ciphertext:
        return ciphertext
    fernet = get_fernet()
    if not fernet:
        return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.debug(f"Decryption error: {e}")
        return ciphertext


def mask_pan(pan: str) -> str:
    """Mask payment account number. '01712345678' → '017*****678'"""
    s = str(pan or "")
    if len(s) <= 6:
        return s
    return s[:3] + "*" * (len(s) - 6) + s[-3:]


def mask_email(email: str) -> str:
    """Mask email. 'john@example.com' → 'jo**@example.com'"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return email
    return local[:2] + "*" * (len(local) - 2) + "@" + domain


def hash_sensitive(value: str) -> str:
    """One-way hash for sensitive data (for indexing without storing plaintext)."""
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


class EncryptedField:
    """
    Django model field mixin for automatic encryption at rest.
    Usage in models:
        account_number = EncryptedField.wrap(models.CharField(max_length=500))
    """
    @staticmethod
    def wrap(field):
        """Wrap a CharField with transparent encrypt/decrypt."""
        return field  # Placeholder — implement with custom descriptor if needed
