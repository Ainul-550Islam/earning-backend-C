"""
AbuseIPDB Integration
=====================
Checks IPs against the AbuseIPDB threat database.
"""
import logging
import requests
from django.core.cache import cache
from django.conf import settings
from ..exceptions import AbuseIPDBError

logger = logging.getLogger(__name__)

ABUSEIPDB_API_URL = "https://api.abuseipdb.com/api/v2/check"
CACHE_TTL = 3600 * 4  # 4 hours


class AbuseIPDBIntegration:
    """
    Integrates with AbuseIPDB to get abuse confidence scores for IPs.
    Requires ABUSEIPDB_API_KEY in Django settings or environment.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'ABUSEIPDB_API_KEY', None)
        if not self.api_key:
            import os
            self.api_key = os.environ.get('ABUSEIPDB_API_KEY')

    def check(self, ip_address: str, max_age_days: int = 90) -> dict:
        """
        Check an IP against AbuseIPDB.
        Returns dict with abuse info.
        """
        cache_key = f"pi:abuseipdb:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        if not self.api_key:
            logger.warning("ABUSEIPDB_API_KEY not configured")
            return self._empty_result(ip_address)

        try:
            resp = requests.get(
                ABUSEIPDB_API_URL,
                headers={'Key': self.api_key, 'Accept': 'application/json'},
                params={'ipAddress': ip_address, 'maxAgeInDays': max_age_days, 'verbose': ''},
                timeout=10
            )

            if resp.status_code == 429:
                logger.warning("AbuseIPDB rate limit exceeded")
                return self._empty_result(ip_address)

            resp.raise_for_status()
            data = resp.json().get('data', {})

            result = {
                'ip_address': ip_address,
                'abuse_confidence_score': data.get('abuseConfidenceScore', 0),
                'is_public': data.get('isPublic', True),
                'ip_version': data.get('ipVersion', 4),
                'is_whitelisted': data.get('isWhitelisted', False),
                'country_code': data.get('countryCode', ''),
                'isp': data.get('isp', ''),
                'domain': data.get('domain', ''),
                'total_reports': data.get('totalReports', 0),
                'last_reported': data.get('lastReportedAt', ''),
                'usage_type': data.get('usageType', ''),
                'source': 'abuseipdb',
            }
            cache.set(cache_key, result, CACHE_TTL)
            return result

        except requests.RequestException as e:
            logger.error(f"AbuseIPDB request failed for {ip_address}: {e}")
            raise AbuseIPDBError(f"AbuseIPDB API error: {e}")

    @staticmethod
    def _empty_result(ip_address: str) -> dict:
        return {
            'ip_address': ip_address,
            'abuse_confidence_score': 0,
            'total_reports': 0,
            'source': 'abuseipdb',
            'error': 'API not available',
        }
