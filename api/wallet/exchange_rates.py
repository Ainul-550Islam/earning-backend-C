# api/wallet/exchange_rates.py
"""
LiveExchangeRateService — Fetch live BDT exchange rates.

Primary:  Bangladesh Bank (BB) open data API
Fallback: exchangerate-api.com (free tier)
Cache:    Redis, 1-hour TTL (rates don't change minute-to-minute)

All rates returned as Decimal (never float).
Thread-safe: cache.set is atomic on Redis.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.core.cache import cache

logger = logging.getLogger("wallet.exchange_rates")

_CACHE_TTL   = 3600          # 1 hour
_CACHE_PREFIX = "wallet_xrate"

# Hard-coded fallback rates (BDT per 1 unit of currency)
# Updated periodically — only used if all live fetches fail
_FALLBACK_RATES: dict = {
    "USD": Decimal("110.00"),
    "EUR": Decimal("120.00"),
    "GBP": Decimal("140.00"),
    "JPY": Decimal("0.74"),
    "CAD": Decimal("80.00"),
    "AUD": Decimal("72.00"),
    "SGD": Decimal("81.00"),
    "INR": Decimal("1.32"),
    "PKR": Decimal("0.39"),
    "SAR": Decimal("29.30"),
    "AED": Decimal("29.95"),
    "MYR": Decimal("23.50"),
    "THB": Decimal("3.05"),
    "CNY": Decimal("15.20"),
    "USDT": Decimal("110.00"),   # Tether ≈ USD
    "BTC": Decimal("11000000"),  # Approximate, always use live for crypto
    "ETH": Decimal("380000"),
}


class LiveExchangeRateService:
    """
    Live BDT exchange rate fetcher.

    Usage:
        rate = LiveExchangeRateService.get_rate("USD")  # BDT per 1 USD
        bdt  = LiveExchangeRateService.convert(100, "USD", "BDT")
    """

    @classmethod
    def get_rate(cls, from_currency: str, to_currency: str = "BDT") -> Decimal:
        """
        Get exchange rate: how many `to_currency` per 1 `from_currency`.
        Default: BDT per 1 unit of from_currency.

        Examples:
            get_rate("USD")        → Decimal("110.00")  (110 BDT per $1)
            get_rate("BDT", "USD") → Decimal("0.0091")  ($0.0091 per 1 BDT)
        """
        from_currency = from_currency.upper()
        to_currency   = to_currency.upper()

        if from_currency == to_currency:
            return Decimal("1.00")

        # Normalize: always fetch as "X per BDT" or "BDT per X"
        if to_currency == "BDT":
            return cls._get_bdt_rate(from_currency)
        if from_currency == "BDT":
            rate = cls._get_bdt_rate(to_currency)
            if rate and rate > Decimal("0"):
                return (Decimal("1") / rate).quantize(Decimal("0.00000001"))
            return Decimal("0")

        # Cross rate: from_currency → BDT → to_currency
        from_rate = cls._get_bdt_rate(from_currency)   # BDT per from_currency
        to_rate   = cls._get_bdt_rate(to_currency)     # BDT per to_currency
        if not from_rate or not to_rate or to_rate == Decimal("0"):
            return Decimal("0")
        return (from_rate / to_rate).quantize(Decimal("0.00000001"))

    @classmethod
    def convert(cls, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """
        Convert an amount between currencies.

        Example:
            convert(Decimal("100"), "USD", "BDT") → Decimal("11000.00")
        """
        amount = Decimal(str(amount))
        rate   = cls.get_rate(from_currency, to_currency)
        if not rate:
            raise ValueError(f"No exchange rate for {from_currency} → {to_currency}")
        return (amount * rate).quantize(Decimal("0.00000001"))

    @classmethod
    def get_all_rates(cls) -> dict:
        """Return BDT rates for all supported currencies."""
        return {
            currency: str(cls.get_rate(currency))
            for currency in _FALLBACK_RATES
        }

    @classmethod
    def invalidate_cache(cls) -> None:
        """Force-clear cached rates (e.g. after manual update)."""
        for currency in _FALLBACK_RATES:
            cache.delete(f"{_CACHE_PREFIX}:{currency}")
        logger.info("Exchange rate cache cleared")

    # ── Private helpers ──────────────────────────────────────────

    @classmethod
    def _get_bdt_rate(cls, currency: str) -> Decimal:
        """Return BDT per 1 unit of currency. Cached 1 hour."""
        cache_key = f"{_CACHE_PREFIX}:{currency}"
        cached = cache.get(cache_key)
        if cached is not None:
            try:
                return Decimal(str(cached))
            except InvalidOperation:
                pass

        # Try live sources
        rate = cls._fetch_bb_api(currency) or cls._fetch_exchangerate_api(currency)

        if not rate:
            rate = _FALLBACK_RATES.get(currency, Decimal("0"))
            logger.warning(
                f"Exchange rate live fetch failed for {currency}; "
                f"using fallback {rate}"
            )

        cache.set(cache_key, str(rate), timeout=_CACHE_TTL)
        return rate

    @staticmethod
    def _fetch_bb_api(currency: str) -> Decimal:
        """Bangladesh Bank open data API (BDT rates)."""
        try:
            import requests
            # BB provides exchange rates in XML — simplified endpoint
            resp = requests.get(
                "https://www.bangladesh-bank.org/econdata/exchangerate.php",
                params={"currency": currency},
                timeout=5,
            )
            if resp.status_code == 200:
                import re
                # BB returns formats like "110.50" for USD
                match = re.search(r"[\d,]+\.?\d*", resp.text)
                if match:
                    raw = match.group().replace(",", "")
                    return Decimal(raw).quantize(Decimal("0.00000001"))
        except Exception as e:
            logger.debug(f"BB API fetch failed {currency}: {e}")
        return Decimal("0")

    @staticmethod
    def _fetch_exchangerate_api(currency: str) -> Decimal:
        """exchangerate-api.com free endpoint (no key, BDT base)."""
        try:
            import requests
            resp = requests.get(
                f"https://open.er-api.com/v6/latest/BDT",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                target_rate = rates.get(currency)  # how many currency per 1 BDT
                if target_rate and float(target_rate) > 0:
                    # Invert: we want BDT per 1 currency
                    bdt_per_unit = Decimal("1") / Decimal(str(target_rate))
                    return bdt_per_unit.quantize(Decimal("0.00000001"))
        except Exception as e:
            logger.debug(f"exchangerate-api fetch failed {currency}: {e}")
        return Decimal("0")
