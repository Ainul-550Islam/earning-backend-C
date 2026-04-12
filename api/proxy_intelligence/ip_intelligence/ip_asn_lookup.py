"""
ASN Lookup
==========
Resolves IP addresses to their Autonomous System Number (ASN) and organization info.
"""
import logging
import socket
import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ASNLookup:
    """Looks up ASN info for an IP address using multiple fallback methods."""

    @classmethod
    def lookup(cls, ip_address: str) -> dict:
        cache_key = f"pi:asn:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = cls._lookup_ipinfo(ip_address) or cls._lookup_rdap(ip_address) or {}
        if result:
            cache.set(cache_key, result, 86400)
        return result

    @classmethod
    def _lookup_ipinfo(cls, ip_address: str) -> dict:
        """Use ipinfo.io free tier (no key required for basic info)."""
        try:
            resp = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                org = data.get('org', '')  # "AS12345 Some ISP"
                asn = ''
                asn_name = ''
                if org and org.startswith('AS'):
                    parts = org.split(' ', 1)
                    asn = parts[0]
                    asn_name = parts[1] if len(parts) > 1 else ''
                return {
                    'asn': asn,
                    'asn_name': asn_name,
                    'isp': asn_name,
                    'country': data.get('country', ''),
                    'city': data.get('city', ''),
                    'region': data.get('region', ''),
                    'org': org,
                }
        except Exception as e:
            logger.debug(f"ipinfo lookup failed for {ip_address}: {e}")
        return {}

    @classmethod
    def _lookup_rdap(cls, ip_address: str) -> dict:
        """Fallback: use RDAP protocol."""
        try:
            resp = requests.get(
                f"https://rdap.arin.net/registry/ip/{ip_address}",
                timeout=5, headers={'Accept': 'application/json'}
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get('name', '')
                return {'asn': '', 'asn_name': name, 'isp': name}
        except Exception as e:
            logger.debug(f"RDAP lookup failed for {ip_address}: {e}")
        return {}
