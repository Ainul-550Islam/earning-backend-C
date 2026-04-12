"""
IPQualityScore Integration  (PRODUCTION-READY - COMPLETE)
===========================================================
Checks IPs against IPQualityScore's fraud & proxy detection API.
API key is loaded from the IntegrationCredential model first,
then falls back to Django settings / environment variables.

IPQS returns: fraud_score, proxy, vpn, tor, bot_status,
              abuse_velocity, connection_type, ISP, country, etc.
"""
import logging
import os
import requests
from django.core.cache import cache
from django.conf import settings
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)

IPQS_API_BASE = "https://ipqualityscore.com/api/json/ip/{api_key}/{ip}"
CACHE_TTL = 3600 * 4  # 4 hours


class IPQualityScoreIntegration:
    """
    Integrates with IPQualityScore (IPQS) API.

    Priority order for API key:
      1. IntegrationCredential model (per-tenant, stored in DB)
      2. settings.IPQUALITYSCORE_API_KEY
      3. os.environ['IPQUALITYSCORE_API_KEY']
    """

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.api_key = self._resolve_api_key()

    # ── API Key Resolution ───────────────────────────────────────────────

    def _resolve_api_key(self) -> Optional[str]:
        # 1. Try IntegrationCredential model
        try:
            from ..models import IntegrationCredential
            qs = IntegrationCredential.objects.filter(
                service='ipqualityscore',
                is_active=True
            )
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            cred = qs.first()
            if cred and cred.api_key:
                # Increment usage counter
                IntegrationCredential.objects.filter(pk=cred.pk).update(
                    used_today=cred.used_today + 1
                )
                return cred.api_key
        except Exception as e:
            logger.debug(f"IntegrationCredential lookup failed: {e}")

        # 2. Django settings
        key = getattr(settings, 'IPQUALITYSCORE_API_KEY', None)
        if key:
            return key

        # 3. Environment variable
        return os.environ.get('IPQUALITYSCORE_API_KEY')

    # ── Main Check ───────────────────────────────────────────────────────

    def check(self, ip_address: str, strict_mode: bool = False,
              allow_public_access_points: bool = False,
              lighter_penalties: bool = False,
              fast: bool = True) -> dict:
        """
        Check an IP address with IPQS.

        Args:
            ip_address:                  The IP to check.
            strict_mode:                 Increases sensitivity for proxies.
            allow_public_access_points:  Don't flag Tor/public WiFi.
            lighter_penalties:           Reduce scores for IPs with low reports.
            fast:                        Use fast mode (reduced accuracy).

        Returns:
            Structured dict with all IPQS signals.
        """
        cache_key = f"pi:ipqs:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.api_key:
            logger.warning("IPQUALITYSCORE_API_KEY not configured. Returning empty result.")
            return self._empty_result(ip_address, error='API key not configured')

        url = IPQS_API_BASE.format(api_key=self.api_key, ip=ip_address)
        params = {
            'strictness':                 1 if strict_mode else 0,
            'allow_public_access_points': 'true' if allow_public_access_points else 'false',
            'lighter_penalties':          'true' if lighter_penalties else 'false',
            'fast':                       'true' if fast else 'false',
            'user_agent':                 '',
            'user_language':              'en-US',
        }

        try:
            resp = requests.get(url, params=params, timeout=8)

            if resp.status_code == 401:
                raise IntegrationError("IPQS: Invalid API key (401).")
            if resp.status_code == 429:
                logger.warning("IPQS rate limit hit. Returning empty result.")
                return self._empty_result(ip_address, error='rate_limited')
            resp.raise_for_status()

            data = resp.json()

            if not data.get('success', False):
                msg = data.get('message', 'Unknown IPQS error')
                logger.warning(f"IPQS returned success=false for {ip_address}: {msg}")
                return self._empty_result(ip_address, error=msg)

            result = self._parse_response(ip_address, data)
            cache.set(cache_key, result, CACHE_TTL)
            return result

        except requests.Timeout:
            logger.warning(f"IPQS timeout for {ip_address}")
            return self._empty_result(ip_address, error='timeout')
        except requests.RequestException as e:
            logger.error(f"IPQS request failed for {ip_address}: {e}")
            raise IntegrationError(f"IPQS API error: {e}")

    # ── Response Parsing ─────────────────────────────────────────────────

    @staticmethod
    def _parse_response(ip_address: str, data: dict) -> dict:
        """
        Maps IPQS raw response to our standardised format.
        """
        fraud_score = int(data.get('fraud_score', 0))

        # IPQS connection_type values: "Residential", "Corporate", "Education",
        # "Mobile", "Data Center", "Satellite"
        connection_type = data.get('connection_type', '').lower()
        is_datacenter = connection_type in ('data center', 'datacenter')
        is_mobile = connection_type == 'mobile'

        return {
            'source':                  'ipqualityscore',
            'ip_address':              ip_address,
            'success':                 True,

            # Core fraud signals
            'fraud_score':             fraud_score,          # 0-100
            'is_proxy':                bool(data.get('proxy', False)),
            'is_vpn':                  bool(data.get('vpn', False)),
            'is_tor':                  bool(data.get('tor', False)),
            'is_bot':                  bool(data.get('bot_status', False)),
            'is_crawler':              bool(data.get('is_crawler', False)),

            # Connection type
            'connection_type':         data.get('connection_type', ''),
            'is_datacenter':           is_datacenter,
            'is_mobile':               is_mobile,
            'is_residential':          connection_type == 'residential',

            # Geo & ISP
            'country_code':            data.get('country_code', ''),
            'region':                  data.get('region', ''),
            'city':                    data.get('city', ''),
            'isp':                     data.get('ISP', ''),
            'organization':            data.get('organization', ''),
            'asn':                     str(data.get('ASN', '')),
            'host':                    data.get('host', ''),
            'timezone':                data.get('timezone', ''),
            'latitude':                float(data.get('latitude', 0)),
            'longitude':               float(data.get('longitude', 0)),

            # Abuse signals
            'abuse_velocity':          data.get('abuse_velocity', 'none'),
            # "none" | "low" | "medium" | "high"
            'recent_abuse':            bool(data.get('recent_abuse', False)),
            'frequent_abuser':         bool(data.get('frequent_abuser', False)),
            'mobile_carrier':          data.get('mobile_carrier', ''),

            # Recommended action
            'recommended_action':      _recommended_action(fraud_score, data),
        }

    @staticmethod
    def _empty_result(ip_address: str, error: str = '') -> dict:
        return {
            'source':       'ipqualityscore',
            'ip_address':   ip_address,
            'success':      False,
            'fraud_score':  0,
            'is_proxy':     False,
            'is_vpn':       False,
            'is_tor':       False,
            'is_bot':       False,
            'error':        error,
        }

    # ── Convenience Methods ───────────────────────────────────────────────

    def enrich_ip_intelligence(self, ip_address: str) -> bool:
        """
        Run IPQS check and write results into IPIntelligence model.
        Returns True if the record was updated successfully.
        """
        try:
            result = self.check(ip_address)
            if not result.get('success'):
                return False

            from ..models import IPIntelligence
            obj, _ = IPIntelligence.objects.get_or_create(
                ip_address=ip_address,
                defaults={'tenant': self.tenant}
            )
            obj.is_vpn          |= result['is_vpn']
            obj.is_proxy        |= result['is_proxy']
            obj.is_tor          |= result['is_tor']
            obj.is_datacenter   |= result['is_datacenter']
            obj.is_mobile        = result['is_mobile']
            obj.fraud_score      = result['fraud_score']
            obj.isp              = result.get('isp', obj.isp)
            obj.country_code     = result.get('country_code', obj.country_code)
            obj.city             = result.get('city', obj.city)
            obj.timezone         = result.get('timezone', obj.timezone)
            obj.latitude         = result.get('latitude', obj.latitude)
            obj.longitude        = result.get('longitude', obj.longitude)
            obj.asn              = result.get('asn', obj.asn)
            obj.organization     = result.get('organization', obj.organization)
            obj.last_checked     = __import__('django.utils.timezone', fromlist=['now']).now()
            obj.save()
            return True
        except Exception as e:
            logger.error(f"IPQS enrich failed for {ip_address}: {e}")
            return False


# ── Standalone helper ─────────────────────────────────────────────────────

def _recommended_action(fraud_score: int, data: dict) -> str:
    if data.get('tor') or data.get('bot_status') or fraud_score >= 85:
        return 'block'
    if data.get('vpn') or data.get('proxy') or fraud_score >= 60:
        return 'challenge'
    if fraud_score >= 40 or data.get('recent_abuse'):
        return 'flag'
    return 'allow'


# For type checking
from typing import Optional
