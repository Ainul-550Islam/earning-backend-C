# api/offer_inventory/finance_payment/currency_converter_v2.py
"""
Currency Converter v2 — Enhanced with live rates, caching, fallback.
All conversions use Decimal — zero float operations.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

P4 = Decimal('0.0001')

FALLBACK_RATES = {
    ('USD', 'BDT'): Decimal('110.00'),
    ('EUR', 'BDT'): Decimal('120.00'),
    ('GBP', 'BDT'): Decimal('140.00'),
    ('INR', 'BDT'): Decimal('1.32'),
    ('BDT', 'USD'): Decimal('0.0091'),
    ('BDT', 'EUR'): Decimal('0.0083'),
    ('BDT', 'GBP'): Decimal('0.0071'),
    ('BDT', 'INR'): Decimal('0.758'),
    ('USD', 'EUR'): Decimal('0.92'),
    ('USD', 'GBP'): Decimal('0.79'),
    ('USD', 'INR'): Decimal('83.5'),
}


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or '0'))
    except (InvalidOperation, TypeError):
        return Decimal('0')


class CurrencyConverterV2:
    """
    Production-grade currency converter.
    Priority: DB cache → Redis cache → External API → Hardcoded fallback
    """

    CACHE_TTL = 3600  # 1 hour

    @classmethod
    def convert(cls, amount: Decimal, from_currency: str,
                 to_currency: str) -> Decimal:
        """Convert amount between currencies. Returns Decimal."""
        from_c = from_currency.upper().strip()
        to_c   = to_currency.upper().strip()

        if from_c == to_c:
            return _d(amount).quantize(P4, rounding=ROUND_HALF_UP)

        rate   = cls.get_rate(from_c, to_c)
        result = (_d(amount) * rate).quantize(P4, rounding=ROUND_HALF_UP)
        return result

    @classmethod
    def get_rate(cls, from_currency: str, to_currency: str) -> Decimal:
        """Get exchange rate. Falls back gracefully."""
        from_c = from_currency.upper()
        to_c   = to_currency.upper()

        # 1. Redis cache
        cache_key = f'fx:{from_c}:{to_c}'
        cached    = cache.get(cache_key)
        if cached:
            return _d(cached)

        # 2. DB (CurrencyRate model)
        rate = cls._from_db(from_c, to_c)
        if rate:
            cache.set(cache_key, str(rate), cls.CACHE_TTL)
            return rate

        # 3. External API
        rate = cls._from_api(from_c, to_c)
        if rate and rate > 0:
            cache.set(cache_key, str(rate), cls.CACHE_TTL)
            cls._save_to_db(from_c, to_c, rate)
            return rate

        # 4. Hardcoded fallback
        fallback = FALLBACK_RATES.get((from_c, to_c))
        if fallback:
            logger.warning(f'Using fallback rate {from_c}→{to_c}: {fallback}')
            return fallback

        # 5. Reverse fallback
        reverse = FALLBACK_RATES.get((to_c, from_c))
        if reverse and reverse > 0:
            rate = (Decimal('1') / reverse).quantize(P4, rounding=ROUND_HALF_UP)
            logger.warning(f'Using reverse fallback rate {from_c}→{to_c}: {rate}')
            return rate

        logger.error(f'No rate found {from_c}→{to_c}. Using 1.')
        return Decimal('1')

    @staticmethod
    def _from_db(from_c: str, to_c: str):
        try:
            from api.offer_inventory.models import CurrencyRate
            obj = CurrencyRate.objects.get(from_currency=from_c, to_currency=to_c)
            return _d(obj.rate)
        except Exception:
            return None

    @staticmethod
    def _from_api(from_c: str, to_c: str):
        try:
            import requests
            resp = requests.get(
                f'https://api.exchangerate-api.com/v4/latest/{from_c}',
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                raw  = data.get('rates', {}).get(to_c)
                if raw:
                    return _d(str(raw)).quantize(P4, rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.warning(f'Currency API error {from_c}→{to_c}: {e}')
        return None

    @staticmethod
    def _save_to_db(from_c: str, to_c: str, rate: Decimal):
        try:
            from api.offer_inventory.models import CurrencyRate
            CurrencyRate.objects.update_or_create(
                from_currency=from_c, to_currency=to_c,
                defaults={'rate': rate, 'source': 'exchangerate-api',
                          'fetched_at': timezone.now()}
            )
        except Exception as e:
            logger.debug(f'CurrencyRate DB save error: {e}')

    @classmethod
    def get_supported_currencies(cls) -> list:
        return ['BDT', 'USD', 'EUR', 'GBP', 'INR', 'SGD', 'AED', 'SAR']

    @classmethod
    def format_amount(cls, amount: Decimal, currency: str) -> str:
        symbols = {
            'BDT': '৳', 'USD': '$', 'EUR': '€',
            'GBP': '£', 'INR': '₹', 'SGD': 'S$',
        }
        sym = symbols.get(currency.upper(), currency)
        return f'{sym}{float(amount):,.2f}'

    @classmethod
    def bulk_convert(cls, amounts: list, from_currency: str,
                      to_currency: str) -> list:
        """Convert a list of amounts at once (one rate fetch)."""
        rate = cls.get_rate(from_currency.upper(), to_currency.upper())
        return [
            (_d(a) * rate).quantize(P4, rounding=ROUND_HALF_UP)
            for a in amounts
        ]

    @classmethod
    def refresh_rates(cls) -> dict:
        """Force refresh all common rates from API."""
        pairs = [
            ('USD', 'BDT'), ('EUR', 'BDT'), ('GBP', 'BDT'),
            ('INR', 'BDT'), ('USD', 'EUR'), ('USD', 'GBP'),
        ]
        refreshed = {}
        for from_c, to_c in pairs:
            rate = cls._from_api(from_c, to_c)
            if rate:
                cls._save_to_db(from_c, to_c, rate)
                cache.set(f'fx:{from_c}:{to_c}', str(rate), cls.CACHE_TTL)
                refreshed[f'{from_c}_{to_c}'] = float(rate)
        return refreshed
