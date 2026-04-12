"""IP Organization — resolves organization data from ASN/RDAP."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class IPOrganizationLookup:
    @classmethod
    def lookup(cls, ip_address: str) -> dict:
        cache_key = f"pi:org:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = cls._from_asn(ip_address) or cls._from_rdap(ip_address) or {
            'ip_address': ip_address, 'organization': '',
            'asn': '', 'isp': '', 'country_code': '', 'source': 'unavailable'
        }
        cache.set(cache_key, result, 86400)
        return result

    @classmethod
    def _from_asn(cls, ip: str) -> dict:
        try:
            from .ip_asn_lookup import ASNLookup
            d = ASNLookup.lookup(ip)
            if d.get('asn_name'):
                return {'ip_address': ip, 'organization': d.get('asn_name',''),
                        'asn': d.get('asn',''), 'isp': d.get('isp',''),
                        'country_code': d.get('country',''), 'source': 'asn_lookup'}
        except Exception:
            pass
        return {}

    @classmethod
    def _from_rdap(cls, ip: str) -> dict:
        try:
            import requests
            resp = requests.get(f"https://rdap.arin.net/registry/ip/{ip}",
                                headers={'Accept':'application/json'}, timeout=5)
            if resp.status_code == 200:
                d = resp.json()
                net = d.get('network', {})
                return {'ip_address': ip, 'organization': net.get('name',''),
                        'asn': '', 'isp': net.get('handle',''),
                        'country_code': net.get('country',''), 'source': 'rdap'}
        except Exception:
            pass
        return {}

    @classmethod
    def get_org_name(cls, ip_address: str) -> str:
        return cls.lookup(ip_address).get('organization', '')
