"""
VirusTotal Integration
=======================
Checks IPs against VirusTotal's threat intelligence database.
"""
import logging
import requests
from django.core.cache import cache
from django.conf import settings
from ..exceptions import VirusTotalError

logger = logging.getLogger(__name__)

VT_API_URL = "https://www.virustotal.com/api/v3/ip_addresses/{ip}"
CACHE_TTL = 3600 * 6  # 6 hours


class VirusTotalIntegration:
    """
    Queries VirusTotal for IP reputation data.
    Requires VIRUSTOTAL_API_KEY in Django settings.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'VIRUSTOTAL_API_KEY', None)
        if not self.api_key:
            import os
            self.api_key = os.environ.get('VIRUSTOTAL_API_KEY')

    def check(self, ip_address: str) -> dict:
        cache_key = f"pi:virustotal:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        if not self.api_key:
            logger.warning("VIRUSTOTAL_API_KEY not configured")
            return self._empty_result(ip_address)

        try:
            resp = requests.get(
                VT_API_URL.format(ip=ip_address),
                headers={'x-apikey': self.api_key},
                timeout=10
            )

            if resp.status_code == 404:
                result = self._empty_result(ip_address)
                cache.set(cache_key, result, CACHE_TTL)
                return result

            if resp.status_code == 429:
                logger.warning("VirusTotal rate limit exceeded")
                return self._empty_result(ip_address)

            resp.raise_for_status()
            data = resp.json().get('data', {}).get('attributes', {})

            last_analysis = data.get('last_analysis_stats', {})
            malicious = last_analysis.get('malicious', 0)
            suspicious = last_analysis.get('suspicious', 0)
            total = sum(last_analysis.values()) or 1
            confidence = (malicious + suspicious * 0.5) / total

            result = {
                'ip_address': ip_address,
                'malicious_votes': malicious,
                'suspicious_votes': suspicious,
                'harmless_votes': last_analysis.get('harmless', 0),
                'undetected_votes': last_analysis.get('undetected', 0),
                'confidence': round(confidence, 3),
                'country': data.get('country', ''),
                'asn': data.get('asn', ''),
                'as_owner': data.get('as_owner', ''),
                'reputation': data.get('reputation', 0),
                'source': 'virustotal',
            }
            cache.set(cache_key, result, CACHE_TTL)
            return result

        except requests.RequestException as e:
            logger.error(f"VirusTotal request failed for {ip_address}: {e}")
            raise VirusTotalError(f"VirusTotal API error: {e}")

    @staticmethod
    def _empty_result(ip_address: str) -> dict:
        return {
            'ip_address': ip_address,
            'malicious_votes': 0,
            'confidence': 0.0,
            'source': 'virustotal',
            'error': 'API not available',
        }
