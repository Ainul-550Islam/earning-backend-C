# services/services_loca/GeoService.py
"""
GeoService — High-level geographic service facade.
Used in middleware for IP→language/currency/timezone auto-detection.
CPAlead country-based offer targeting এখান থেকে।
"""
import logging
from typing import Optional, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)
CACHE_TTL = 3600 * 24


class GeoService:
    """
    Complete geographic service — IP detect, country info, city search.
    Middleware এই service ব্যবহার করে user-এর location detect করে।
    """

    def detect_from_ip(self, ip_address: str) -> Dict:
        """
        IP থেকে সম্পূর্ণ geo info পাওয়া।
        Returns: country, city, timezone, language, currency
        """
        cache_key = f"geo_detect_{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..geo.GeoIPService import GeoIPService
            raw = GeoIPService().lookup(ip_address)
            result = self._enrich_geo_data(raw)
            if result.get('country_code'):
                cache.set(cache_key, result, CACHE_TTL)
            return result
        except Exception as e:
            logger.error(f"GeoService.detect_from_ip failed for {ip_address}: {e}")
            return self._empty_geo()

    def _enrich_geo_data(self, raw: Dict) -> Dict:
        """Raw geo data-তে language + currency + timezone যোগ করে"""
        result = dict(raw)
        country_code = raw.get('country_code', '')
        if not country_code:
            return result
        try:
            # Language
            result['recommended_language'] = self.get_language_for_country(country_code)
            # Currency
            result['recommended_currency'] = self.get_currency_for_country(country_code)
            # Timezone (use from raw if available)
            if not result.get('timezone'):
                result['timezone'] = self.get_timezone_for_country(country_code)
            # GDPR
            result['requires_gdpr'] = self._country_requires_gdpr(country_code)
        except Exception as e:
            logger.error(f"_enrich_geo_data failed: {e}")
        return result

    def get_language_for_country(self, country_code: str) -> Optional[str]:
        """Country code থেকে official language code পাওয়া"""
        cache_key = f"geo_lang_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.geo import CountryLanguage
            official = CountryLanguage.objects.filter(
                country__code=country_code.upper(),
                is_official=True
            ).select_related('language').order_by('-speaker_percentage').first()
            code = official.language.code if official else None
            if not code:
                # Country model-এ languages_spoken field check
                from ..models.core import Country
                country = Country.objects.filter(code=country_code.upper()).first()
                if country and country.languages_spoken:
                    langs = country.languages_spoken
                    code = langs[0] if isinstance(langs, list) else langs
            if code:
                cache.set(cache_key, code, CACHE_TTL)
            return code
        except Exception as e:
            logger.error(f"get_language_for_country failed: {e}")
            return None

    def get_currency_for_country(self, country_code: str) -> Optional[str]:
        """Country code থেকে primary currency code পাওয়া"""
        cache_key = f"geo_currency_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.geo import CountryCurrency
            cc = CountryCurrency.objects.filter(
                country__code=country_code.upper(), is_primary=True
            ).select_related('currency').first()
            if cc:
                code = cc.currency.code
            else:
                from ..models.core import Country
                country = Country.objects.filter(code=country_code.upper()).first()
                code = country.currency_code if country else 'USD'
            if code:
                cache.set(cache_key, code, CACHE_TTL)
            return code
        except Exception as e:
            logger.error(f"get_currency_for_country failed: {e}")
            return 'USD'

    def get_timezone_for_country(self, country_code: str) -> Optional[str]:
        """Country code থেকে default timezone পাওয়া"""
        cache_key = f"geo_tz_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            # Known country → timezone mappings
            COUNTRY_TZ = {
                'BD': 'Asia/Dhaka', 'IN': 'Asia/Kolkata', 'PK': 'Asia/Karachi',
                'US': 'America/New_York', 'GB': 'Europe/London', 'DE': 'Europe/Berlin',
                'FR': 'Europe/Paris', 'JP': 'Asia/Tokyo', 'CN': 'Asia/Shanghai',
                'AU': 'Australia/Sydney', 'SA': 'Asia/Riyadh', 'AE': 'Asia/Dubai',
                'TR': 'Europe/Istanbul', 'ID': 'Asia/Jakarta', 'MY': 'Asia/Kuala_Lumpur',
                'PH': 'Asia/Manila', 'TH': 'Asia/Bangkok', 'VN': 'Asia/Ho_Chi_Minh',
                'KR': 'Asia/Seoul', 'NP': 'Asia/Kathmandu', 'LK': 'Asia/Colombo',
                'MM': 'Asia/Rangoon', 'KH': 'Asia/Phnom_Penh', 'SG': 'Asia/Singapore',
                'EG': 'Africa/Cairo', 'NG': 'Africa/Lagos', 'ZA': 'Africa/Johannesburg',
                'BR': 'America/Sao_Paulo', 'MX': 'America/Mexico_City', 'CA': 'America/Toronto',
                'AR': 'America/Argentina/Buenos_Aires', 'RU': 'Europe/Moscow',
                'IR': 'Asia/Tehran', 'IQ': 'Asia/Baghdad',
            }
            tz = COUNTRY_TZ.get(country_code.upper())
            if not tz:
                from ..models.core import Country, Timezone
                country = Country.objects.filter(code=country_code.upper()).first()
                if country and country.capital:
                    city_tz = Timezone.objects.filter(
                        regions__country=country
                    ).first()
                    tz = city_tz.name if city_tz else 'UTC'
                else:
                    tz = 'UTC'
            if tz:
                cache.set(cache_key, tz, CACHE_TTL)
            return tz
        except Exception as e:
            logger.error(f"get_timezone_for_country failed: {e}")
            return 'UTC'

    def get_country_info(self, country_code: str) -> Optional[Dict]:
        """Complete country info dict"""
        cache_key = f"geo_country_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.core import Country
            country = Country.objects.filter(code=country_code.upper()).first()
            if not country:
                return None
            info = {
                'code': country.code, 'name': country.name,
                'native_name': country.native_name,
                'flag_emoji': country.flag_emoji,
                'phone_code': country.phone_code,
                'continent': country.continent, 'region': country.region,
                'capital': country.capital, 'currency_code': country.currency_code,
                'is_eu': country.is_eu_member, 'requires_gdpr': country.requires_gdpr,
                'measurement': country.measurement_system,
                'driving_side': country.driving_side, 'tld': country.tld,
                'week_start': country.week_start,
                'recommended_language': self.get_language_for_country(country_code),
                'recommended_currency': self.get_currency_for_country(country_code),
                'timezone': self.get_timezone_for_country(country_code),
            }
            cache.set(cache_key, info, CACHE_TTL)
            return info
        except Exception as e:
            logger.error(f"get_country_info failed: {e}")
            return None

    def search_cities(self, query: str, country_code: str = '',
                      limit: int = 10) -> List[Dict]:
        """City autocomplete search"""
        try:
            from ..services.geo.CityService import CityService
            return CityService().autocomplete(query, country_code, limit)
        except Exception as e:
            logger.error(f"GeoService.search_cities failed: {e}")
            return []

    def get_all_countries(self) -> List[Dict]:
        """All active countries — cached"""
        cache_key = 'geo_all_countries'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.core import Country
            countries = list(Country.objects.filter(is_active=True).order_by('name').values(
                'code', 'name', 'native_name', 'flag_emoji',
                'phone_code', 'continent', 'currency_code', 'is_eu_member'
            ))
            cache.set(cache_key, countries, CACHE_TTL)
            return countries
        except Exception as e:
            logger.error(f"get_all_countries failed: {e}")
            return []

    def get_region_info(self, country_code: str) -> Optional[Dict]:
        """ContentRegion info for a country"""
        try:
            from ..models.region import ContentRegion
            region = ContentRegion.get_region_for_country(country_code)
            if not region:
                return None
            return {
                'name': region.name, 'slug': region.slug,
                'default_language': region.default_language.code if region.default_language else None,
                'default_currency': region.default_currency.code if region.default_currency else None,
                'requires_gdpr': region.requires_gdpr,
                'requires_age_verification': region.requires_age_verification,
                'min_age': region.min_age_requirement,
                'feature_flags': region.feature_flags or {},
            }
        except Exception as e:
            logger.error(f"get_region_info failed: {e}")
            return None

    def _country_requires_gdpr(self, country_code: str) -> bool:
        """EU GDPR requirement check"""
        EU_COUNTRIES = {
            'AT','BE','BG','CY','CZ','DE','DK','EE','ES','FI','FR','GR',
            'HR','HU','IE','IT','LT','LU','LV','MT','NL','PL','PT','RO',
            'SE','SI','SK', 'IS','LI','NO',  # EEA
        }
        return country_code.upper() in EU_COUNTRIES

    def _empty_geo(self) -> Dict:
        return {
            'country_code': '', 'country_name': '', 'city': '', 'region': '',
            'timezone': 'UTC', 'latitude': None, 'longitude': None,
            'recommended_language': 'en', 'recommended_currency': 'USD',
            'requires_gdpr': False, 'is_vpn': False, 'is_proxy': False,
        }
