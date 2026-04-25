# api/payment_gateways/targeting/GeoTargeting.py
# GEO targeting and IP geolocation

import logging
import socket
from django.core.cache import cache
logger = logging.getLogger(__name__)

# Country → region mapping for BD-specific use
BD_REGIONS = {
    'BD': 'South Asia',
    'IN': 'South Asia',
    'PK': 'South Asia',
    'LK': 'South Asia',
    'NP': 'South Asia',
    'US': 'North America',
    'CA': 'North America',
    'GB': 'Europe',
    'DE': 'Europe',
    'FR': 'Europe',
    'AU': 'Oceania',
    'SG': 'Southeast Asia',
    'MY': 'Southeast Asia',
    'AE': 'Middle East',
    'SA': 'Middle East',
}

# Countries with high-value CPA offers
TIER1_COUNTRIES = {'US','CA','GB','AU','DE','FR','NL','SE','NO','DK','CH','AT','NZ','IE','SG'}
TIER2_COUNTRIES = {'JP','KR','IT','ES','PL','BE','PT','AE','SA','IL','HK','TW'}
TIER3_COUNTRIES = {'BD','IN','PK','PH','ID','VN','TH','MY','BR','MX','AR','CO','ZA','EG','NG'}


class GeoTargeting:
    """Geo lookup and targeting utilities."""

    def get_country_from_ip(self, ip_address: str) -> dict:
        """
        Get country info from IP address.
        Uses CloudFlare header if available, otherwise free GeoIP API.
        Result cached for 1 hour.
        """
        if not ip_address or ip_address in ('127.0.0.1', '::1', 'localhost'):
            return {'country_code': '', 'country_name': '', 'region': '', 'city': ''}

        cache_key = f'geo:{ip_address}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        result = self._lookup_ip(ip_address)
        cache.set(cache_key, result, 3600)
        return result

    def _lookup_ip(self, ip: str) -> dict:
        """Lookup IP via free API (ip-api.com)."""
        try:
            import urllib.request, json
            url  = f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,isp'
            req  = urllib.request.Request(url, headers={'User-Agent': 'PaymentGateway/1.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
            if data.get('status') == 'success':
                return {
                    'country_code': data.get('countryCode', ''),
                    'country_name': data.get('country', ''),
                    'region':       data.get('regionName', ''),
                    'city':         data.get('city', ''),
                    'carrier':      data.get('isp', ''),
                }
        except Exception as e:
            logger.debug(f'GeoIP lookup failed for {ip}: {e}')
        return {'country_code': '', 'country_name': '', 'region': '', 'city': '', 'carrier': ''}

    def get_country_tier(self, country_code: str) -> int:
        """Return traffic tier for a country (1=premium, 2=mid, 3=standard)."""
        if country_code in TIER1_COUNTRIES: return 1
        if country_code in TIER2_COUNTRIES: return 2
        return 3

    def get_payout_multiplier(self, country_code: str) -> float:
        """Get payout multiplier based on country tier."""
        tier = self.get_country_tier(country_code)
        return {1: 1.0, 2: 0.7, 3: 0.4}.get(tier, 0.3)

    def is_country_allowed(self, country_code: str, target_countries: list,
                           blocked_countries: list) -> bool:
        if country_code in (blocked_countries or []):
            return False
        if not target_countries:
            return True  # Worldwide
        return country_code in target_countries
