# api/offer_inventory/optimization_scale/request_deduplication.py
"""Request Deduplication — Idempotent request handling via Redis."""
import hashlib
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300   # 5 minutes


class RequestDeduplicator:
    """Prevent duplicate processing of identical API requests."""

    @staticmethod
    def make_key(method: str, path: str,
                  body: bytes = b'', user_id=None) -> str:
        """Generate a unique cache key for a request."""
        body_hash = hashlib.md5(body or b'').hexdigest()
        raw       = f'{method}:{path}:{body_hash}:{user_id}'
        return f'dedup:{hashlib.md5(raw.encode()).hexdigest()}'

    @staticmethod
    def is_duplicate(request_key: str) -> bool:
        """True if this request was already processed recently."""
        return bool(cache.get(request_key))

    @staticmethod
    def mark_processed(request_key: str, result=None, ttl: int = DEFAULT_TTL):
        """Mark a request as processed with optional result caching."""
        cache.set(request_key, result or '1', ttl)

    @staticmethod
    def get_cached_result(request_key: str):
        """Get cached result for a previously processed request."""
        val = cache.get(request_key)
        return None if val == '1' else val

    @classmethod
    def check_and_mark(cls, method: str, path: str,
                        body: bytes = b'', user_id=None,
                        ttl: int = DEFAULT_TTL) -> dict:
        """
        Combined check-and-mark operation.
        Returns {'is_duplicate': bool, 'key': str}
        """
        key = cls.make_key(method, path, body, user_id)
        if cls.is_duplicate(key):
            return {'is_duplicate': True,  'key': key}
        cls.mark_processed(key, ttl=ttl)
        return {'is_duplicate': False, 'key': key}

    @staticmethod
    def reset(request_key: str):
        """Remove deduplication lock for a key."""
        cache.delete(request_key)

    @classmethod
    def idempotent_postback(cls, transaction_id: str,
                             network_slug: str) -> bool:
        """
        Check if a postback transaction_id has already been processed.
        Used specifically for postback idempotency.
        """
        key = f'postback_idem:{network_slug}:{transaction_id}'
        if cache.get(key):
            return True   # Duplicate
        cache.set(key, '1', 86400)   # Mark as seen for 24h
        return False

    @classmethod
    def get_stats(cls) -> dict:
        """Stats on deduplication usage (approximate)."""
        return {
            'description': 'Deduplication keys stored in Redis with TTL.',
            'default_ttl': DEFAULT_TTL,
        }
