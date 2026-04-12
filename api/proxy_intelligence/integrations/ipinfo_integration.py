"""
IpInfo Integration — IP intelligence via ipinfo API.
API key from: IntegrationCredential model -> settings.IPINFO_API_KEY -> os.environ["IPINFO_API_KEY"]
"""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class IpInfoIntegration:
    SERVICE_NAME = 'ipinfo'

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
        return getattr(settings, 'IPINFO_API_KEY', None) or os.environ.get('IPINFO_API_KEY', '')

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
        cache_key = f"pi:ipinfo:{ip_address}"
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
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = requests.get(f"https://ipinfo.io/{ip_address}/json", headers=headers, timeout=8)
            if resp.status_code == 429:
                return {"ip_address": ip_address, "error": "rate_limited", "source": self.SERVICE_NAME}
            resp.raise_for_status()
            d = resp.json()
            loc = d.get("loc", "0,0").split(",")
            org = d.get("org", "").split(" ", 1)
            prv = d.get("privacy", {})
            return {
                "ip_address": ip_address, "source": self.SERVICE_NAME,
                "country_code": d.get("country", ""), "city": d.get("city", ""),
                "region": d.get("region", ""), "postal": d.get("postal", ""),
                "timezone": d.get("timezone", ""),
                "latitude": float(loc[0]) if len(loc) == 2 else 0.0,
                "longitude": float(loc[1]) if len(loc) == 2 else 0.0,
                "asn": org[0] if org else "", "isp": org[1] if len(org) > 1 else "",
                "hostname": d.get("hostname", ""), "is_bogon": bool(d.get("bogon", False)),
                "is_vpn": bool(prv.get("vpn")), "is_proxy": bool(prv.get("proxy")),
                "is_tor": bool(prv.get("tor")), "is_relay": bool(prv.get("relay")),
                "is_hosting": bool(prv.get("hosting")),
                "abuse_email": d.get("abuse", {}).get("email", ""),
            }
        except Exception as e:
            return {"ip_address": ip_address, "error": str(e), "source": self.SERVICE_NAME}
