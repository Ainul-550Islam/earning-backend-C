# services/currency/ExchangeRateService.py
"""Exchange rate service — lookup, convert, cache"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
RATE_CACHE_TTL = 3600  # 1h


class ExchangeRateService:
    """
    Currency exchange rate service.
    Priority: DB latest rate → Currency.exchange_rate field → 1.0 fallback
    """

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """USD→BDT exchange rate পাওয়া — cached"""
        if from_currency == to_currency:
            return Decimal('1')

        cache_key = f"exrate_{from_currency}_{to_currency}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        try:
            # 1. Latest ExchangeRate record
            from ...models.currency import ExchangeRate
            latest = ExchangeRate.objects.filter(
                from_currency__code=from_currency,
                to_currency__code=to_currency,
            ).order_by('-date', '-fetched_at').first()

            if latest:
                rate = latest.rate
                cache.set(cache_key, str(rate), RATE_CACHE_TTL)
                return rate

            # 2. Triangulate via USD (if not direct pair)
            if from_currency != 'USD' and to_currency != 'USD':
                from_usd = self.get_rate('USD', from_currency)
                to_usd = self.get_rate('USD', to_currency)
                if from_usd and to_usd and from_usd != 0:
                    rate = to_usd / from_usd
                    cache.set(cache_key, str(rate), RATE_CACHE_TTL)
                    return rate

            # 3. Currency model exchange_rate field (vs USD)
            from ...models.core import Currency
            if from_currency == 'USD':
                curr = Currency.objects.filter(code=to_currency).first()
                if curr and curr.exchange_rate:
                    rate = Decimal(str(curr.exchange_rate))
                    cache.set(cache_key, str(rate), RATE_CACHE_TTL)
                    return rate
            elif to_currency == 'USD':
                curr = Currency.objects.filter(code=from_currency).first()
                if curr and curr.exchange_rate and curr.exchange_rate != 0:
                    rate = Decimal('1') / Decimal(str(curr.exchange_rate))
                    cache.set(cache_key, str(rate), RATE_CACHE_TTL)
                    return rate

        except Exception as e:
            logger.error(f"get_rate {from_currency}→{to_currency} failed: {e}")

        return None

    def convert(self, amount, from_currency: str, to_currency: str) -> Optional[Dict]:
        """Amount convert করে"""
        try:
            amount_dec = Decimal(str(amount))
            if from_currency == to_currency:
                return {
                    'amount': amount_dec,
                    'converted': amount_dec,
                    'rate': Decimal('1'),
                    'from': from_currency,
                    'to': to_currency,
                }
            rate = self.get_rate(from_currency, to_currency)
            if rate is None:
                logger.warning(f"No rate for {from_currency}→{to_currency}")
                return None
            converted = (amount_dec * rate).quantize(Decimal('0.01'))
            return {
                'amount': amount_dec,
                'converted': converted,
                'rate': rate,
                'from': from_currency,
                'to': to_currency,
            }
        except (InvalidOperation, Exception) as e:
            logger.error(f"convert failed: {e}")
            return None

    def get_all_rates_from_usd(self) -> Dict:
        """All rates from USD — for currency selector display"""
        cache_key = 'all_rates_from_usd'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ...models.core import Currency
            rates = {}
            for curr in Currency.objects.filter(is_active=True, exchange_rate__isnull=False):
                rates[curr.code] = float(curr.exchange_rate)
            cache.set(cache_key, rates, RATE_CACHE_TTL)
            return rates
        except Exception as e:
            logger.error(f"get_all_rates_from_usd failed: {e}")
            return {}

    def fetch_and_save_rates(self, provider: str = 'exchangerate-api') -> Dict:
        """External API থেকে rates fetch করে DB-তে save করে"""
        try:
            from .CurrencyRateProvider import CurrencyRateProvider
            from ...models.core import Currency
            from ...models.currency import ExchangeRate

            provider_service = CurrencyRateProvider()
            result = provider_service.fetch_rates('USD', provider)

            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'Fetch failed')}

            usd = Currency.objects.filter(code='USD').first()
            if not usd:
                return {'success': False, 'error': 'USD currency not found in DB'}

            saved = 0
            today = timezone.now().date()
            for code, rate in result.get('rates', {}).items():
                try:
                    to_curr = Currency.objects.filter(code=code).first()
                    if not to_curr:
                        continue
                    # Update Currency model's cached rate
                    to_curr.exchange_rate = rate
                    to_curr.exchange_rate_updated_at = timezone.now()
                    to_curr.save(update_fields=['exchange_rate', 'exchange_rate_updated_at'])
                    # Save historical record
                    ExchangeRate.objects.get_or_create(
                        from_currency=usd,
                        to_currency=to_curr,
                        date=today,
                        defaults={'rate': Decimal(str(rate)), 'source': provider},
                    )
                    saved += 1
                except Exception:
                    pass

            # Clear rate cache
            cache.delete('all_rates_from_usd')
            logger.info(f"Saved {saved} exchange rates from {provider}")
            return {'success': True, 'saved': saved, 'provider': provider}

        except Exception as e:
            logger.error(f"fetch_and_save_rates failed: {e}")
            return {'success': False, 'error': str(e)}
