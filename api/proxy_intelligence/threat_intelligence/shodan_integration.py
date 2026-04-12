"""Shodan Integration — checks device exposure and known vulnerabilities."""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings
logger = logging.getLogger(__name__)

class ShodanIntegration:
    API_BASE = "https://api.shodan.io/shodan/host/{ip}?key={key}"

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.api_key = self._resolve_key()

    def _resolve_key(self) -> str:
        try:
            from ..models import IntegrationCredential
            cred = IntegrationCredential.objects.filter(
                service='shodan', is_active=True
            ).first()
            if cred:
                return cred.api_key
        except Exception:
            pass
        return getattr(settings,'SHODAN_API_KEY',None) or os.environ.get('SHODAN_API_KEY','')

    def lookup(self, ip_address: str) -> dict:
        if not self.api_key:
            return {'error': 'SHODAN_API_KEY not configured', 'ip_address': ip_address}
        cache_key = f"pi:shodan:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            url = self.API_BASE.format(ip=ip_address, key=self.api_key)
            resp = requests.get(url, timeout=10)
            if resp.status_code == 404:
                result = {'ip_address': ip_address, 'not_found': True, 'open_ports': []}
            elif resp.status_code == 401:
                return {'error': 'Invalid Shodan API key'}
            else:
                resp.raise_for_status()
                data = resp.json()
                result = {
                    'ip_address': ip_address,
                    'open_ports': data.get('ports', []),
                    'hostnames': data.get('hostnames', []),
                    'vulns': list(data.get('vulns', {}).keys()),
                    'tags': data.get('tags', []),
                    'country_code': data.get('country_code', ''),
                    'isp': data.get('isp', ''),
                    'org': data.get('org', ''),
                    'os': data.get('os', ''),
                    'last_update': data.get('last_update', ''),
                    'is_high_risk': len(data.get('vulns', {})) > 0,
                }
            cache.set(cache_key, result, 86400)
            return result
        except Exception as e:
            logger.error(f"Shodan lookup failed for {ip_address}: {e}")
            return {'error': str(e), 'ip_address': ip_address}
