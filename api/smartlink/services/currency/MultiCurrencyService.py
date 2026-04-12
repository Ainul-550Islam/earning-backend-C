"""
SmartLink Multi-Currency Service
World #1: Track revenue in multiple currencies with live exchange rates.
CPAlead only supports USD. Ours supports 30+ currencies.
"""
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger('smartlink.currency')

# Fallback rates (updated by task every hour)
FALLBACK_RATES_TO_USD = {
    'USD': 1.0, 'EUR': 1.08, 'GBP': 1.27, 'JPY': 0.0067,
    'CAD': 0.74, 'AUD': 0.65, 'CHF': 1.12, 'CNY': 0.138,
    'INR': 0.012, 'BDT': 0.0091, 'PKR': 0.0036, 'NGN': 0.00065,
    'BRL': 0.20, 'MXN': 0.058, 'ZAR': 0.054, 'AED': 0.272,
    'SGD': 0.74, 'HKD': 0.128, 'KRW': 0.00075, 'TRY': 0.031,
    'PLN': 0.25, 'SEK': 0.095, 'NOK': 0.094, 'DKK': 0.145,
    'THB': 0.028, 'IDR': 0.000063, 'MYR': 0.213, 'PHP': 0.0174,
    'VND': 0.000040, 'EGP': 0.032,
}


class MultiCurrencyService:
    """Convert payouts between currencies for unified reporting."""

    CACHE_KEY    = 'currency:rates:usd'
    CACHE_TTL    = 3600  # 1 hour

    def to_usd(self, amount: float, from_currency: str) -> float:
        """Convert amount from any currency to USD."""
        if from_currency.upper() == 'USD':
            return round(amount, 4)
        rates = self._get_rates()
        rate  = rates.get(from_currency.upper(), 1.0)
        return round(amount * rate, 4)

    def from_usd(self, amount_usd: float, to_currency: str) -> float:
        """Convert USD amount to target currency."""
        if to_currency.upper() == 'USD':
            return round(amount_usd, 4)
        rates = self._get_rates()
        rate  = rates.get(to_currency.upper(), 1.0)
        if rate == 0:
            return 0.0
        return round(amount_usd / rate, 4)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert between any two currencies via USD."""
        usd = self.to_usd(amount, from_currency)
        return self.from_usd(usd, to_currency)

    def format_currency(self, amount: float, currency: str) -> str:
        """Format amount with currency symbol."""
        symbols = {
            'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
            'BDT': '৳', 'INR': '₹', 'CNY': '¥', 'KRW': '₩',
        }
        symbol = symbols.get(currency.upper(), currency.upper() + ' ')
        return f"{symbol}{amount:,.4f}"

    def get_supported_currencies(self) -> list:
        """Return list of all supported currency codes."""
        return sorted(FALLBACK_RATES_TO_USD.keys())

    def update_rates_from_api(self) -> bool:
        """
        Fetch live exchange rates from free API.
        Called by Celery task every hour.
        """
        try:
            import urllib.request
            import json
            # Free tier: exchangerate-api.com
            api_key = 'YOUR_API_KEY_HERE'
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get('result') == 'success':
                    rates = data.get('conversion_rates', {})
                    # Store as USD-base rates
                    usd_rates = {
                        code: 1.0 / rate if rate != 0 else 1.0
                        for code, rate in rates.items()
                    }
                    cache.set(self.CACHE_KEY, usd_rates, self.CACHE_TTL)
                    logger.info(f"Currency rates updated: {len(usd_rates)} currencies")
                    return True
        except Exception as e:
            logger.warning(f"Currency rate update failed: {e}")
        return False

    def _get_rates(self) -> dict:
        """Get current rates (cache or fallback)."""
        cached = cache.get(self.CACHE_KEY)
        if cached:
            return cached
        return FALLBACK_RATES_TO_USD
