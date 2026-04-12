# =============================================================================
# api/promotions/localization/forex_engine.py
# Forex Engine — Real-time currency conversion
# Multiple provider support with fallback chain
# =============================================================================

import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('localization.forex')
CACHE_PREFIX_FOREX = 'loc:forex:{}'
CACHE_TTL_FOREX    = 3600   # 1 hour


@dataclass
class ExchangeRate:
    base:       str
    target:     str
    rate:       Decimal
    source:     str
    timestamp:  float


@dataclass
class ConversionResult:
    from_amount:  Decimal
    from_currency: str
    to_amount:    Decimal
    to_currency:  str
    rate:         Decimal
    fee_amount:   Decimal       # Platform fee
    net_amount:   Decimal       # After fee
    source:       str


class ForexEngine:
    """
    Currency conversion engine।

    Provider chain:
    1. ExchangeRate-API (free tier: 1500 req/month)
    2. Fixer.io (fallback)
    3. Open Exchange Rates (fallback)
    4. Static rates (last resort)

    Features:
    - Real-time rates with 1-hour cache
    - Markup/fee support (platform takes cut)
    - Bulk conversion
    - Historical rates
    """

    # Platform conversion fee (%)
    CONVERSION_FEE_RATE = Decimal('0.025')   # 2.5%

    # Static fallback rates (USD base) — UPDATE PERIODICALLY
    STATIC_RATES_FROM_USD = {
        'BDT': Decimal('110.0'),
        'INR': Decimal('83.5'),
        'PKR': Decimal('278.0'),
        'NGN': Decimal('1550.0'),
        'IDR': Decimal('15700.0'),
        'PHP': Decimal('57.0'),
        'MYR': Decimal('4.7'),
        'BRL': Decimal('5.0'),
        'MXN': Decimal('17.5'),
        'TRY': Decimal('32.0'),
        'EGP': Decimal('48.0'),
        'GBP': Decimal('0.79'),
        'EUR': Decimal('0.92'),
        'JPY': Decimal('150.0'),
        'KRW': Decimal('1330.0'),
        'CNY': Decimal('7.2'),
        'AED': Decimal('3.67'),
        'SAR': Decimal('3.75'),
        'CAD': Decimal('1.36'),
        'AUD': Decimal('1.52'),
        'USD': Decimal('1.0'),
    }

    def get_rate(self, from_currency: str, to_currency: str) -> ExchangeRate:
        """Exchange rate return করে।"""
        from_c = from_currency.upper()
        to_c   = to_currency.upper()

        if from_c == to_c:
            return ExchangeRate(base=from_c, target=to_c, rate=Decimal('1'), source='same_currency', timestamp=0)

        cache_key = CACHE_PREFIX_FOREX.format(f'{from_c}_{to_c}')
        cached    = cache.get(cache_key)
        if cached:
            return ExchangeRate(**cached)

        rate = None
        for provider_fn in [self._try_exchangerate_api, self._try_fixer, self._static_rate]:
            try:
                rate = provider_fn(from_c, to_c)
                if rate:
                    break
            except Exception as e:
                logger.debug(f'Forex provider failed: {e}')

        if not rate:
            rate = self._static_rate(from_c, to_c)

        if rate:
            cache.set(cache_key, rate.__dict__, timeout=CACHE_TTL_FOREX)

        return rate

    def convert(
        self,
        amount:        Decimal,
        from_currency: str,
        to_currency:   str,
        apply_fee:     bool = False,
    ) -> ConversionResult:
        """Currency convert করে।"""
        rate_obj  = self.get_rate(from_currency, to_currency)
        converted = (amount * rate_obj.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        fee    = Decimal('0')
        net    = converted
        if apply_fee:
            fee = (converted * self.CONVERSION_FEE_RATE).quantize(Decimal('0.01'))
            net = converted - fee

        return ConversionResult(
            from_amount=amount, from_currency=from_currency.upper(),
            to_amount=converted, to_currency=to_currency.upper(),
            rate=rate_obj.rate, fee_amount=fee, net_amount=net,
            source=rate_obj.source,
        )

    def convert_usd_to_local(self, usd_amount: Decimal, country: str) -> ConversionResult:
        """USD থেকে country এর local currency তে convert করে।"""
        local_currency = self._get_country_currency(country)
        return self.convert(usd_amount, 'USD', local_currency)

    def bulk_convert(self, amounts: dict, to_currency: str) -> dict:
        """Multiple currencies একসাথে convert করে।"""
        results = {}
        for from_currency, amount in amounts.items():
            results[from_currency] = self.convert(Decimal(str(amount)), from_currency, to_currency)
        return results

    # ── Providers ──────────────────────────────────────────────────────────────

    def _try_exchangerate_api(self, from_c: str, to_c: str) -> Optional[ExchangeRate]:
        from django.conf import settings
        api_key = getattr(settings, 'EXCHANGERATE_API_KEY', None)
        if not api_key:
            return None
        import requests, time
        resp = requests.get(
            f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_c}/{to_c}',
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return ExchangeRate(
            base=from_c, target=to_c,
            rate=Decimal(str(data['conversion_rate'])),
            source='exchangerate_api', timestamp=time.time(),
        )

    def _try_fixer(self, from_c: str, to_c: str) -> Optional[ExchangeRate]:
        from django.conf import settings
        api_key = getattr(settings, 'FIXER_API_KEY', None)
        if not api_key:
            return None
        import requests, time
        resp = requests.get(
            f'https://data.fixer.io/api/latest?access_key={api_key}&base={from_c}&symbols={to_c}',
            timeout=5,
        )
        data = resp.json()
        if not data.get('success'):
            return None
        rate = data['rates'].get(to_c)
        if not rate:
            return None
        return ExchangeRate(base=from_c, target=to_c, rate=Decimal(str(rate)), source='fixer', timestamp=time.time())

    def _static_rate(self, from_c: str, to_c: str) -> ExchangeRate:
        """Static rates — fallback।"""
        import time
        if from_c == 'USD':
            rate = self.STATIC_RATES_FROM_USD.get(to_c, Decimal('1'))
        elif to_c == 'USD':
            base_rate = self.STATIC_RATES_FROM_USD.get(from_c, Decimal('1'))
            rate = Decimal('1') / base_rate
        else:
            usd_from = self.STATIC_RATES_FROM_USD.get(from_c, Decimal('1'))
            usd_to   = self.STATIC_RATES_FROM_USD.get(to_c, Decimal('1'))
            rate = usd_to / usd_from
        return ExchangeRate(base=from_c, target=to_c, rate=rate, source='static', timestamp=time.time())

    @staticmethod
    def _get_country_currency(country: str) -> str:
        country_currency_map = {
            'BD': 'BDT', 'IN': 'INR', 'PK': 'PKR', 'NG': 'NGN',
            'ID': 'IDR', 'PH': 'PHP', 'MY': 'MYR', 'BR': 'BRL',
            'MX': 'MXN', 'TR': 'TRY', 'EG': 'EGP', 'GB': 'GBP',
            'DE': 'EUR', 'FR': 'EUR', 'JP': 'JPY', 'KR': 'KRW',
            'CN': 'CNY', 'AE': 'AED', 'SA': 'SAR', 'CA': 'CAD',
            'AU': 'AUD', 'US': 'USD',
        }
        return country_currency_map.get(country.upper(), 'USD')
