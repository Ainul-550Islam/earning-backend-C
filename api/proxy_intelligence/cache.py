"""
Proxy Intelligence Cache Layer
================================
Centralized cache key management and helpers for the proxy intelligence module.
"""
from django.core.cache import cache
from .constants import (
    IP_INTELLIGENCE_CACHE_TTL, BLACKLIST_CACHE_TTL,
    THREAT_FEED_CACHE_TTL, GEO_CACHE_TTL
)


class PICache:
    """
    Centralized cache management for Proxy Intelligence.
    Provides typed methods for common cache operations.
    """
    PREFIX = "pi"

    @classmethod
    def _key(cls, *parts) -> str:
        return f"{cls.PREFIX}:" + ":".join(str(p) for p in parts)

    # ---- IP Intelligence ----
    @classmethod
    def get_intelligence(cls, ip_address: str):
        return cache.get(cls._key('intel', ip_address))

    @classmethod
    def set_intelligence(cls, ip_address: str, data: dict):
        cache.set(cls._key('intel', ip_address), data, IP_INTELLIGENCE_CACHE_TTL)

    # ---- Blacklist ----
    @classmethod
    def is_blacklisted(cls, ip_address: str):
        return cache.get(cls._key('blacklist', ip_address))

    @classmethod
    def set_blacklist(cls, ip_address: str, value: bool):
        cache.set(cls._key('blacklist', ip_address), value, BLACKLIST_CACHE_TTL)

    @classmethod
    def invalidate_blacklist(cls, ip_address: str):
        cache.delete(cls._key('blacklist', ip_address))

    # ---- Whitelist ----
    @classmethod
    def is_whitelisted(cls, ip_address: str):
        return cache.get(cls._key('whitelist', ip_address))

    @classmethod
    def set_whitelist(cls, ip_address: str, value: bool):
        cache.set(cls._key('whitelist', ip_address), value, BLACKLIST_CACHE_TTL)

    @classmethod
    def invalidate_whitelist(cls, ip_address: str):
        cache.delete(cls._key('whitelist', ip_address))

    # ---- Geo cache ----
    @classmethod
    def get_geo(cls, ip_address: str):
        return cache.get(cls._key('geo', ip_address))

    @classmethod
    def set_geo(cls, ip_address: str, data: dict):
        cache.set(cls._key('geo', ip_address), data, GEO_CACHE_TTL)

    # ---- Threat feed ----
    @classmethod
    def get_threat(cls, ip_address: str, feed_name: str):
        return cache.get(cls._key('threat', feed_name, ip_address))

    @classmethod
    def set_threat(cls, ip_address: str, feed_name: str, data: dict):
        cache.set(cls._key('threat', feed_name, ip_address), data, THREAT_FEED_CACHE_TTL)

    # ---- Bulk invalidation ----
    @classmethod
    def invalidate_all_for_ip(cls, ip_address: str):
        """Clear all cached data for a specific IP."""
        keys = [
            cls._key('intel', ip_address),
            cls._key('blacklist', ip_address),
            cls._key('whitelist', ip_address),
            cls._key('geo', ip_address),
            cls._key('vpn_detect', ip_address),
            cls._key('proxy_detect', ip_address),
            cls._key('tor_check', ip_address),
            cls._key('dc_detect', ip_address),
            cls._key('asn', ip_address),
        ]
        cache.delete_many(keys)
