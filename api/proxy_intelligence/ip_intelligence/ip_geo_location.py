"""IP Geolocation — resolves lat/lng, country, city from IP address."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class IPGeoLocation:
    """Multi-source IP geolocation with caching."""

    @classmethod
    def get_country(cls, ip_address: str) -> str:
        data = cls.lookup(ip_address)
        return data.get('country_code', '')

    @classmethod
    def lookup(cls, ip_address: str) -> dict:
        cache_key = f"pi:geo:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = cls._try_maxmind(ip_address) or cls._try_ipinfo(ip_address) or {}
        if result:
            cache.set(cache_key, result, 86400)
        return result

    @classmethod
    def _try_maxmind(cls, ip: str) -> dict:
        try:
            from ..integrations.maxmind_integration import MaxMindIntegration
            return MaxMindIntegration().lookup(ip)
        except Exception:
            return {}

    @classmethod
    def _try_ipinfo(cls, ip: str) -> dict:
        try:
            import requests
            r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            if r.status_code == 200:
                d = r.json()
                loc = d.get('loc','0,0').split(',')
                return {
                    'country_code': d.get('country',''),
                    'city': d.get('city',''),
                    'region': d.get('region',''),
                    'latitude': float(loc[0]) if len(loc)==2 else 0.0,
                    'longitude': float(loc[1]) if len(loc)==2 else 0.0,
                    'timezone': d.get('timezone',''),
                    'isp': d.get('org',''),
                    'source': 'ipinfo',
                }
        except Exception:
            return {}
