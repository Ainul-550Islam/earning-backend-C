# api/payment_gateways/utils/HashUtils.py
# Hashing, HMAC, and cryptographic utilities for payment security

import hashlib
import hmac
import secrets
import base64
from typing import Union


class HashUtils:
    """Cryptographic utilities for payment gateway security."""

    @staticmethod
    def sha256(data: Union[str, bytes], encoding: str = 'utf-8') -> str:
        """SHA-256 hash of a string or bytes."""
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha512(data: Union[str, bytes]) -> str:
        """SHA-512 hash."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha512(data).hexdigest()

    @staticmethod
    def md5(data: Union[str, bytes]) -> str:
        """MD5 hash (legacy use for SSLCommerz, etc.)."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def hmac_sha256(secret: str, message: Union[str, bytes]) -> str:
        """
        HMAC-SHA256 for webhook signature verification.
        Used by: Stripe (Stripe-Signature), bKash, Nagad, etc.
        """
        if isinstance(message, str):
            message = message.encode()
        return hmac.new(
            secret.encode(), message, hashlib.sha256
        ).hexdigest()

    @staticmethod
    def hmac_sha512(secret: str, message: Union[str, bytes]) -> str:
        """HMAC-SHA512."""
        if isinstance(message, str):
            message = message.encode()
        return hmac.new(
            secret.encode(), message, hashlib.sha512
        ).hexdigest()

    @staticmethod
    def verify_hmac(secret: str, message: Union[str, bytes], signature: str,
                    algo: str = 'sha256') -> bool:
        """
        Verify HMAC signature using constant-time comparison (prevents timing attacks).

        Args:
            secret:    The shared secret key
            message:   The message/payload that was signed
            signature: The signature to verify against
            algo:      'sha256' or 'sha512'

        Returns:
            bool: True if signature is valid
        """
        if isinstance(message, str):
            message = message.encode()
        if algo == 'sha512':
            expected = hmac.new(secret.encode(), message, hashlib.sha512).hexdigest()
        else:
            expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected.lower(), signature.lower())

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_hex(length)

    @staticmethod
    def generate_api_key(prefix: str = 'sk') -> str:
        """Generate an API key like Stripe's sk_live_... format."""
        token = secrets.token_urlsafe(32)
        return f'{prefix}_{token}'

    @staticmethod
    def hash_sensitive(value: str) -> str:
        """
        One-way hash for storing sensitive data (account numbers, etc.).
        Use for: storing masked references that can be looked up but not reversed.
        """
        salt = 'pg_sensitive_v1'
        return hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:32]

    @staticmethod
    def mask_account(account_number: str) -> str:
        """
        Mask an account number for display.
        01712345678 → ****45678
        4111111111111111 → ************1111
        """
        if not account_number:
            return ''
        visible = min(4, len(account_number) // 4)
        return '*' * (len(account_number) - visible) + account_number[-visible:]

    @staticmethod
    def encode_base64(data: Union[str, bytes]) -> str:
        """Base64 encode."""
        if isinstance(data, str):
            data = data.encode()
        return base64.b64encode(data).decode()

    @staticmethod
    def decode_base64(data: str) -> bytes:
        """Base64 decode."""
        return base64.b64decode(data.encode())
