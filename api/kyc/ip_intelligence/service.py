# kyc/ip_intelligence/service.py  ── WORLD #1
"""
IP Intelligence Service.
- Geolocation (country, city, ISP)
- VPN / Proxy / Tor detection
- IP reputation scoring
- High-risk country detection

Providers: MaxMind GeoIP2, ipinfo.io, ip-api.com, AbuseIPDB
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# High-risk countries for KYC (FATF grey/black list 2025)
HIGH_RISK_COUNTRIES = {
    'KP',  # North Korea
    'IR',  # Iran
    'SY',  # Syria
    'YE',  # Yemen
    'SO',  # Somalia
    'AF',  # Afghanistan
    'MM',  # Myanmar
    'PK',  # Pakistan (grey)
    'SS',  # South Sudan
    'VE',  # Venezuela
}

# Countries requiring Enhanced Due Diligence
EDD_COUNTRIES = HIGH_RISK_COUNTRIES | {
    'NG', 'ET', 'ML', 'SN', 'TZ', 'CM',
}


class IPIntelligenceService:

    @staticmethod
    def analyze(ip_address: str) -> dict:
        """
        Full IP analysis.
        Returns: geo data + risk flags + reputation score.
        """
        result = {
            'ip':            ip_address,
            'country_code':  '',
            'country_name':  '',
            'city':          '',
            'region':        '',
            'isp':           '',
            'org':           '',
            'timezone':      '',
            'is_vpn':        False,
            'is_proxy':      False,
            'is_tor':        False,
            'is_datacenter': False,
            'is_high_risk_country': False,
            'requires_edd':  False,
            'risk_score':    0,
            'abuse_score':   0,
            'provider':      'unknown',
            'error':         '',
        }

        if not ip_address or ip_address in ('127.0.0.1', '::1', 'localhost'):
            result['country_code'] = 'BD'
            result['country_name'] = 'Bangladesh'
            result['provider']     = 'local'
            return result

        # Try providers in order
        for method in [
            IPIntelligenceService._try_maxmind,
            IPIntelligenceService._try_ipinfo,
            IPIntelligenceService._try_ipapi,
        ]:
            try:
                data = method(ip_address)
                if data:
                    result.update(data)
                    break
            except Exception as e:
                logger.warning(f"IP intelligence provider failed: {e}")

        # Post-process risk flags
        cc = result.get('country_code', '')
        result['is_high_risk_country'] = cc in HIGH_RISK_COUNTRIES
        result['requires_edd']         = cc in EDD_COUNTRIES

        # Composite risk score
        risk = 0
        if result['is_vpn']:        risk += 25
        if result['is_proxy']:      risk += 30
        if result['is_tor']:        risk += 50
        if result['is_datacenter']: risk += 15
        if result['is_high_risk_country']: risk += 40
        if result['abuse_score'] > 50:     risk += 20
        result['risk_score'] = min(risk, 100)

        return result

    @staticmethod
    def _try_maxmind(ip: str) -> dict:
        """MaxMind GeoIP2 (most accurate, paid)"""
        try:
            import geoip2.database
            db_path = getattr(settings, 'MAXMIND_DB_PATH', '/usr/local/share/GeoIP/GeoLite2-City.mmdb')
            with geoip2.database.Reader(db_path) as reader:
                resp = reader.city(ip)
                return {
                    'country_code': resp.country.iso_code or '',
                    'country_name': resp.country.name or '',
                    'city':         resp.city.name or '',
                    'region':       resp.subdivisions.most_specific.name or '',
                    'timezone':     resp.location.time_zone or '',
                    'provider':     'maxmind',
                }
        except Exception:
            return {}

    @staticmethod
    def _try_ipinfo(ip: str) -> dict:
        """ipinfo.io API (free tier: 50k/month)"""
        try:
            import requests
            token = getattr(settings, 'IPINFO_TOKEN', '')
            url   = f'https://ipinfo.io/{ip}/json'
            if token: url += f'?token={token}'
            resp  = requests.get(url, timeout=5)
            if resp.status_code != 200: return {}
            data  = resp.json()
            return {
                'country_code': data.get('country', ''),
                'city':         data.get('city', ''),
                'region':       data.get('region', ''),
                'isp':          data.get('org', ''),
                'timezone':     data.get('timezone', ''),
                'is_vpn':       data.get('privacy', {}).get('vpn', False),
                'is_proxy':     data.get('privacy', {}).get('proxy', False),
                'is_tor':       data.get('privacy', {}).get('tor', False),
                'is_datacenter':data.get('privacy', {}).get('hosting', False),
                'provider':     'ipinfo',
            }
        except Exception:
            return {}

    @staticmethod
    def _try_ipapi(ip: str) -> dict:
        """ip-api.com (free, no auth needed, 45 req/min)"""
        try:
            import requests
            resp = requests.get(
                f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,regionName,isp,org,proxy,hosting',
                timeout=5
            )
            if resp.status_code != 200: return {}
            data = resp.json()
            if data.get('status') != 'success': return {}
            return {
                'country_code':  data.get('countryCode', ''),
                'country_name':  data.get('country', ''),
                'city':          data.get('city', ''),
                'region':        data.get('regionName', ''),
                'isp':           data.get('isp', ''),
                'org':           data.get('org', ''),
                'is_proxy':      data.get('proxy', False),
                'is_datacenter': data.get('hosting', False),
                'provider':      'ip-api',
            }
        except Exception:
            return {}

    @staticmethod
    def log_ip(user, ip_address: str, action: str = 'kyc_access', kyc=None):
        """Log IP to KYCIPTracker model."""
        try:
            from kyc.models import KYCIPTracker
            intel = IPIntelligenceService.analyze(ip_address)
            KYCIPTracker.objects.create(
                user=user,
                kyc=kyc,
                ip_address=ip_address,
                action=action,
                country=intel.get('country_name', ''),
                city=intel.get('city', ''),
                is_vpn=intel.get('is_vpn', False),
                is_proxy=intel.get('is_proxy', False),
                is_tor=intel.get('is_tor', False),
                risk_score=intel.get('risk_score', 0),
            )
        except Exception as e:
            logger.warning(f"IP log failed: {e}")
