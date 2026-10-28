# api/referral/encryption.py
# Encryption utilities for sensitive referral data
# Referral codes, IP addresses, device fingerprints, payout accounts
# ============================================================

import base64
import hashlib
import hmac
import logging
import secrets
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

_SECRET = getattr(settings, 'SECRET_KEY', 'default').encode()[:32]


def sign_payload(payload: str) -> str:
    """
    Create HMAC-SHA256 signature for webhook payload verification.
    Usage: sign_payload(json.dumps(data))
    """
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return sig


def verify_signature(payload: str, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature.
    Returns True if signature matches.
    """
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)


def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def hash_sensitive_data(data: str, salt: str = '') -> str:
    """
    One-way hash of sensitive data (IP, device fingerprint).
    Used for GDPR-compliant storage — can detect duplicates, cannot reverse.
    """
    combined = f'{salt}{data}{_SECRET.decode()}'
    return hashlib.sha256(combined.encode()).hexdigest()


def encrypt_payout_account(account: str) -> str:
    """
    Encrypt payout account number for storage.
    Uses Fernet symmetric encryption if cryptography is installed.
    Falls back to base64 + HMAC (not secure for production without real encryption).
    """
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(
            hashlib.sha256(_SECRET).digest()
        )
        fernet = Fernet(key)
        return fernet.encrypt(account.encode()).decode()
    except ImportError:
        # Fallback: base64 (NOT secure — install cryptography for production)
        encoded = base64.b64encode(account.encode()).decode()
        return f'b64:{encoded}'


def decrypt_payout_account(encrypted: str) -> Optional[str]:
    """Decrypt payout account number."""
    try:
        if encrypted.startswith('b64:'):
            return base64.b64decode(encrypted[4:]).decode()
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(
            hashlib.sha256(_SECRET).digest()
        )
        fernet = Fernet(key)
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f'[Encryption] Decrypt failed: {e}')
        return None


def mask_referral_code_for_display(code: str) -> str:
    """
    Partially mask referral code for analytics display.
    'EARN12345678' → 'EARN****5678'
    """
    if len(code) <= 8:
        return code
    return code[:4] + '****' + code[-4:]