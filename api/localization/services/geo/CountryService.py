# services/geo/CountryService.py
"""Country data service"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CountryService:
    """Country information service"""

    def get_country_info(self, country_code: str) -> Optional[Dict]:
        try:
            from ..models.core import Country
            from ..models.geo import CountryLanguage, CountryCurrency
            from ..models.settings import AddressFormat
            from django.core.cache import cache
            cache_key = f"country_info_{country_code}"
            cached = cache.get(cache_key)
            if cached:
                return cached
            country = Country.objects.filter(code=country_code.upper()).first()
            if not country:
                return None
            official_lang = CountryLanguage.objects.filter(
                country=country, is_official=True
            ).order_by('-speaker_percentage').first()
            primary_currency = CountryCurrency.objects.filter(
                country=country, is_primary=True
            ).first()
            result = {
                'code': country.code,
                'name': country.name,
                'native_name': country.native_name,
                'flag_emoji': country.flag_emoji,
                'phone_code': country.phone_code,
                'official_language': official_lang.language.code if official_lang else None,
                'primary_currency': primary_currency.currency.code if primary_currency else country.currency_code,
                'continent': country.continent,
                'region': country.region,
                'is_eu': country.is_eu_member,
                'requires_gdpr': country.requires_gdpr,
                'driving_side': country.driving_side,
                'tld': country.tld,
                'week_start': country.week_start,
                'measurement': country.measurement_system,
            }
            cache.set(cache_key, result, 86400)
            return result
        except Exception as e:
            logger.error(f"Country info failed for {country_code}: {e}")
            return None

    def get_countries_by_continent(self, continent: str) -> List[Dict]:
        try:
            from ..models.core import Country
            countries = Country.objects.filter(continent=continent, is_active=True)
            return list(countries.values('code', 'name', 'flag_emoji', 'phone_code'))
        except Exception as e:
            logger.error(f"Countries by continent failed: {e}")
            return []
