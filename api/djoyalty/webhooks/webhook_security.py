# api/djoyalty/webhooks/webhook_security.py
import hashlib
import hmac
import logging
from ..utils import generate_secure_token

logger = logging.getLogger(__name__)

def generate_secret() -> str:
    return generate_secure_token(32)

def sign_payload(payload: bytes, secret: str) -> str:
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    return 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()

def verify_signature(payload: bytes, signature: str, secret: str = None) -> bool:
    if not secret:
        return False
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)
