# kyc/utils/encryption_utils.py  ── WORLD #1
"""Encryption/hashing utilities for KYC sensitive data"""
import hashlib
import hmac
import secrets
import logging

logger = logging.getLogger(__name__)


def hash_otp(otp: str, salt: str = '') -> str:
    """Hash OTP with SHA-256 + salt. Never store plain OTP."""
    raw = f"{salt}:{otp}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def verify_otp_hash(otp: str, stored_hash: str, salt: str = '') -> bool:
    raw = f"{salt}:{otp}".encode('utf-8')
    computed = hashlib.sha256(raw).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


def generate_otp(length: int = 6) -> str:
    """Generate cryptographically secure numeric OTP."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


def generate_secret_key(length: int = 32) -> str:
    """Generate random secret key for webhook signing."""
    return secrets.token_hex(length)


def generate_webhook_signature(payload: str, secret: str) -> str:
    """HMAC-SHA256 webhook payload signature."""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(payload: str, secret: str, signature: str) -> bool:
    expected = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected, signature.replace('sha256=', ''))


def mask_document_number(doc_number: str) -> str:
    """Mask document number for safe display: 123****890"""
    if not doc_number or len(doc_number) < 6:
        return '****'
    return doc_number[:3] + '****' + doc_number[-3:]


def mask_email(email: str) -> str:
    """Mask email: te***@gmail.com"""
    if not email or '@' not in email:
        return '****'
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return '**@' + domain
    return local[:2] + '***@' + domain
