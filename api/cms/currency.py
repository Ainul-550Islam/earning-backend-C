# api/cms/currency.py
"""
Currency localization — multi-currency display for international users.
Converts USD amounts to user's local currency for display (not payment).
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Static fallback rates (updated via task)
FALLBACK_RATES = {
    'USD': 1.0, 'EUR': 0.92, 'GBP': 0.79, 'BDT': 110.0,
    'INR': 83.2, 'PKR': 278.0, 'NGN': 1600.0, 'BRL': 5.0,
    'MXN': 17.2, 'PHP': 56.0, 'VND': 24000.0, 'IDR': 15800.0,
    'CAD': 1.36, 'AUD': 1.53, 'NZD': 1.63, 'SGD': 1.34,
    'MYR': 4.7, 'THB': 35.0, 'KRW': 1330.0, 'JPY': 149.0,
    'CNY': 7.24, 'AED': 3.67, 'SAR': 3.75, 'EGP': 48.0,
    'ZAR': 18.7, 'GHS': 12.0, 'KES': 130.0, 'TZS': 2520.0,
    'UGX': 3760.0, 'RWF': 1280.0, 'ETB': 56.0, 'XOF': 603.0,
}

CURRENCY_SYMBOLS = {
    'USD': '$', 'EUR': '€', 'GBP': '£', 'BDT': '৳',
    'INR': '₹', 'PKR': '₨', 'NGN': '₦', 'BRL': 'R$',
    'MXN': '$', 'PHP': '₱', 'VND': '₫', 'IDR': 'Rp',
    'CAD': 'CA$', 'AUD': 'A$', 'NZD': 'NZ$', 'SGD': 'S$',
    'MYR': 'RM', 'THB': '฿', 'KRW': '₩', 'JPY': '¥',
    'CNY': '¥', 'AED': 'د.إ', 'SAR': '﷼', 'EGP': '£',
    'ZAR': 'R', 'GHS': 'GH₵', 'KES': 'KSh',
}

# Currency by country code
COUNTRY_CURRENCY = {
    'US': 'USD', 'GB': 'GBP', 'DE': 'EUR', 'FR': 'EUR',
    'BD': 'BDT', 'IN': 'INR', 'PK': 'PKR', 'NG': 'NGN',
    'BR': 'BRL', 'MX': 'MXN', 'PH': 'PHP', 'VN': 'VND',
    'ID': 'IDR', 'CA': 'CAD', 'AU': 'AUD', 'NZ': 'NZD',
    'SG': 'SGD', 'MY': 'MYR', 'TH': 'THB', 'KR': 'KRW',
    'JP': 'JPY', 'CN': 'CNY', 'AE': 'AED', 'SA': 'SAR',
    'EG': 'EGP', 'ZA': 'ZAR', 'GH': 'GHS', 'KE': 'KES',
    'ET': 'ETB', 'TZ': 'TZS', 'UG': 'UGX', 'RW': 'RWF',
}


class CurrencyService:
    """Currency conversion and localization service."""
    CACHE_KEY = 'cms:exchange_rates'
    CACHE_TTL = 3600  # 1 hour

    @classmethod
    def get_rates(cls) -> Dict[str, float]:
        """Get exchange rates (cached, updated hourly)."""
        cached = cache.get(cls.CACHE_KEY)
        if cached:
            return cached
        # Try to fetch live rates
        live = cls._fetch_live_rates()
        rates = live if live else FALLBACK_RATES
        cache.set(cls.CACHE_KEY, rates, cls.CACHE_TTL)
        return rates

    @classmethod
    def _fetch_live_rates(cls) -> Optional[Dict]:
        """Fetch live rates from free API (exchangerate-api.com)."""
        try:
            import urllib.request, json
            url = "https://open.er-api.com/v6/latest/USD"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read())
                if data.get('result') == 'success':
                    return data.get('rates', {})
        except Exception as e:
            logger.debug(f"[Currency] Live rate fetch failed: {e}")
        return None

    @classmethod
    def convert(cls, usd_amount: Decimal, to_currency: str) -> Decimal:
        """Convert USD to target currency."""
        to_currency = to_currency.upper()
        if to_currency == 'USD':
            return usd_amount
        rates = cls.get_rates()
        rate = rates.get(to_currency, 1.0)
        return (usd_amount * Decimal(str(rate))).quantize(Decimal('0.01'))

    @classmethod
    def format(cls, usd_amount: Decimal, currency: str = 'USD',
                country: str = '') -> str:
        """Format amount in local currency with symbol."""
        if country and not currency:
            currency = COUNTRY_CURRENCY.get(country.upper(), 'USD')
        amount = cls.convert(usd_amount, currency)
        symbol = CURRENCY_SYMBOLS.get(currency.upper(), '$')
        # Format with 2 decimal places for most, 0 for JPY/KRW etc.
        no_decimal = {'JPY', 'KRW', 'VND', 'IDR', 'NGN', 'UGX', 'TZS', 'RWF', 'GHS', 'KES', 'ETB', 'XOF'}
        if currency.upper() in no_decimal:
            return f"{symbol}{int(amount):,}"
        return f"{symbol}{float(amount):,.2f}"

    @classmethod
    def get_user_currency(cls, user) -> str:
        """Get user's preferred currency based on profile or country."""
        try:
            from api.cms.models_new.withdrawal import UserProfile
            profile = UserProfile.objects.get(user=user)
            if profile.preferred_currency and profile.preferred_currency != 'USD':
                return profile.preferred_currency
            if profile.country:
                return COUNTRY_CURRENCY.get(profile.country.upper(), 'USD')
        except Exception:
            pass
        return 'USD'

    @classmethod
    def get_supported_currencies(cls) -> List[Dict]:
        """List of all supported currencies with symbols."""
        return [
            {'code': code, 'symbol': CURRENCY_SYMBOLS.get(code, '$'),
             'rate': rate}
            for code, rate in FALLBACK_RATES.items()
        ]
