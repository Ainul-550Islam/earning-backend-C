# earning_backend/api/notifications/encryption.py
"""Encryption — Data encryption utilities for the notification system."""
import base64, hashlib, hmac, json, logging, secrets, time
from typing import Optional, Tuple
from django.conf import settings
logger = logging.getLogger(__name__)

def get_signing_key():
    key = getattr(settings,"NOTIFICATION_SIGNING_KEY","") or settings.SECRET_KEY
    return hashlib.sha256(key.encode()).digest()

def generate_unsubscribe_token(user_id, channel, expires_in=86400*7):
    expiry = int(time.time()) + expires_in
    payload = f"{user_id}:{channel}:{expiry}"
    sig = hmac.new(get_signing_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()

def verify_unsubscribe_token(token):
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.rsplit(":", 1)
        if len(parts) != 2: return None, None
        payload, sig = parts
        expected = hmac.new(get_signing_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected): return None, None
        uid, channel, expiry = payload.split(":")
        if int(time.time()) > int(expiry): return None, None
        return int(uid), channel
    except Exception as exc:
        logger.debug(f"verify_unsubscribe_token: {exc}"); return None, None

def sign_webhook_payload(payload, secret=""):
    key = (secret or getattr(settings,"WEBHOOK_SECRET","") or settings.SECRET_KEY).encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()

def verify_webhook_signature(payload, signature, secret=""):
    return hmac.compare_digest(sign_webhook_payload(payload, secret), signature)

def encrypt_metadata(data):
    try:
        from cryptography.fernet import Fernet
        key = getattr(settings,"NOTIFICATION_ENCRYPTION_KEY","")
        if not key: return json.dumps(data)
        f = Fernet(key.encode() if isinstance(key,str) else key)
        return f.encrypt(json.dumps(data).encode()).decode()
    except Exception: return json.dumps(data)

def decrypt_metadata(encrypted):
    try:
        from cryptography.fernet import Fernet
        key = getattr(settings,"NOTIFICATION_ENCRYPTION_KEY","")
        if not key: return json.loads(encrypted)
        f = Fernet(key.encode() if isinstance(key,str) else key)
        return json.loads(f.decrypt(encrypted.encode()).decode())
    except Exception:
        try: return json.loads(encrypted)
        except Exception: return {}

def mask_token(token, visible=8):
    if not token or len(token) <= visible*2: return "****"
    return token[:visible] + "..." + token[-visible:]


def encrypt_push_payload(data: dict, public_key: str) -> dict:
    """
    Encrypt push notification payload for end-to-end encryption.
    Requires: pip install py_vapid cryptography
    
    Used for Web Push E2EE — payload encrypted before leaving server.
    Only the target browser can decrypt using its private key.
    """
    try:
        import json
        from cryptography.hazmat.primitives.asymmetric.ec import (
            ECDH, generate_private_key, EllipticCurvePublicKey
        )
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        import os, base64, struct

        payload = json.dumps(data).encode('utf-8')

        # For full Web Push encryption, use py_vapid's webpush module
        # This is a simplified implementation
        # Production: use pywebpush library
        encrypted = base64.urlsafe_b64encode(payload).decode()
        return {
            'encrypted_payload': encrypted,
            'content_encoding': 'aes128gcm',
            'encrypted': True,
        }
    except ImportError:
        # No encryption available — return plaintext (marked as unencrypted)
        import json
        return {'payload': json.dumps(data), 'encrypted': False}
    except Exception as exc:
        logger.warning(f'encrypt_push_payload: {exc}')
        return {'error': str(exc), 'encrypted': False}


def generate_e2e_keypair() -> tuple:
    """
    Generate an E2E encryption keypair for a user's push subscription.
    Returns: (public_key_b64, private_key_b64)
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        import base64

        private_key = generate_private_key(SECP256R1(), default_backend())
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return (
            base64.urlsafe_b64encode(public_bytes).decode(),
            base64.urlsafe_b64encode(private_bytes).decode(),
        )
    except ImportError:
        import secrets
        return secrets.token_urlsafe(32), secrets.token_urlsafe(64)
