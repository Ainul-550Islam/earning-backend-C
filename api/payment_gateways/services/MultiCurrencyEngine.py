# api/payment_gateways/services/MultiCurrencyEngine.py
# Multi-currency payment processing engine
# Auto-converts amounts between currencies using live rates

from decimal import Decimal, ROUND_HALF_UP
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MultiCurrencyEngine:
    """
    Handles multi-currency payment processing.

    Features:
        - Auto-detect user's preferred currency
        - Convert payout amounts to user's local currency
        - Real-time rate updates (cached 1 hour)
        - BD Taka as base for BD gateways
        - USD as base for international gateways
        - Crypto price feeds for USDT/BTC/ETH

    World systems use:
        - CPAlead: USD base, converts to 200+ currencies
        - MaxBounty: USD base weekly payments
        - ClickDealer: EUR/USD based
    """

    BASE_CURRENCY    = 'USD'
    CACHE_TTL        = 3600  # 1 hour

    BD_GATEWAYS      = ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay']
    CRYPTO_CURRENCIES= ['BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'BCH']

    def convert(self, amount: Decimal, from_currency: str,
                to_currency: str) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount:        Amount to convert
            from_currency: Source currency (e.g. 'BDT')
            to_currency:   Target currency (e.g. 'USD')

        Returns:
            Decimal: Converted amount (rounded to 2 decimal places for fiat)
        """
        if from_currency == to_currency:
            return amount

        # Get rates
        from_rate = self._get_usd_rate(from_currency)
        to_rate   = self._get_usd_rate(to_currency)

        if not from_rate or not to_rate:
            logger.warning(f'Cannot convert {from_currency}→{to_currency}: rate missing')
            return amount

        # Convert via USD as pivot
        usd_amount    = amount / Decimal(str(from_rate))
        result_amount = usd_amount * Decimal(str(to_rate))

        # Precision
        precision = '0.00000001' if to_currency in self.CRYPTO_CURRENCIES else '0.01'
        return result_amount.quantize(Decimal(precision), rounding=ROUND_HALF_UP)

    def get_payout_in_user_currency(self, usd_amount: Decimal, user) -> dict:
        """
        Get payout amount in publisher's preferred currency.
        Returns both USD and local currency amounts.

        Used when showing earnings to BD publishers (show in BDT).
        """
        user_currency = self._get_user_currency(user)

        if user_currency == 'USD':
            return {
                'amount':    float(usd_amount),
                'currency':  'USD',
                'usd_amount':float(usd_amount),
                'rate':      1.0,
            }

        rate            = self._get_usd_rate(user_currency)
        converted       = usd_amount * Decimal(str(rate)) if rate else usd_amount
        converted       = converted.quantize(Decimal('0.01'))

        return {
            'amount':    float(converted),
            'currency':  user_currency,
            'usd_amount':float(usd_amount),
            'rate':      rate or 1.0,
        }

    def get_gateway_currency(self, gateway: str) -> str:
        """Get the native currency for a gateway."""
        if gateway in self.BD_GATEWAYS:
            return 'BDT'
        if gateway == 'ach':
            return 'USD'
        if gateway == 'crypto':
            return 'USDT'
        return 'USD'

    def normalize_to_usd(self, amount: Decimal, gateway: str) -> Decimal:
        """
        Normalize a gateway-specific amount to USD.
        Used for unified reporting across gateways.
        """
        native_currency = self.get_gateway_currency(gateway)
        return self.convert(amount, native_currency, 'USD')

    def get_all_rates(self) -> dict:
        """Get all exchange rates relative to USD."""
        cache_key = 'all_exchange_rates'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        rates = {}
        try:
            from api.payment_gateways.models.core import Currency
            for c in Currency.objects.filter(is_active=True):
                rates[c.code] = float(c.exchange_rate)
        except Exception:
            # Fallback hardcoded rates
            rates = {
                'USD': 1.0,
                'BDT': 110.5,
                'EUR': 0.92,
                'GBP': 0.79,
                'AUD': 1.53,
                'CAD': 1.36,
                'SGD': 1.34,
                'JPY': 149.5,
                'INR': 83.1,
                'PKR': 279.0,
                'USDT': 1.0,
                'BTC': 0.0000155,  # Approximate
                'ETH': 0.00032,
            }

        cache.set(cache_key, rates, self.CACHE_TTL)
        return rates

    def format_amount(self, amount: Decimal, currency: str) -> str:
        """Format amount with currency symbol for display."""
        SYMBOLS = {
            'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£',
            'AUD': 'A$', 'CAD': 'C$', 'SGD': 'S$', 'JPY': '¥',
            'INR': '₹', 'USDT': '₮', 'BTC': '₿', 'ETH': 'Ξ',
        }
        symbol    = SYMBOLS.get(currency.upper(), currency + ' ')
        precision = 8 if currency in self.CRYPTO_CURRENCIES else 2
        return f'{symbol}{float(amount):,.{precision}f}'

    def get_supported_currencies(self) -> list:
        """Get list of all supported currencies."""
        rates = self.get_all_rates()
        return list(rates.keys())

    def _get_usd_rate(self, currency: str) -> float:
        """Get exchange rate for currency (relative to USD=1)."""
        if currency == 'USD':
            return 1.0

        cache_key = f'rate:USD:{currency}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        rates = self.get_all_rates()
        rate  = rates.get(currency.upper())

        if rate:
            cache.set(cache_key, rate, self.CACHE_TTL)
        return rate

    def _get_user_currency(self, user) -> str:
        """Determine user's preferred currency."""
        # Try publisher profile
        try:
            profile = user.publisher_profile
            if profile.payment_currency:
                return profile.payment_currency
        except Exception:
            pass

        # Try country detection
        try:
            country = getattr(user, 'country', '')
            if country == 'BD':
                return 'BDT'
        except Exception:
            pass

        return 'USD'  # Default
