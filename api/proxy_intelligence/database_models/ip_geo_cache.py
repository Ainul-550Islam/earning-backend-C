"""IP Geo Cache — multi-level caching for geolocation data."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

GEO_CACHE_TTL = 86400   # 24 hours
MISS_CACHE_TTL = 3600   # 1 hour for known misses (avoids repeated lookups)


class IPGeoCache:
    """
    Two-level geolocation cache:
      L1: Redis (fast, in-memory)
      L2: Django ORM IPIntelligence model (slower, persistent)
    """

    @staticmethod
    def get(ip_address: str) -> dict:
        """Get cached geo data. Returns empty dict on miss."""
        return cache.get(f"pi:geo_cache:{ip_address}", {})

    @staticmethod
    def set(ip_address: str, data: dict):
        """Cache geo data for 24 hours."""
        if data:
            cache.set(f"pi:geo_cache:{ip_address}", data, GEO_CACHE_TTL)

    @staticmethod
    def invalidate(ip_address: str):
        """Remove geo cache for an IP."""
        cache.delete(f"pi:geo_cache:{ip_address}")

    @classmethod
    def get_or_fetch(cls, ip_address: str) -> dict:
        """
        Get geo data with auto-fetch.
        L1: Redis → L2: IPIntelligence model → L3: MaxMind API
        """
        # L1: Redis
        cached = cls.get(ip_address)
        if cached:
            return cached

        # L2: IPIntelligence model
        try:
            from ..models import IPIntelligence
            intel = IPIntelligence.objects.filter(
                ip_address=ip_address
            ).values(
                'country_code', 'country_name', 'city', 'region',
                'latitude', 'longitude', 'timezone', 'isp', 'asn',
            ).first()
            if intel and intel.get('country_code'):
                cls.set(ip_address, intel)
                return intel
        except Exception as e:
            logger.debug(f"IPGeoCache L2 lookup failed: {e}")

        # L3: MaxMind API
        try:
            from ..integrations.maxmind_integration import MaxMindIntegration
            data = MaxMindIntegration().lookup(ip_address)
            if data and data.get('country_code'):
                cls.set(ip_address, data)
                return data
        except Exception as e:
            logger.debug(f"IPGeoCache L3 lookup failed: {e}")

        # Mark as known miss to avoid repeated lookups
        cache.set(f"pi:geo_miss:{ip_address}", True, MISS_CACHE_TTL)
        return {}

    @staticmethod
    def warm_cache(ip_list: list) -> dict:
        """Pre-warm the geo cache for a list of IPs."""
        results = {}
        for ip in ip_list:
            results[ip] = IPGeoCache.get_or_fetch(ip)
        return results

    @staticmethod
    def is_cached(ip_address: str) -> bool:
        """True if geo data is already in cache."""
        return bool(cache.get(f"pi:geo_cache:{ip_address}"))

    @staticmethod
    def is_known_miss(ip_address: str) -> bool:
        """True if this IP was previously looked up and had no geo data."""
        return bool(cache.get(f"pi:geo_miss:{ip_address}"))
