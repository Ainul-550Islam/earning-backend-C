# api/offer_inventory/api_connectivity/rest_api_v2.py
"""
REST API v2 — Enhanced API connectivity layer.
Versioned endpoints, rate limiting, API key management,
response formatting, and external API integration.
"""
import logging
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# API version
API_VERSION      = 'v2'
API_KEY_PREFIX   = 'oi_'
API_KEY_LENGTH   = 40
RATE_LIMIT_WINDOW = 60    # seconds
RATE_LIMIT_MAX    = 1000  # requests per window


class APIKeyManager:
    """
    Manage API keys for external integrations.
    Keys are hashed in DB — plaintext shown only once at creation.
    """

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key."""
        raw = secrets.token_urlsafe(API_KEY_LENGTH)
        return f'{API_KEY_PREFIX}{raw}'

    @staticmethod
    def hash_key(key: str) -> str:
        """SHA-256 hash of API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create(cls, service: str, tenant=None, expires_days: int = None) -> dict:
        """
        Create and store a new API key.
        Returns plaintext key — shown only once.
        """
        from api.offer_inventory.models import APIKeyManager as APIKeyModel
        from django.utils import timezone

        key       = cls.generate_key()
        key_hash  = cls.hash_key(key)
        expires   = timezone.now() + timedelta(days=expires_days) if expires_days else None

        APIKeyModel.objects.create(
            tenant    =tenant,
            service   =service,
            key_name  =f'{service}_key',
            key_value =key_hash,
            expires_at=expires,
        )
        logger.info(f'API key created for service: {service}')
        return {
            'key'       : key,        # Only shown once
            'service'   : service,
            'expires_at': expires.isoformat() if expires else None,
            'warning'   : 'Store this key safely — it will not be shown again.',
        }

    @classmethod
    def validate(cls, key: str, tenant=None) -> bool:
        """Validate an API key from request header."""
        if not key or not key.startswith(API_KEY_PREFIX):
            return False

        cache_key = f'api_key_valid:{cls.hash_key(key)}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        from api.offer_inventory.models import APIKeyManager as APIKeyModel
        from django.db.models import Q

        now = timezone.now()
        valid = APIKeyModel.objects.filter(
            key_value=cls.hash_key(key),
            is_active=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        if tenant:
            valid = valid.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

        result = valid.exists()
        cache.set(cache_key, result, 300)
        return result

    @classmethod
    def rotate(cls, service: str, tenant=None) -> dict:
        """Rotate API key for a service."""
        from api.offer_inventory.models import APIKeyManager as APIKeyModel
        APIKeyModel.objects.filter(service=service, tenant=tenant).update(is_active=False)
        return cls.create(service, tenant)

    @classmethod
    def revoke(cls, service: str, tenant=None) -> int:
        """Revoke all API keys for a service."""
        from api.offer_inventory.models import APIKeyManager as APIKeyModel
        count = APIKeyModel.objects.filter(service=service, tenant=tenant).update(is_active=False)
        logger.warning(f'API keys revoked: {count} keys for service={service}')
        return count


class APIRateLimiter:
    """
    Per-key and per-IP rate limiting.
    Uses Redis sliding window counter.
    """

    @staticmethod
    def check(identifier: str, limit: int = RATE_LIMIT_MAX,
               window: int = RATE_LIMIT_WINDOW) -> dict:
        """
        Check rate limit for an identifier (API key or IP).
        Returns {'allowed': bool, 'remaining': int, 'reset_in': int}
        """
        key   = f'rate:{identifier}'
        count = cache.get(key, 0)
        ttl   = cache.ttl(key) if hasattr(cache, 'ttl') else window

        if count >= limit:
            return {
                'allowed'  : False,
                'remaining': 0,
                'reset_in' : ttl or window,
                'count'    : count,
            }

        cache.set(key, count + 1, window)
        return {
            'allowed'  : True,
            'remaining': limit - count - 1,
            'reset_in' : window,
            'count'    : count + 1,
        }

    @staticmethod
    def reset(identifier: str):
        """Reset rate limit counter."""
        cache.delete(f'rate:{identifier}')


class APIResponseFormatter:
    """
    Standardized API response formatting for v2.
    Consistent envelope structure.
    """

    @staticmethod
    def success(data=None, message: str = '', meta: dict = None,
                 status_code: int = 200) -> Response:
        return Response({
            'api_version': API_VERSION,
            'success'    : True,
            'message'    : message,
            'data'       : data,
            'meta'       : meta or {},
            'timestamp'  : timezone.now().isoformat(),
        }, status=status_code)

    @staticmethod
    def error(message: str, code: str = 'error',
               errors: dict = None, status_code: int = 400) -> Response:
        return Response({
            'api_version': API_VERSION,
            'success'    : False,
            'message'    : message,
            'code'       : code,
            'errors'     : errors or {},
            'timestamp'  : timezone.now().isoformat(),
        }, status=status_code)

    @staticmethod
    def paginated(data: list, page: int, page_size: int,
                   total: int, message: str = '') -> Response:
        return Response({
            'api_version': API_VERSION,
            'success'    : True,
            'message'    : message,
            'data'       : data,
            'pagination' : {
                'page'      : page,
                'page_size' : page_size,
                'total'     : total,
                'pages'     : (total + page_size - 1) // page_size,
                'has_next'  : (page * page_size) < total,
                'has_prev'  : page > 1,
            },
            'timestamp': timezone.now().isoformat(),
        })


class ExternalAPIClient:
    """
    Generic resilient client for external API calls.
    Timeout, retry, circuit breaker integration.
    """

    def __init__(self, base_url: str, api_key: str = '',
                 timeout: int = 10, max_retries: int = 3):
        self.base_url   = base_url.rstrip('/')
        self.api_key    = api_key
        self.timeout    = timeout
        self.max_retries = max_retries

    def get(self, endpoint: str, params: dict = None) -> dict:
        """GET request with retry."""
        return self._request('GET', endpoint, params=params)

    def post(self, endpoint: str, data: dict = None) -> dict:
        """POST request with retry."""
        return self._request('POST', endpoint, json=data)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        import requests
        import time

        url     = f'{self.base_url}/{endpoint.lstrip("/")}'
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['X-API-Key']     = self.api_key

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.request(
                    method, url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs
                )
                resp.raise_for_status()
                return {'success': True, 'data': resp.json(), 'status': resp.status_code}
            except requests.exceptions.Timeout:
                last_error = 'timeout'
                logger.warning(f'API timeout: {url} (attempt {attempt+1})')
            except requests.exceptions.HTTPError as e:
                last_error = str(e)
                if resp.status_code < 500:
                    break  # Don't retry 4xx errors
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        return {'success': False, 'error': last_error, 'data': None}
