# api/payment_gateways/utils/CurrencyConverter.py
# Real-time currency conversion utility

from decimal import Decimal, ROUND_HALF_UP
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


class CurrencyConverter:
    """
    Currency conversion using cached exchange rates.
    Falls back to DB rates if cache is empty.
    Rates updated hourly by exchange_rate_tasks.py
    """

    def convert(self, amount: Decimal, from_currency: str,
                to_currency: str, precision: int = 2) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount:        Amount to convert
            from_currency: Source currency code (e.g. 'USD')
            to_currency:   Target currency code (e.g. 'BDT')
            precision:     Decimal places in result

        Returns:
            Decimal: Converted amount

        Example:
            converter = CurrencyConverter()
            bdt = converter.convert(Decimal('100'), 'USD', 'BDT')  # → 11050.00
        """
        if from_currency == to_currency:
            return amount.quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP)

        from_rate = self._get_rate(from_currency)
        to_rate   = self._get_rate(to_currency)

        if not from_rate or not to_rate:
            logger.warning(f'Could not convert {from_currency}→{to_currency}: rate not found')
            return amount

        # Convert via USD as base
        usd_amount    = amount / from_rate
        target_amount = usd_amount * to_rate

        return target_amount.quantize(
            Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP
        )

    def _get_rate(self, currency: str) -> Decimal:
        """Get exchange rate (vs USD base) from cache or DB."""
        # Try cache first
        cached = cache.get(f'exchange_rate:USD:{currency}')
        if cached:
            return Decimal(str(cached))

        # Try DB
        try:
            from api.payment_gateways.models.core import Currency
            c = Currency.objects.get(code=currency.upper(), is_active=True)
            rate = c.exchange_rate
            # Cache it
            cache.set(f'exchange_rate:USD:{currency}', float(rate), CACHE_TTL)
            return rate
        except Exception:
            logger.warning(f'Exchange rate not found for {currency}')
            return None

    def get_all_rates(self) -> dict:
        """Get all available exchange rates (vs USD)."""
        try:
            from api.payment_gateways.models.core import Currency
            rates = {}
            for c in Currency.objects.filter(is_active=True):
                rates[c.code] = float(c.exchange_rate)
                cache.set(f'exchange_rate:USD:{c.code}', float(c.exchange_rate), CACHE_TTL)
            return rates
        except Exception:
            return {}

    def format_amount(self, amount: Decimal, currency: str) -> str:
        """Format amount with currency symbol."""
        SYMBOLS = {
            'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£',
            'AUD': 'A$', 'CAD': 'C$', 'SGD': 'S$',
            'BTC': '₿', 'ETH': 'Ξ', 'USDT': '₮',
        }
        symbol = SYMBOLS.get(currency.upper(), currency + ' ')
        return f'{symbol}{float(amount):,.2f}'

    def usd_to_bdt(self, usd: Decimal) -> Decimal:
        """Shortcut: USD to BDT."""
        return self.convert(usd, 'USD', 'BDT')

    def bdt_to_usd(self, bdt: Decimal) -> Decimal:
        """Shortcut: BDT to USD."""
        return self.convert(bdt, 'BDT', 'USD')
