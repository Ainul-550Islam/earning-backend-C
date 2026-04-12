# services/geo/GeoIPService.py
"""IP → Country/City/Timezone service (MaxMind GeoIP2 style)"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class GeoIPService:
    """IP address থেকে geographic information lookup করে"""

    def lookup(self, ip_address: str) -> Dict:
        """IP থেকে country/city/tz পাওয়ার main method"""
        try:
            # 1. Database lookup
            from ..models.geo import GeoIPMapping
            mapping = GeoIPMapping.lookup(ip_address)
            if mapping:
                return self._mapping_to_dict(mapping)
            # 2. External API fallback (ip-api.com free tier)
            return self._external_lookup(ip_address)
        except Exception as e:
            logger.error(f"GeoIP lookup failed for {ip_address}: {e}")
            return self._empty_result(ip_address)

    def _mapping_to_dict(self, mapping) -> Dict:
        return {
            'ip': mapping.ip_start,
            'country_code': mapping.country_code or '',
            'country_name': mapping.country.name if mapping.country else '',
            'region': mapping.region_name or '',
            'city': mapping.city_name or '',
            'timezone': mapping.timezone.name if mapping.timezone else '',
            'latitude': float(mapping.latitude) if mapping.latitude else None,
            'longitude': float(mapping.longitude) if mapping.longitude else None,
            'isp': mapping.isp or '',
            'asn': mapping.asn or '',
            'is_vpn': mapping.is_vpn,
            'is_proxy': mapping.is_proxy,
            'is_tor': mapping.is_tor,
            'threat_score': mapping.threat_score,
            'source': mapping.source,
        }

    def _external_lookup(self, ip_address: str) -> Dict:
        """External API fallback — ip-api.com"""
        try:
            import urllib.request, json
            url = f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,region,city,lat,lon,timezone,isp,org,as,proxy,hosting"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            if data.get('status') == 'success':
                return {
                    'ip': ip_address,
                    'country_code': data.get('countryCode', ''),
                    'country_name': data.get('country', ''),
                    'region': data.get('region', ''),
                    'city': data.get('city', ''),
                    'timezone': data.get('timezone', ''),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'isp': data.get('isp', ''),
                    'is_vpn': data.get('proxy', False),
                    'is_proxy': data.get('proxy', False),
                    'is_datacenter': data.get('hosting', False),
                    'is_tor': False,
                    'threat_score': None,
                    'source': 'ip-api',
                }
        except Exception as e:
            logger.error(f"External GeoIP failed for {ip_address}: {e}")
        return self._empty_result(ip_address)

    def _empty_result(self, ip_address: str) -> Dict:
        return {
            'ip': ip_address, 'country_code': '', 'country_name': '',
            'region': '', 'city': '', 'timezone': '',
            'latitude': None, 'longitude': None, 'isp': '',
            'is_vpn': False, 'is_proxy': False, 'is_datacenter': False,
            'is_tor': False, 'threat_score': None, 'source': 'unknown',
        }

    def get_language_for_ip(self, ip_address: str) -> Optional[str]:
        """IP থেকে recommended language code return করে"""
        try:
            result = self.lookup(ip_address)
            country_code = result.get('country_code', '')
            if not country_code:
                return None
            from ..models.geo import CountryLanguage
            official = CountryLanguage.objects.filter(
                country__code=country_code, is_official=True
            ).order_by('-speaker_percentage').first()
            if official:
                return official.language.code
        except Exception as e:
            logger.error(f"Language for IP failed: {e}")
        return None
