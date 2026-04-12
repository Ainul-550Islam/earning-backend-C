"""CrowdSec Integration — community-driven threat intelligence."""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings
logger = logging.getLogger(__name__)

class CrowdSecIntegration:
    API_BASE = "https://cti.api.crowdsec.net/v2/smoke/{ip}"

    def __init__(self, tenant=None):
        self.api_key = self._resolve_key(tenant)

    def _resolve_key(self, tenant) -> str:
        try:
            from ..models import IntegrationCredential
            cred = IntegrationCredential.objects.filter(
                service='crowdsec', is_active=True
            ).first()
            if cred:
                return cred.api_key
        except Exception:
            pass
        return getattr(settings,'CROWDSEC_API_KEY','') or os.environ.get('CROWDSEC_API_KEY','')

    def check(self, ip_address: str) -> dict:
        if not self.api_key:
            return {'error': 'CROWDSEC_API_KEY not configured'}
        cache_key = f"pi:crowdsec:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            resp = requests.get(
                self.API_BASE.format(ip=ip_address),
                headers={'x-api-key': self.api_key}, timeout=10
            )
            if resp.status_code == 404:
                result = {'ip_address': ip_address, 'is_malicious': False, 'source': 'crowdsec'}
            else:
                resp.raise_for_status()
                data = resp.json()
                result = {
                    'ip_address': ip_address,
                    'is_malicious': bool(data.get('attack_details')),
                    'attack_details': data.get('attack_details', []),
                    'behaviors': [b.get('name') for b in data.get('attack_details', [])],
                    'confidence': data.get('confidence', ''),
                    'source': 'crowdsec',
                }
            cache.set(cache_key, result, 3600)
            return result
        except Exception as e:
            logger.debug(f"CrowdSec check failed: {e}")
            return {'ip_address': ip_address, 'error': str(e), 'source': 'crowdsec'}
