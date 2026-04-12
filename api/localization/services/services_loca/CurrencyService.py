# services/services_loca/CurrencyService.py
"""
CurrencyService — High-level facade for currency operations.
Used in middleware, user preferences, offer display, earning calculations.
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, List
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)
CACHE_TTL = 3600


class CurrencyService:
    """
    High-level currency service — format, convert, get rates.
    CPAlead earning site কে সব currency needs এখান থেকে serve করা হয়।
    """

    def get_currency(self, currency_code: str):
        """Currency object return করে — cached"""
        cache_key = f"currency_obj_{currency_code}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from ..models.core import Currency
            obj = Currency.objects.filter(code=currency_code.upper(), is_active=True).first()
            if obj:
                cache.set(cache_key, obj, CACHE_TTL)
            return obj
        except Exception as e:
            logger.error(f"get_currency failed for {currency_code}: {e}")
            return None

    def get_default_currency(self):
        """Default currency return করে"""
        try:
            from ..models.core import Currency
            return Currency.objects.filter(is_default=True, is_active=True).first()
        except Exception as e:
            logger.error(f"get_default_currency failed: {e}")
            return None

    def get_all_active(self) -> List:
        """All active currencies — cached list"""
        cache_key = 'all_active_currencies'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.core import Currency
            currencies = list(Currency.objects.filter(is_active=True).order_by('code').values(
                'code', 'name', 'symbol', 'symbol_native', 'exchange_rate',
                'decimal_digits', 'symbol_position', 'is_default', 'is_crypto'
            ))
            cache.set(cache_key, currencies, CACHE_TTL)
            return currencies
        except Exception as e:
            logger.error(f"get_all_active currencies failed: {e}")
            return []

    def convert(self, amount, from_code: str, to_code: str) -> Optional[Dict]:
        """Amount convert করে — CPAlead earning conversion এখানে"""
        try:
            from ..services.currency.ExchangeRateService import ExchangeRateService
            return ExchangeRateService().convert(Decimal(str(amount)), from_code, to_code)
        except Exception as e:
            logger.error(f"CurrencyService.convert failed: {e}")
            return None

    def convert_for_display(self, amount, from_code: str, to_code: str,
                             language_code: str = 'en') -> Optional[str]:
        """
        Amount convert করে formatted string return করে।
        CPAlead offer display তে: "$10.00 USD" → "৳1,100 BDT"
        """
        try:
            result = self.convert(amount, from_code, to_code)
            if not result:
                return None
            from ..services.currency.CurrencyFormatService import CurrencyFormatService
            return CurrencyFormatService().format(
                result['converted'], to_code, language_code
            )
        except Exception as e:
            logger.error(f"convert_for_display failed: {e}")
            return None

    def format_amount(self, amount, currency_code: str, language_code: str = 'en') -> str:
        """Amount format করে locale-specific rules অনুযায়ী"""
        try:
            from ..services.currency.CurrencyFormatService import CurrencyFormatService
            return CurrencyFormatService().format(Decimal(str(amount)), currency_code, language_code)
        except Exception as e:
            logger.error(f"format_amount failed: {e}")
            currency = self.get_currency(currency_code)
            if currency:
                return currency.format_amount(Decimal(str(amount)))
            return f"{currency_code} {amount}"

    def get_exchange_rate(self, from_code: str, to_code: str) -> Optional[Decimal]:
        """Latest exchange rate পাওয়া"""
        try:
            from ..services.currency.ExchangeRateService import ExchangeRateService
            return ExchangeRateService().get_rate(from_code, to_code)
        except Exception as e:
            logger.error(f"get_exchange_rate failed: {e}")
            return None

    def get_currency_for_country(self, country_code: str) -> Optional[str]:
        """Country code দিয়ে primary currency code পাওয়া"""
        cache_key = f"country_currency_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.geo import CountryCurrency
            cc = CountryCurrency.objects.filter(
                country__code=country_code.upper(), is_primary=True
            ).select_related('currency').first()
            code = cc.currency.code if cc else None
            if not code:
                from ..models.core import Country
                country = Country.objects.filter(code=country_code.upper()).first()
                code = country.currency_code if country else 'USD'
            if code:
                cache.set(cache_key, code, CACHE_TTL * 24)
            return code
        except Exception as e:
            logger.error(f"get_currency_for_country failed: {e}")
            return 'USD'

    def update_rates_from_external(self, provider: str = 'exchangerate-api') -> Dict:
        """External API থেকে rates update করে"""
        try:
            from ..services.currency.CurrencyRateProvider import CurrencyRateProvider
            from ..models.core import Currency
            from ..models.currency import ExchangeRate
            from django.utils import timezone
            provider_obj = CurrencyRateProvider()
            result = provider_obj.fetch_rates('USD', provider)
            if not result.get('success'):
                return {'success': False, 'error': result.get('error')}
            updated = 0
            from_curr = Currency.objects.filter(code='USD').first()
            for code, rate in result.get('rates', {}).items():
                try:
                    to_curr = Currency.objects.filter(code=code).first()
                    if from_curr and to_curr:
                        ExchangeRate.objects.create(
                            from_currency=from_curr, to_currency=to_curr,
                            rate=Decimal(str(rate)), date=timezone.now().date(),
                            source=provider,
                        )
                        to_curr.exchange_rate = rate
                        to_curr.exchange_rate_updated_at = timezone.now()
                        to_curr.save(update_fields=['exchange_rate', 'exchange_rate_updated_at'])
                        updated += 1
                except Exception:
                    pass
            cache.delete('all_active_currencies')
            return {'success': True, 'updated': updated, 'provider': provider}
        except Exception as e:
            logger.error(f"update_rates_from_external failed: {e}")
            return {'success': False, 'error': str(e)}
