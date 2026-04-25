# FILE 90 of 257 — cache/GatewayTokenCache.py
# Redis-backed gateway token caching (bKash, Nagad, ShurjoPay auth tokens)

from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

TOKEN_TTL = {
    'bkash':     3500,   # bKash token valid 1 hour — cache 58 min
    'nagad':     3500,
    'shurjopay': 3500,
    'paypal':    30000,  # PayPal token valid ~9h
    'upay':      3500,
}

class GatewayTokenCache:
    """Cache gateway OAuth/session tokens to avoid re-authenticating every request."""

    @staticmethod
    def get(gateway: str, key: str = 'default') -> str | None:
        cache_key = f'gw_token:{gateway}:{key}'
        return cache.get(cache_key)

    @staticmethod
    def set(gateway: str, token: str, key: str = 'default'):
        ttl       = TOKEN_TTL.get(gateway, 3000)
        cache_key = f'gw_token:{gateway}:{key}'
        cache.set(cache_key, token, ttl)
        logger.debug(f'GatewayTokenCache: cached token for {gateway} (ttl={ttl}s)')

    @staticmethod
    def delete(gateway: str, key: str = 'default'):
        cache.delete(f'gw_token:{gateway}:{key}')

    @staticmethod
    def get_or_fetch(gateway: str, fetch_fn, key: str = 'default') -> str:
        """
        Get token from cache or call fetch_fn() to obtain a fresh one.
        Usage:
            token = GatewayTokenCache.get_or_fetch('bkash', self._get_token)
        """
        token = GatewayTokenCache.get(gateway, key)
        if token:
            return token
        token = fetch_fn()
        GatewayTokenCache.set(gateway, token, key)
        return token
