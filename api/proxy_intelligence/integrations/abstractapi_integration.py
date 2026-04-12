"""
AbstractApi Integration — IP intelligence via abstractapi API.
API key from: IntegrationCredential model -> settings.ABSTRACTAPI_API_KEY -> os.environ["ABSTRACTAPI_API_KEY"]
"""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class AbstractApiIntegration:
    SERVICE_NAME = 'abstractapi'

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
        return getattr(settings, 'ABSTRACTAPI_API_KEY', None) or os.environ.get('ABSTRACTAPI_API_KEY', '')

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
        cache_key = f"pi:abstractapi:{ip_address}"
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
            resp = requests.get(
                f"https://ipgeolocation.abstractapi.com/v1/?api_key={self.api_key}&ip_address={ip_address}",
                timeout=8
            )
            if resp.status_code == 429:
                return {"ip_address": ip_address, "error": "rate_limited", "source": self.SERVICE_NAME}
            resp.raise_for_status()
            d = resp.json()
            sec = d.get("security", {})
            return {
                "ip_address": ip_address, "source": self.SERVICE_NAME,
                "country_code": d.get("country_code", ""), "country_name": d.get("country", ""),
                "city": d.get("city", ""), "region": d.get("region", ""),
                "latitude": float(d.get("latitude", 0) or 0),
                "longitude": float(d.get("longitude", 0) or 0),
                "timezone": d.get("timezone", {}).get("name", ""),
                "isp": d.get("connection", {}).get("isp_name", ""),
                "asn": str(d.get("connection", {}).get("autonomous_system_number", "")),
                "is_vpn": bool(sec.get("is_vpn")), "is_proxy": bool(sec.get("is_proxy")),
                "is_tor": bool(sec.get("is_tor_exit_node")),
                "fraud_score": int(sec.get("threat_score", 0)),
                "is_malicious": bool(sec.get("is_vpn") or sec.get("is_tor_exit_node")),
            }
        except Exception as e:
            return {"ip_address": ip_address, "error": str(e), "source": self.SERVICE_NAME}
