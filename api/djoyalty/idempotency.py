# api/djoyalty/idempotency.py
"""
Djoyalty Idempotency -- Prevent duplicate operations via idempotency keys।
Especially important for: earn points, cashout, offer completions।
"Do not summarize or skip any logic. Provide the full code."
"""
import hashlib
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 86400  # 24 hours
IDEMPOTENCY_PREFIX = 'djoyalty:idempotency:'


class IdempotencyGuard:
    """
    Guard against duplicate operations using idempotency keys।
    Uses Redis (Django cache) for distributed deduplication।

    Usage:
        guard = IdempotencyGuard('earn_points', customer_id=1, txn_id=123)
        if guard.already_processed():
            return guard.get_cached_result()
        result = do_earn_points(...)
        guard.mark_processed(result)
        return result
    """

    def __init__(self, operation: str, **key_parts):
        self.operation = operation
        key_data = ':'.join(f'{k}={v}' for k, v in sorted(key_parts.items()))
        raw_key = f'{operation}:{key_data}'
        self.key = IDEMPOTENCY_PREFIX + hashlib.md5(raw_key.encode()).hexdigest()

    def already_processed(self) -> bool:
        return cache.get(self.key) is not None

    def get_cached_result(self) -> dict:
        import json
        val = cache.get(self.key)
        if val:
            try:
                return json.loads(val) if isinstance(val, str) else val
            except Exception:
                return {}
        return {}

    def mark_processed(self, result: dict, ttl: int = IDEMPOTENCY_TTL):
        import json
        try:
            cache.set(self.key, json.dumps(result, default=str), timeout=ttl)
        except Exception as e:
            logger.debug('IdempotencyGuard.mark_processed error: %s', e)

    def clear(self):
        cache.delete(self.key)

    @staticmethod
    def make_key(operation: str, **key_parts) -> str:
        key_data = ':'.join(f'{k}={v}' for k, v in sorted(key_parts.items()))
        raw_key = f'{operation}:{key_data}'
        return IDEMPOTENCY_PREFIX + hashlib.md5(raw_key.encode()).hexdigest()

    @staticmethod
    def is_duplicate(operation: str, **key_parts) -> bool:
        key = IdempotencyGuard.make_key(operation, **key_parts)
        return cache.get(key) is not None


def idempotent(operation: str, key_fields: list = None):
    """
    Decorator: make a function idempotent based on specified kwargs fields।
    Usage:
        @idempotent('earn_points', key_fields=['customer_id', 'txn_id'])
        def earn_points(customer_id, txn_id, amount):
            ...
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_fields:
                key_parts = {k: kwargs.get(k, '') for k in key_fields}
            else:
                key_parts = {'hash': str(hash(str(args) + str(sorted(kwargs.items()))))}

            guard = IdempotencyGuard(operation, **key_parts)
            if guard.already_processed():
                logger.debug('idempotent: duplicate %s call, returning cached result', operation)
                return guard.get_cached_result()

            result = func(*args, **kwargs)
            if isinstance(result, dict):
                guard.mark_processed(result)
            return result

        return wrapper
    return decorator
