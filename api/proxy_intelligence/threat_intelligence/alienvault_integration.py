"""AlienVault OTX Integration — Open Threat Exchange."""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings
logger = logging.getLogger(__name__)

class AlienVaultIntegration:
    API_BASE = "https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/reputation"

    def __init__(self, tenant=None):
        self.api_key = self._resolve_key(tenant)

    def _resolve_key(self, tenant) -> str:
        try:
            from ..models import IntegrationCredential
            cred = IntegrationCredential.objects.filter(
                service='alienvault', is_active=True
            ).first()
            if cred:
                return cred.api_key
        except Exception:
            pass
        return getattr(settings,'ALIENVAULT_API_KEY','') or os.environ.get('ALIENVAULT_API_KEY','')

    def check(self, ip_address: str) -> dict:
        cache_key = f"pi:av:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        headers = {'X-OTX-API-KEY': self.api_key} if self.api_key else {}
        try:
            resp = requests.get(
                self.API_BASE.format(ip=ip_address),
                headers=headers, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            result = {
                'ip_address': ip_address,
                'reputation': data.get('reputation', 0),
                'threat_score': data.get('threat_score', 0),
                'activities': data.get('activities', []),
                'is_malicious': data.get('reputation', 0) < -1,
                'source': 'alienvault',
            }
            cache.set(cache_key, result, 7200)
            return result
        except Exception as e:
            logger.debug(f"AlienVault check failed for {ip_address}: {e}")
            return {'ip_address': ip_address, 'error': str(e), 'source': 'alienvault'}
