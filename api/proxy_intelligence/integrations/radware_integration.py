"""
Radware Integration — IP intelligence via radware API.
API key from: IntegrationCredential model -> settings.RADWARE_API_KEY -> os.environ["RADWARE_API_KEY"]
"""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RadwareIntegration:
    SERVICE_NAME = 'radware'

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.api_key = self._resolve_key()
        self.config = self._resolve_config()

    def _resolve_key(self) -> str:
        try:
            from ..models import IntegrationCredential
            qs = IntegrationCredential.objects.filter(service=self.SERVICE_NAME, is_active=True)
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            cred = qs.first()
            if cred and cred.api_key:
                IntegrationCredential.objects.filter(pk=cred.pk).update(used_today=cred.used_today + 1)
                return cred.api_key
        except Exception as e:
            logger.debug(f"Credential lookup failed: {e}")
        return getattr(settings, 'RADWARE_API_KEY', None) or os.environ.get('RADWARE_API_KEY', '')

    def _resolve_config(self) -> dict:
        try:
            from ..models import IntegrationCredential
            qs = IntegrationCredential.objects.filter(service=self.SERVICE_NAME, is_active=True)
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            cred = qs.first()
            if cred and cred.config:
                return cred.config
        except Exception:
            pass
        return {}

    def check(self, ip_address: str) -> dict:
        cache_key = f"pi:radware:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        if not self.api_key:
            return {'ip_address': ip_address, 'error': f'{self.SERVICE_NAME} API key not configured', 'source': self.SERVICE_NAME}
        result = self._fetch(ip_address)
        if result and 'error' not in result:
            cache.set(cache_key, result, 3600)
        return result

    def enrich_ip_intelligence(self, ip_address: str) -> bool:
        try:
            result = self.check(ip_address)
            if 'error' in result:
                return False
            from ..models import IPIntelligence
            obj, _ = IPIntelligence.objects.get_or_create(ip_address=ip_address, defaults={'tenant': self.tenant})
            for field in ('country_code','country_name','city','isp','asn','latitude','longitude','timezone'):
                val = result.get(field)
                if val and hasattr(obj, field):
                    setattr(obj, field, val)
            for flag in ('is_vpn','is_proxy','is_tor','is_datacenter'):
                if result.get(flag):
                    setattr(obj, flag, True)
            if result.get('fraud_score'):
                obj.fraud_score = max(obj.fraud_score, result['fraud_score'])
            obj.save()
            return True
        except Exception as e:
            logger.error(f"{self.SERVICE_NAME} enrich failed for {ip_address}: {e}")
            return False

FETCH_PLACEHOLDER
    def _fetch(self, ip_address: str) -> dict:
        try:
            base_url = self.config.get("api_url", "https://api.radware.com/threat/v1/ip")
            resp = requests.get(
                f"{base_url}/{ip_address}",
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                timeout=10
            )
            if resp.status_code in (401, 403):
                return {"ip_address": ip_address, "error": "invalid_credentials", "source": self.SERVICE_NAME}
            if resp.status_code == 429:
                return {"ip_address": ip_address, "error": "rate_limited", "source": self.SERVICE_NAME}
            if resp.status_code == 404:
                return {"ip_address": ip_address, "found": False, "source": self.SERVICE_NAME}
            resp.raise_for_status()
            d = resp.json()
            return {
                "ip_address": ip_address, "source": self.SERVICE_NAME,
                "threat_level": d.get("threatLevel", "LOW"),
                "categories": d.get("categories", []),
                "is_malicious": d.get("threatLevel", "LOW") in ("HIGH", "CRITICAL"),
                "bot_score": int(d.get("botScore", 0) or 0),
                "is_bot": bool(d.get("isBot", False)),
                "country_code": d.get("country", ""), "asn": str(d.get("asn", "")),
                "last_seen": d.get("lastSeen", ""), "first_seen": d.get("firstSeen", ""),
            }
        except Exception as e:
            return {"ip_address": ip_address, "error": str(e), "source": self.SERVICE_NAME}
