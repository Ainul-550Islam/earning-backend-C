"""DNS Leak Detector — detects mismatched DNS and IP geolocation."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class DNSLeakDetector:
    """
    Detects DNS leaks: user's IP country differs from DNS resolver country.
    This is a server-side approximation — full detection requires client JS.
    """
    def __init__(self, ip_address: str, ip_country: str = '',
                 reported_dns_servers: list = None):
        self.ip_address = ip_address
        self.ip_country = ip_country.upper()
        self.dns_servers = reported_dns_servers or []

    def detect(self) -> dict:
        cache_key = f"pi:dns_leak:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        leak_detected = False
        mismatched_dns = []

        for dns_ip in self.dns_servers:
            dns_country = self._get_country(dns_ip)
            if dns_country and dns_country != self.ip_country:
                leak_detected = True
                mismatched_dns.append({
                    'dns_ip': dns_ip,
                    'dns_country': dns_country,
                    'ip_country': self.ip_country,
                })

        result = {
            'ip_address': self.ip_address,
            'dns_leak_detected': leak_detected,
            'mismatched_dns': mismatched_dns,
            'confidence': 0.7 if leak_detected else 0.0,
        }
        cache.set(cache_key, result, 1800)
        return result

    def _get_country(self, ip: str) -> str:
        try:
            from ..ip_intelligence.ip_geo_location import IPGeoLocation
            return IPGeoLocation.get_country(ip)
        except Exception:
            return ''
