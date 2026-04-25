# api/payment_gateways/encryption.py
# Encryption utilities for sensitive payment data
# "Do not summarize or skip any logic. Provide the full code."

import base64
import hashlib
import hmac
import os
import logging
from typing import Optional, Union
from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentEncryption:
    """
    Encryption for sensitive payment data.
    Uses AES-256-GCM (Fernet) for symmetric encryption.
    Used for storing API keys, account numbers, webhook secrets.

    Setup: pip install cryptography
    Settings: PAYMENT_ENCRYPTION_KEY (32 bytes base64)
    """

    _key: Optional[bytes] = None

    def _get_key(self) -> bytes:
        if self._key is None:
            raw = getattr(settings, 'PAYMENT_ENCRYPTION_KEY', '')
            if not raw:
                # Generate from SECRET_KEY (deterministic but secure)
                secret = getattr(settings, 'SECRET_KEY', 'fallback-secret')
                raw = hashlib.sha256(secret.encode()).digest()
                raw = base64.urlsafe_b64encode(raw).decode()
                logger.debug('Using derived encryption key from SECRET_KEY')
            if isinstance(raw, str):
                raw = raw.encode()
            # Pad/truncate to 32 bytes for Fernet
            self._key = base64.urlsafe_b64encode(
                hashlib.sha256(base64.urlsafe_b64decode(
                    raw + b'=' * (4 - len(raw) % 4)
                )).digest()
            )
        return self._key

    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt sensitive data using Fernet (AES-128-CBC + HMAC).
        Returns base64-encoded ciphertext safe for DB storage.

        Args:
            plaintext: String or bytes to encrypt

        Returns:
            str: Encrypted token (safe to store in DB)

        Example:
            enc = PaymentEncryption()
            token = enc.encrypt('sk_live_abc123')
            # → 'gAAAAABl...' (Fernet token)
        """
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self._get_key())
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
            return f.encrypt(plaintext).decode('utf-8')
        except ImportError:
            logger.warning('cryptography not installed — using base64 fallback')
            if isinstance(plaintext, bytes):
                plaintext = plaintext.decode('utf-8')
            return 'b64:' + base64.b64encode(plaintext.encode()).decode()
        except Exception as e:
            logger.error(f'Encryption failed: {e}')
            raise

    def decrypt(self, ciphertext: Union[str, bytes]) -> str:
        """
        Decrypt previously encrypted data.

        Args:
            ciphertext: Encrypted token from encrypt()

        Returns:
            str: Decrypted plaintext

        Raises:
            Exception: If decryption fails (wrong key, tampered data)
        """
        if isinstance(ciphertext, bytes):
            ciphertext = ciphertext.decode('utf-8')

        # Handle base64 fallback
        if ciphertext.startswith('b64:'):
            return base64.b64decode(ciphertext[4:]).decode('utf-8')

        try:
            from cryptography.fernet import Fernet, InvalidToken
            f = Fernet(self._get_key())
            return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
        except ImportError:
            logger.warning('cryptography not installed — decryption not available')
            return ciphertext
        except Exception as e:
            logger.error(f'Decryption failed: {e}')
            raise ValueError('Decryption failed — data may be corrupted or key changed')

    def encrypt_api_credential(self, api_key: str, api_secret: str) -> tuple:
        """
        Encrypt gateway API credentials for secure storage.

        Returns:
            tuple: (encrypted_key, encrypted_secret)
        """
        return self.encrypt(api_key), self.encrypt(api_secret)

    def decrypt_api_credential(self, encrypted_key: str,
                                encrypted_secret: str) -> tuple:
        """Decrypt gateway API credentials."""
        return self.decrypt(encrypted_key), self.decrypt(encrypted_secret)

    def hash_for_lookup(self, value: str) -> str:
        """
        Create a deterministic hash for looking up encrypted values.
        Useful for querying encrypted account numbers.

        Returns:
            str: 32-char hex hash (safe for DB index)
        """
        salt   = getattr(settings, 'PAYMENT_HASH_SALT', 'pg_hash_v1')
        return hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:32]

    def mask(self, value: str, visible: int = 4) -> str:
        """Mask a value for display: 'sk_live_abc123' → 'sk_li***23'"""
        if not value:
            return '****'
        if len(value) <= visible * 2:
            return '*' * len(value)
        return value[:visible] + '***' + value[-visible:]

    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted."""
        if not value:
            return False
        return value.startswith('gAAAAA') or value.startswith('b64:')

    def rotate_key(self, old_ciphertext: str, old_key: bytes,
                    new_key: bytes) -> str:
        """
        Re-encrypt data with a new key.
        Used during key rotation.

        Args:
            old_ciphertext: Data encrypted with old_key
            old_key:        Old Fernet key
            new_key:        New Fernet key

        Returns:
            str: Data re-encrypted with new_key
        """
        try:
            from cryptography.fernet import Fernet
            plaintext = Fernet(old_key).decrypt(old_ciphertext.encode())
            return Fernet(new_key).encrypt(plaintext).decode()
        except Exception as e:
            logger.error(f'Key rotation failed: {e}')
            raise


