# api/wallet/currency_converter.py
"""
Live currency conversion service.
Sources: ExchangeRate-API, OpenExchangeRates, NowPayments (for crypto).
Caches rates in Redis for 1 hour.

Usage:
    from .currency_converter import CurrencyConverter
    bdt_amount = CurrencyConverter.to_bdt(10, "USD")  # 10 USD → BDT
    usd_amount = CurrencyConverter.from_bdt(1000, "USD")  # 1000 BDT → USD
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger("wallet.currency")

# Fallback rates (updated manually if API fails)
FALLBACK_RATES_TO_BDT = {
    "USD":  Decimal("110.00"),
    "EUR":  Decimal("120.00"),
    "GBP":  Decimal("140.00"),
    "AUD":  Decimal("72.00"),
    "CAD":  Decimal("81.00"),
    "SGD":  Decimal("82.00"),
    "INR":  Decimal("1.32"),
    "SAR":  Decimal("29.30"),
    "AED":  Decimal("30.00"),
    "CNY":  Decimal("15.20"),
    "JPY":  Decimal("0.74"),
    "BDT":  Decimal("1.00"),
    "USDT": Decimal("110.00"),
    "BTC":  Decimal("11000000.00"),
    "ETH":  Decimal("370000.00"),
}

CACHE_TTL = 3600  # 1 hour


class CurrencyConverter:
    """BDT-centric currency converter with live rate fetching."""

    @staticmethod
    def get_rate_to_bdt(from_currency: str) -> Decimal:
        """Get 1 unit of from_currency in BDT."""
        from_currency = from_currency.upper()
        if from_currency == "BDT":
            return Decimal("1.00")

        cache_key = f"fx_rate:{from_currency}:BDT"
        cached = cache.get(cache_key)
        if cached:
            return Decimal(str(cached))

        # Try live fetch
        rate = CurrencyConverter._fetch_live_rate(from_currency)
        if rate:
            cache.set(cache_key, str(rate), CACHE_TTL)
            return rate

        # Fallback
        fallback = FALLBACK_RATES_TO_BDT.get(from_currency, Decimal("1.00"))
        logger.warning(f"Using fallback rate: 1 {from_currency} = {fallback} BDT")
        return fallback

    @staticmethod
    def to_bdt(amount: Decimal, from_currency: str) -> Decimal:
        """Convert amount from any currency to BDT."""
        rate = CurrencyConverter.get_rate_to_bdt(from_currency)
        return (Decimal(str(amount)) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def from_bdt(bdt_amount: Decimal, to_currency: str) -> Decimal:
        """Convert BDT amount to another currency."""
        to_currency = to_currency.upper()
        if to_currency == "BDT":
            return Decimal(str(bdt_amount))
        rate = CurrencyConverter.get_rate_to_bdt(to_currency)
        if rate == 0:
            return Decimal("0")
        return (Decimal(str(bdt_amount)) / rate).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """Convert between any two currencies via BDT as pivot."""
        bdt = CurrencyConverter.to_bdt(amount, from_currency)
        return CurrencyConverter.from_bdt(bdt, to_currency)

    @staticmethod
    def _fetch_live_rate(currency: str) -> Decimal:
        """Fetch live exchange rate from API."""
        import requests

        # Try ExchangeRate-API (free tier)
        api_key = getattr(settings, "EXCHANGE_RATE_API_KEY", "")
        if api_key:
            try:
                resp = requests.get(
                    f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{currency}/BDT",
                    timeout=5,
                )
                data = resp.json()
                if data.get("result") == "success":
                    return Decimal(str(data["conversion_rate"]))
            except Exception as e:
                logger.debug(f"ExchangeRate-API failed: {e}")

        # Try OpenExchangeRates
        oxr_key = getattr(settings, "OPEN_EXCHANGE_RATES_APP_ID", "")
        if oxr_key:
            try:
                resp = requests.get(
                    f"https://openexchangerates.org/api/latest.json?app_id={oxr_key}&base=USD",
                    timeout=5,
                )
                data = resp.json()
                rates = data.get("rates", {})
                if "BDT" in rates and currency in rates:
                    usd_to_bdt = Decimal(str(rates["BDT"]))
                    usd_to_curr = Decimal(str(rates[currency]))
                    return (usd_to_bdt / usd_to_curr).quantize(Decimal("0.000001"))
            except Exception as e:
                logger.debug(f"OpenExchangeRates failed: {e}")

        return Decimal("0")

    @staticmethod
    def update_all_rates() -> dict:
        """Update all cached rates (called by currency_tasks daily)."""
        updated = {}
        for currency, fallback in FALLBACK_RATES_TO_BDT.items():
            if currency == "BDT":
                continue
            try:
                rate = CurrencyConverter._fetch_live_rate(currency)
                if rate > 0:
                    cache_key = f"fx_rate:{currency}:BDT"
                    cache.set(cache_key, str(rate), CACHE_TTL * 24)
                    updated[currency] = float(rate)
            except Exception as e:
                logger.error(f"Rate update failed {currency}: {e}")
        logger.info(f"Updated {len(updated)} exchange rates")
        return updated

    @staticmethod
    def get_all_rates() -> dict:
        """Get all current rates (for display)."""
        rates = {}
        for currency in FALLBACK_RATES_TO_BDT:
            rate = CurrencyConverter.get_rate_to_bdt(currency)
            rates[currency] = float(rate)
        return rates
