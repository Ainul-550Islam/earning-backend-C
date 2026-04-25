# api/wallet/decorators.py
import functools
import logging
from django.core.cache import cache

logger = logging.getLogger("wallet.decorators")


def wallet_lock(timeout: int = 30):
    """
    Redis-based distributed lock per wallet.
    Prevents concurrent mutations on the same wallet.
    Usage:
        @wallet_lock(timeout=30)
        def my_view(request, wallet_id):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wallet_id = kwargs.get("wallet_id") or (args[1].id if len(args) > 1 else None)
            key = f"wallet_dist_lock_{wallet_id}"
            acquired = cache.add(key, "1", timeout)
            if not acquired:
                from .exceptions import WalletLockedError
                raise WalletLockedError("Wallet operation in progress. Please retry.")
            try:
                return func(*args, **kwargs)
            finally:
                try:
                    cache.delete(key)
                except Exception:
                    pass
        return wrapper
    return decorator


def idempotent(key_func=None, ttl: int = 86400):
    """
    Idempotency decorator — prevents double execution.
    key_func: callable that takes (request,) and returns unique key string.
    If key_func is None, uses HTTP_IDEMPOTENCY_KEY header.
    Usage:
        @idempotent()
        def my_view(request):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if key_func:
                idem_key = key_func(request)
            else:
                idem_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "")

            if idem_key:
                cache_key = f"idem_{idem_key}"
                cached = cache.get(cache_key)
                if cached is not None:
                    logger.info(f"Idempotent replay: key={idem_key}")
                    from rest_framework.response import Response
                    return Response(cached)
            result = func(self, request, *args, **kwargs)
            if idem_key and hasattr(result, "data"):
                cache.set(cache_key, result.data, ttl)
            return result
        return wrapper
    return decorator


def require_kyc(min_level: int = 1):
    """
    Require minimum KYC level for a viewset action.
    Usage:
        @require_kyc(min_level=2)
        def approve(self, request, pk=None):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                from .services.core.WalletService import WalletService
                level = WalletService._get_kyc_level(request.user)
                if level < min_level:
                    from rest_framework.response import Response
                    return Response({
                        "error": f"KYC Level {min_level}+ required. Your level: {level}",
                        "upgrade_url": "/api/wallet/kyc/",
                    }, status=403)
            except Exception:
                pass
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def cache_response(timeout: int = 60, key_prefix: str = "wallet_view"):
    """Cache view response for N seconds."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            cache_key = f"{key_prefix}_{request.user.id}_{request.get_full_path()}"
            cached = cache.get(cache_key)
            if cached is not None:
                from rest_framework.response import Response
                return Response(cached)
            result = func(self, request, *args, **kwargs)
            if hasattr(result, "data") and result.status_code == 200:
                cache.set(cache_key, result.data, timeout)
            return result
        return wrapper
    return decorator