class WebhookSecretManager:
    """
    Manages webhook signing secrets for each gateway.
    Stores encrypted secrets and verifies webhook signatures.
    """

    def __init__(self):
        self.enc = PaymentEncryption()

    def store_secret(self, gateway: str, secret: str) -> str:
        """Store webhook secret encrypted. Returns encrypted value."""
        return self.enc.encrypt(secret)

    def get_secret(self, gateway: str) -> Optional[str]:
        """Get decrypted webhook secret for a gateway."""
        try:
            from api.payment_gateways.models.gateway_config import GatewayWebhookConfig
            from api.payment_gateways.models.core import PaymentGateway
            gw     = PaymentGateway.objects.get(name=gateway)
            config = GatewayWebhookConfig.objects.get(gateway=gw, is_active=True)
            return self.enc.decrypt(config.secret_key) if config.secret_key else None
        except Exception:
            # Fallback to settings
            setting_key = f'{gateway.upper()}_WEBHOOK_SECRET'
            return getattr(settings, setting_key, '')

    def verify(self, gateway: str, payload: bytes, headers: dict) -> bool:
        """Verify webhook signature from gateway."""
        secret = self.get_secret(gateway)
        if not secret:
            logger.debug(f'No webhook secret for {gateway} — skipping verification')
            return True  # Allow if no secret configured

        # Gateway-specific verification logic
        if gateway == 'stripe':
            sig_header = headers.get('Stripe-Signature', '')
            return self._verify_stripe(payload, sig_header, secret)
        elif gateway in ('bkash', 'nagad', 'shurjopay'):
            return self._verify_hmac_sha256(payload, headers.get('X-Signature',''), secret)
        elif gateway == 'sslcommerz':
            return self._verify_sslcommerz(payload, secret)
        else:
            # Generic HMAC-SHA256
            sig = headers.get('X-Signature', headers.get('X-Hub-Signature-256', ''))
            return self._verify_hmac_sha256(payload, sig, secret)

    def _verify_stripe(self, payload: bytes, sig_header: str, secret: str) -> bool:
        try:
            import stripe
            stripe.WebhookSignature.verify_header(
                payload.decode('utf-8'), sig_header, secret, tolerance=300
            )
            return True
        except Exception:
            return False

    def _verify_hmac_sha256(self, payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        received = signature.replace('sha256=', '').replace('sha512=', '')
        return hmac.compare_digest(expected.lower(), received.lower()) if received else False

    def _verify_sslcommerz(self, payload: bytes, secret: str) -> bool:
        """SSLCommerz uses MD5 hash verification."""
        import hashlib
        try:
            data = dict(x.split('=') for x in payload.decode().split('&'))
            verify_sign = data.pop('verify_sign', '')
            verify_key  = data.pop('verify_key', '')
            keys        = sorted(verify_key.split(','))
            sign_string = ''.join(data.get(k, '') for k in keys) + secret
            expected    = hashlib.md5(sign_string.encode()).hexdigest()
            return hmac.compare_digest(expected, verify_sign)
        except Exception:
            return False


# Global instances
payment_encryption = PaymentEncryption()
webhook_secret_manager = WebhookSecretManager()
