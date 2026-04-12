"""Residential Proxy Detector — detects ISP-IP proxies sold by providers."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

# Known residential proxy provider keywords in ISP/org names
RESIDENTIAL_PROXY_KEYWORDS = [
    'brightdata', 'luminati', 'smartproxy', 'oxylabs', 'netnut',
    'geosurf', 'soax', 'iproyal', 'proxy-cheap', 'stormproxies',
    'residential proxy', 'res proxy', 'rotating proxy',
]

class ResidentialProxyDetector:
    """
    Residential proxies are harder to detect because they use
    real ISP IP addresses. We use ISP keyword + behavioral signals.
    """
    def __init__(self, ip_address: str, isp: str = '', org: str = ''):
        self.ip_address = ip_address
        self.isp = (isp + ' ' + org).lower()

    def detect(self) -> dict:
        cache_key = f"pi:res_proxy:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        matched_keywords = [kw for kw in RESIDENTIAL_PROXY_KEYWORDS if kw in self.isp]
        db_match = self._check_db()
        confidence = 0.0
        if matched_keywords: confidence += 0.6
        if db_match: confidence = max(confidence, db_match)
        confidence = min(confidence, 1.0)

        result = {
            'ip_address': self.ip_address,
            'is_residential_proxy': confidence >= 0.5,
            'confidence': round(confidence, 3),
            'matched_keywords': matched_keywords,
            'detection_method': 'isp_keyword' if matched_keywords else 'db_lookup',
        }
        cache.set(cache_key, result, 3600)
        return result

    def _check_db(self) -> float:
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address,
                threat_type=ThreatType.PROXY,
                is_active=True
            ).first()
            return float(entry.confidence_score) if entry else 0.0
        except Exception:
            return 0.0
