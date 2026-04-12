# =============================================================================
# api/promotions/security_vault/request_signer.py
# HMAC-SHA256 API Request Signing
# প্রতিটি API request এ digital signature যোগ করে — replay attack রোধ করে
# =============================================================================

import hashlib
import hmac
import json
import logging
import time
from functools import wraps
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

logger = logging.getLogger('security_vault.request_signer')


# =============================================================================
# ── CONFIG ────────────────────────────────────────────────────────────────────
# =============================================================================

# settings.py তে এগুলো define করুন:
# HMAC_SECRET_KEY   = env('HMAC_SECRET_KEY')         # 64+ char random string
# HMAC_TIMESTAMP_TOLERANCE_SECONDS = 300             # ৫ মিনিটের বেশি পুরনো request reject
# HMAC_NONCE_TTL_SECONDS           = 600             # nonce cache এ কতক্ষণ থাকবে

HMAC_ALGORITHM              = 'sha256'
HEADER_SIGNATURE            = 'X-Signature'
HEADER_TIMESTAMP            = 'X-Timestamp'
HEADER_NONCE                = 'X-Nonce'
CACHE_PREFIX_NONCE          = 'hmac:nonce:{}'
DEFAULT_TOLERANCE_SECONDS   = getattr(settings, 'HMAC_TIMESTAMP_TOLERANCE_SECONDS', 300)
DEFAULT_NONCE_TTL           = getattr(settings, 'HMAC_NONCE_TTL_SECONDS', 600)


# =============================================================================
# ── SIGNATURE GENERATION ──────────────────────────────────────────────────────
# =============================================================================

