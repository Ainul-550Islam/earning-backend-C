# =============================================================================
# api/promotions/localization/currency_cache.py
# Currency Cache — Exchange rates background refresh, multi-layer caching
# =============================================================================

import logging
import threading
import time
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger('localization.currency_cache')
CACHE_PREFIX_CURR = 'loc:curr:{}'


# All currency pairs to pre-cache
CURRENCY_PAIRS_TO_CACHE = [
    ('USD', 'BDT'), ('USD', 'INR'), ('USD', 'PKR'), ('USD', 'NGN'),
    ('USD', 'IDR'), ('USD', 'PHP'), ('USD', 'MYR'), ('USD', 'BRL'),
    ('USD', 'MXN'), ('USD', 'TRY'), ('USD', 'GBP'), ('USD', 'EUR'),
    ('USD', 'JPY'), ('USD', 'KRW'), ('USD', 'CNY'), ('USD', 'AED'),
    ('BDT', 'USD'), ('INR', 'USD'),
]


class CurrencyRateCache:
    """
    Currency rates multi-layer cache।

    Layers:
    1. In-memory dict (fastest — Python process memory)
    2. Redis cache (shared across workers)
    3. Database (CurrencyRate model)
    4. API fetch (slowest — network call)

    Background refresh: প্রতি ঘন্টায় Celery task দিয়ে rates update।
    """

    _memory_cache: dict = {}  # In-process cache
    _lock = threading.Lock()

    def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Exchange rate return করে — fastest available source থেকে।"""
        from_c = from_currency.upper()
        to_c   = to_currency.upper()
        key    = f'{from_c}_{to_c}'

        # Layer 1: Memory
        if key in self._memory_cache:
            rate, expires_at = self._memory_cache[key]
            if time.time() < expires_at:
                return rate

        # Layer 2: Redis
        redis_key = CACHE_PREFIX_CURR.format(key)
        cached    = cache.get(redis_key)
        if cached:
            rate = Decimal(str(cached))
            with self._lock:
                self._memory_cache[key] = (rate, time.time() + 300)  # 5 min memory cache
            return rate

        # Layer 3: Database
        db_rate = self._get_from_db(from_c, to_c)
        if db_rate:
            self._set_to_cache(key, db_rate, ttl=3600)
            return db_rate

        # Layer 4: API fetch
        from .forex_engine import ForexEngine
        rate_obj = ForexEngine().get_rate(from_c, to_c)
        self._set_to_cache(key, rate_obj.rate, ttl=3600)
        self._save_to_db(from_c, to_c, rate_obj.rate, rate_obj.source)
        return rate_obj.rate

    def refresh_all_rates(self) -> dict:
        """সব configured currency pairs refresh করে।"""
        from .forex_engine import ForexEngine
        engine  = ForexEngine()
        results = {}

        for from_c, to_c in CURRENCY_PAIRS_TO_CACHE:
            try:
                rate_obj = engine.get_rate(from_c, to_c)
                key = f'{from_c}_{to_c}'
                self._set_to_cache(key, rate_obj.rate, ttl=3600)
                self._save_to_db(from_c, to_c, rate_obj.rate, rate_obj.source)
                results[key] = float(rate_obj.rate)
                logger.debug(f'Rate refreshed: {key} = {rate_obj.rate}')
            except Exception as e:
                logger.error(f'Rate refresh failed for {from_c}_{to_c}: {e}')

        logger.info(f'Currency rates refreshed: {len(results)} pairs')
        return results

    def get_all_rates(self) -> dict:
        """All available rates return করে।"""
        rates = {}
        for from_c, to_c in CURRENCY_PAIRS_TO_CACHE:
            try:
                rates[f'{from_c}_{to_c}'] = float(self.get_rate(from_c, to_c))
            except Exception:
                pass
        return rates

    def _set_to_cache(self, key: str, rate: Decimal, ttl: int = 3600) -> None:
        cache.set(CACHE_PREFIX_CURR.format(key), str(rate), timeout=ttl)
        with self._lock:
            self._memory_cache[key] = (rate, time.time() + min(ttl, 300))

    def _get_from_db(self, from_c: str, to_c: str) -> Decimal | None:
        try:
            from api.promotions.models import CurrencyRate
            from django.utils import timezone
            from datetime import timedelta
            rate = CurrencyRate.objects.filter(
                base_currency=from_c, target_currency=to_c,
                is_active=True,
                fetched_at__gte=timezone.now() - timedelta(hours=2),
            ).order_by('-fetched_at').values('rate').first()
            return Decimal(str(rate['rate'])) if rate else None
        except Exception:
            return None

    def _save_to_db(self, from_c: str, to_c: str, rate: Decimal, source: str) -> None:
        try:
            from api.promotions.models import CurrencyRate
            from django.utils import timezone
            CurrencyRate.objects.update_or_create(
                base_currency=from_c, target_currency=to_c,
                defaults={'rate': rate, 'source': source, 'fetched_at': timezone.now(), 'is_active': True},
            )
        except Exception as e:
            logger.debug(f'DB save failed for rate {from_c}_{to_c}: {e}')


# Singleton
currency_cache = CurrencyRateCache()
