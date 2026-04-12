# utils/cache_warming.py
"""Cache pre-warming strategy for World #1 localization system"""
import logging
from typing import List, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

WARM_TTL = 86400  # 24h for stable data


def warm_all(languages: List[str] = None, namespaces: List[str] = None) -> dict:
    """All caches warm করে — startup time-এ call করো"""
    results = {}
    results['languages'] = warm_languages()
    results['countries'] = warm_countries()
    results['currencies'] = warm_currencies()
    if languages:
        for lang_code in languages:
            ns_list = namespaces or ['global']
            for ns in ns_list:
                key = f"translation_pack_{lang_code}_{ns}"
                result = warm_translations(lang_code, ns)
                results[key] = result
    logger.info(f"Cache warming complete: {results}")
    return results


def warm_languages() -> bool:
    """Languages list pre-warm করে"""
    try:
        from ..models.core import Language
        cached = cache.get('languages_list_v1')
        if cached:
            return True
        langs = list(Language.objects.filter(is_active=True).order_by('-is_default', 'name').values(
            'code', 'name', 'name_native', 'is_rtl', 'flag_emoji',
            'locale_code', 'text_direction', 'bcp47_code', 'coverage_percent',
        ))
        cache.set('languages_list_v1', langs, WARM_TTL)
        logger.debug(f"Warmed languages cache: {len(langs)} languages")
        return True
    except Exception as e:
        logger.error(f"warm_languages failed: {e}")
        return False


def warm_countries() -> bool:
    """Countries list pre-warm করে"""
    try:
        from ..models.core import Country
        cached = cache.get('countries_list_v1')
        if cached:
            return True
        countries = list(Country.objects.filter(is_active=True).order_by('name').values(
            'code', 'name', 'native_name', 'phone_code', 'flag_emoji',
            'continent', 'currency_code', 'is_eu_member', 'requires_gdpr',
        ))
        cache.set('countries_list_v1', countries, WARM_TTL)
        logger.debug(f"Warmed countries cache: {len(countries)} countries")
        return True
    except Exception as e:
        logger.error(f"warm_countries failed: {e}")
        return False


def warm_currencies() -> bool:
    """Currencies list pre-warm করে"""
    try:
        from ..models.core import Currency
        cached = cache.get('currencies_list_v1')
        if cached:
            return True
        currencies = list(Currency.objects.filter(is_active=True).order_by('code').values(
            'code', 'name', 'symbol', 'symbol_native', 'exchange_rate',
            'decimal_digits', 'symbol_position', 'is_default', 'is_crypto',
        ))
        cache.set('currencies_list_v1', currencies, WARM_TTL)
        logger.debug(f"Warmed currencies cache: {len(currencies)} currencies")
        return True
    except Exception as e:
        logger.error(f"warm_currencies failed: {e}")
        return False


def warm_translations(language_code: str, namespace: str = 'global') -> bool:
    """Language translation pack pre-warm করে"""
    try:
        from ..services.translation.LanguagePackBuilder import LanguagePackBuilder
        cache_key = f"translation_pack_{language_code}_{namespace}"
        if cache.get(cache_key):
            return True
        result = LanguagePackBuilder().build(language_code, namespace)
        if result['success']:
            cache.set(cache_key, result['pack'], WARM_TTL)
            logger.debug(f"Warmed translations: {language_code}/{namespace} ({result['count']} keys)")
            return True
        return False
    except Exception as e:
        logger.error(f"warm_translations failed for {language_code}: {e}")
        return False


def warm_exchange_rates() -> bool:
    """Current exchange rates pre-warm করে"""
    try:
        from ..models.core import Currency
        rates = {}
        for curr in Currency.objects.filter(is_active=True).values('code', 'exchange_rate'):
            rates[curr['code']] = float(curr['exchange_rate'])
            cache.set(f"exchange_rate_USD_{curr['code']}", curr['exchange_rate'], 3600)
        logger.debug(f"Warmed {len(rates)} exchange rates")
        return True
    except Exception as e:
        logger.error(f"warm_exchange_rates failed: {e}")
        return False


def get_cache_stats() -> dict:
    """Cache statistics"""
    try:
        stats = {
            'languages_cached': bool(cache.get('languages_list_v1')),
            'countries_cached': bool(cache.get('countries_list_v1')),
            'currencies_cached': bool(cache.get('currencies_list_v1')),
        }
        return stats
    except Exception:
        return {'error': 'cache unavailable'}