class RequestSigner:
    """
    HMAC-SHA256 দিয়ে API request sign ও verify করে।

    Signature এর উপাদান:
        METHOD + PATH + TIMESTAMP + NONCE + BODY_HASH

    Example (client side):
        signer = RequestSigner(secret_key='your-secret')
        headers = signer.sign_request('POST', '/api/promotions/submissions/', body=payload)
        # headers['X-Signature'], headers['X-Timestamp'], headers['X-Nonce']
    """

    def __init__(self, secret_key: str = None):
        self._secret = (
            secret_key or
            getattr(settings, 'HMAC_SECRET_KEY', None) or
            'INSECURE-DEFAULT-KEY-CHANGE-IN-PRODUCTION'
        )
        if self._secret == 'INSECURE-DEFAULT-KEY-CHANGE-IN-PRODUCTION':
            logger.critical('HMAC_SECRET_KEY is not set! Using insecure default.')

    # ── Public Methods ────────────────────────────────────────────────────────

    def sign_request(
        self,
        method: str,
        path: str,
        body: dict | str | bytes = None,
        timestamp: int = None,
        nonce: str = None,
    ) -> dict:
        """
        Request এর জন্য signature headers তৈরি করে।

        Returns:
            dict: {X-Signature, X-Timestamp, X-Nonce}
        """
        ts    = timestamp or int(time.time())
        nc    = nonce or self._generate_nonce()
        sig   = self._build_signature(method, path, ts, nc, body)

        return {
            HEADER_SIGNATURE: sig,
            HEADER_TIMESTAMP: str(ts),
            HEADER_NONCE:     nc,
        }

    def verify_request(
        self,
        method: str,
        path: str,
        signature: str,
        timestamp: str | int,
        nonce: str,
        body: dict | str | bytes = None,
    ) -> bool:
        """
        Request এর signature verify করে।

        Raises:
            AuthenticationFailed: Signature invalid বা missing হলে
            PermissionDenied: Replay attack detected হলে
        """
        # ── ১. সব header আছে কিনা check ──────────────────────────────────
        if not all([signature, timestamp, nonce]):
            raise AuthenticationFailed(_('Request signature headers missing.'))

        # ── ২. Timestamp tolerance check ─────────────────────────────────
        try:
            ts_int = int(timestamp)
        except (ValueError, TypeError):
            raise AuthenticationFailed(_('Invalid timestamp format.'))

        now  = int(time.time())
        diff = abs(now - ts_int)
        if diff > DEFAULT_TOLERANCE_SECONDS:
            logger.warning(
                f'Expired request signature: timestamp={ts_int}, now={now}, '
                f'diff={diff}s (max {DEFAULT_TOLERANCE_SECONDS}s)'
            )
            raise AuthenticationFailed(
                _(f'Request expired. Timestamp drift: {diff}s (max {DEFAULT_TOLERANCE_SECONDS}s).')
            )

        # ── ৩. Nonce replay check (একই nonce দুইবার নয়) ─────────────────
        cache_key = CACHE_PREFIX_NONCE.format(nonce)
        if cache.get(cache_key):
            logger.warning(f'Replay attack detected: nonce={nonce}')
            raise PermissionDenied(_('Replay attack detected. Request already processed.'))

        # ── ৪. Signature compare ──────────────────────────────────────────
        expected_sig = self._build_signature(method, path, ts_int, nonce, body)
        if not hmac.compare_digest(expected_sig, signature):
            logger.warning(
                f'Invalid HMAC signature: method={method}, path={path}, '
                f'expected={expected_sig[:8]}..., got={signature[:8]}...'
            )
            raise AuthenticationFailed(_('Invalid request signature.'))

        # ── ৫. Nonce consume (cache এ mark করো) ──────────────────────────
        cache.set(cache_key, True, timeout=DEFAULT_NONCE_TTL)
        logger.debug(f'Request signature verified: method={method}, path={path}')
        return True

    # ── Private Methods ───────────────────────────────────────────────────────

    def _build_signature(
        self,
        method: str,
        path: str,
        timestamp: int,
        nonce: str,
        body: dict | str | bytes = None,
    ) -> str:
        """Canonical string তৈরি করে HMAC sign করে।"""
        body_hash = self._hash_body(body)

        # Canonical string: METHOD|PATH|TIMESTAMP|NONCE|BODY_HASH
        canonical = '|'.join([
            method.upper(),
            path.strip().lower(),
            str(timestamp),
            nonce,
            body_hash,
        ])

        signature = hmac.new(
            key=self._secret.encode('utf-8'),
            msg=canonical.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return signature

    @staticmethod
    def _hash_body(body: dict | str | bytes = None) -> str:
        """Request body এর SHA-256 hash বের করে।"""
        if body is None:
            raw = b''
        elif isinstance(body, dict):
            raw = json.dumps(body, sort_keys=True, separators=(',', ':')).encode('utf-8')
        elif isinstance(body, str):
            raw = body.encode('utf-8')
        elif isinstance(body, bytes):
            raw = body
        else:
            raw = str(body).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _generate_nonce() -> str:
        """Cryptographically secure random nonce তৈরি করে।"""
        import secrets
        return secrets.token_hex(16)  # 32 char hex string


# =============================================================================
# ── DRF MIDDLEWARE / DECORATOR ────────────────────────────────────────────────
# =============================================================================

# Singleton instance (settings থেকে key নেয়)
_signer = RequestSigner()


class HMACSignatureMiddleware:
    """
    Django middleware — প্রতিটি POST/PUT/PATCH request এ HMAC verify করে।
    settings.py তে HMAC_PROTECTED_PATHS list দিলে শুধু সেই path গুলোতে apply হবে।
    """

    # এই path গুলোতে HMAC check করা হবে না
    EXEMPT_PATHS = [
        '/admin/',
        '/api/auth/',
        '/api/token/',
        '/health/',
    ]
    # এই methods এ শুধু check হবে
    PROTECTED_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_verify(request):
            try:
                _signer.verify_request(
                    method    = request.method,
                    path      = request.path,
                    signature = request.META.get(f'HTTP_{HEADER_SIGNATURE.upper().replace("-","_")}', ''),
                    timestamp = request.META.get(f'HTTP_{HEADER_TIMESTAMP.upper().replace("-","_")}', ''),
                    nonce     = request.META.get(f'HTTP_{HEADER_NONCE.upper().replace("-","_")}', ''),
                    body      = request.body,
                )
            except (AuthenticationFailed, PermissionDenied) as e:
                from django.http import JsonResponse
                return JsonResponse({'error': str(e.detail), 'code': e.default_code}, status=e.status_code)

        return self.get_response(request)

    def _should_verify(self, request) -> bool:
        if request.method not in self.PROTECTED_METHODS:
            return False
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return False
        # settings এ explicitly enable করতে হবে
        return getattr(settings, 'HMAC_SIGNATURE_REQUIRED', False)


def require_signed_request(view_func):
    """
    View decorator — নির্দিষ্ট endpoint এ HMAC signature enforce করে।

    Usage:
        @require_signed_request
        def my_sensitive_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        _signer.verify_request(
            method    = request.method,
            path      = request.path,
            signature = request.META.get(f'HTTP_{HEADER_SIGNATURE.upper().replace("-","_")}', ''),
            timestamp = request.META.get(f'HTTP_{HEADER_TIMESTAMP.upper().replace("-","_")}', ''),
            nonce     = request.META.get(f'HTTP_{HEADER_NONCE.upper().replace("-","_")}', ''),
            body      = request.body,
        )
        return view_func(request, *args, **kwargs)
    return wrapper


# =============================================================================
# ── WEBHOOK SIGNING ───────────────────────────────────────────────────────────
# =============================================================================

class WebhookSigner:
    """
    Outgoing webhook request sign করার utility।
    Third-party service (যেমন payment gateway) কে পাঠানো webhook verify করতে ব্যবহার করুন।
    """

    def __init__(self, webhook_secret: str):
        self._secret = webhook_secret

    def sign_payload(self, payload: dict) -> str:
        """Webhook payload sign করে।"""
        body = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hmac.new(
            key=self._secret.encode('utf-8'),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

    def verify_webhook(self, payload: dict, received_signature: str) -> bool:
        """Incoming webhook এর signature verify করে।"""
        expected = self.sign_payload(payload)
        return hmac.compare_digest(expected, received_signature)
