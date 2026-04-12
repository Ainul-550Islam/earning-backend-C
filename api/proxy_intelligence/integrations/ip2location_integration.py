"""
Ip2Location Integration — IP intelligence via ip2location API.
API key from: IntegrationCredential model -> settings.IP2LOCATION_API_KEY -> os.environ["IP2LOCATION_API_KEY"]
"""
import logging, os, requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class Ip2LocationIntegration:
    SERVICE_NAME = 'ip2location'

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
        return getattr(settings, 'IP2LOCATION_API_KEY', None) or os.environ.get('IP2LOCATION_API_KEY', '')

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
        cache_key = f"pi:ip2location:{ip_address}"
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
                f"https://api.ip2location.io/?key={self.api_key}&ip={ip_address}&format=json",
                timeout=8
            )
            if resp.status_code == 429:
                return {"ip_address": ip_address, "error": "rate_limited", "source": self.SERVICE_NAME}
            resp.raise_for_status()
            d = resp.json()
            if "error" in d:
                return {"ip_address": ip_address, "error": d["error"].get("info","api_error"), "source": self.SERVICE_NAME}
            proxy_type = d.get("proxy_type", "")
            return {
                "ip_address": ip_address, "source": self.SERVICE_NAME,
                "country_code": d.get("country_code", ""), "country_name": d.get("country_name", ""),
                "region": d.get("region_name", ""), "city": d.get("city_name", ""),
                "latitude": float(d.get("latitude", 0) or 0),
                "longitude": float(d.get("longitude", 0) or 0),
                "zip_code": d.get("zip_code", ""), "timezone": d.get("time_zone", ""),
                "asn": str(d.get("asn", "")), "isp": d.get("isp", ""),
                "domain": d.get("domain", ""), "net_speed": d.get("net_speed", ""),
                "is_proxy": proxy_type not in ("-", "", "NOT"),
                "proxy_type": proxy_type, "threat": d.get("threat", ""),
                "is_vpn": "VPN" in proxy_type, "is_tor": "TOR" in proxy_type,
                "is_datacenter": "DCH" in proxy_type, "is_residential": proxy_type == "RES",
            }
        except Exception as e:
            return {"ip_address": ip_address, "error": str(e), "source": self.SERVICE_NAME}
