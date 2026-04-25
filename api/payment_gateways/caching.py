# api/payment_gateways/caching.py
# Full Redis caching layer for payment_gateways
# "Do not summarize or skip any logic. Provide the full code."

import json
import logging
from decimal import Decimal
from typing import Any, Optional, Callable
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Cache key prefixes ─────────────────────────────────────────────────────────
class CacheKey:
    GATEWAY_STATUS      = 'pg:gw:status:{gateway}'
    GATEWAY_HEALTH      = 'pg:gw:health:{gateway}'
    GATEWAY_LIST        = 'pg:gw:list:active'
    GATEWAY_FEE         = 'pg:gw:fee:{gateway}'
    EXCHANGE_RATE       = 'pg:fx:{from_currency}:{to_currency}'
    ALL_RATES           = 'pg:fx:all'
    OFFER_LIST          = 'pg:offers:active:{country}:{device}'
    OFFER_EPC           = 'pg:offer:epc:{offer_id}'
    OFFER_CAPS          = 'pg:offer:caps:{offer_id}'
    PUBLISHER_BALANCE   = 'pg:pub:balance:{user_id}'
    PUBLISHER_PROFILE   = 'pg:pub:profile:{user_id}'
    PUBLISHER_STATS     = 'pg:pub:stats:{user_id}:{period}'
    USER_CAPABILITIES   = 'pg:user:caps:{user_id}'
    FEATURE_FLAG        = 'pg:ff:{flag_name}'
    FRAUD_RISK          = 'pg:fraud:risk:{user_id}'
    CLICK_DUPLICATE     = 'pg:click:dup:{click_id}:{offer_id}'
    SMARTLINK_ROTATION  = 'pg:sl:rotation:{smart_link_id}'
    DASHBOARD_STATS     = 'pg:dashboard:stats:{admin_id}'
    LEADERBOARD         = 'pg:leaderboard:{period}'
    KB_ENTRY            = 'pg:kb:{slug}'
    KYC_STATUS          = 'pg:kyc:{user_id}'
    CONVERSION_COUNT    = 'pg:conv:count:{offer_id}:{date}'
    RATE_LIMIT          = 'pg:rl:{operation}:{user_id}'


# ── Cache TTLs ─────────────────────────────────────────────────────────────────
class CacheTTL:
    GATEWAY_STATUS   = 300    # 5 minutes
    GATEWAY_HEALTH   = 60     # 1 minute
    GATEWAY_LIST     = 300    # 5 minutes
    EXCHANGE_RATE    = 3600   # 1 hour
    OFFER_LIST       = 300    # 5 minutes
    OFFER_EPC        = 1800   # 30 minutes
    OFFER_CAPS       = 60     # 1 minute (needs to be fresh)
    PUBLISHER_BALANCE= 30     # 30 seconds (balance changes fast)
    PUBLISHER_PROFILE= 600    # 10 minutes
    PUBLISHER_STATS  = 300    # 5 minutes
    USER_CAPABILITIES= 600    # 10 minutes
    FEATURE_FLAG     = 300    # 5 minutes
    FRAUD_RISK       = 1800   # 30 minutes
    CLICK_DUPLICATE  = 86400  # 24 hours
    LEADERBOARD      = 300    # 5 minutes
    DASHBOARD_STATS  = 60     # 1 minute
    KYC_STATUS       = 3600   # 1 hour


class PaymentCache:
    """
    Centralized caching layer for payment_gateways.

    Provides typed get/set/invalidate methods for every cached entity.
    All methods handle serialization, deserialization, and error handling.

    Usage:
        pc = PaymentCache()
        # Get with fallback
        balance = pc.get_publisher_balance(user_id=1, fallback=lambda: db_query())
        # Set
        pc.set_exchange_rate('USD', 'BDT', Decimal('110.5'))
        # Invalidate
        pc.invalidate_offer(offer_id=42)
    """

    # ── Generic helpers ────────────────────────────────────────────────────────
    def get_or_set(self, key: str, factory: Callable,
                    ttl: int = 300) -> Any:
        """Get from cache or compute with factory."""
        value = cache.get(key)
        if value is None:
            try:
                value = factory()
                if value is not None:
                    cache.set(key, value, ttl)
            except Exception as e:
                logger.debug(f'Cache factory failed for {key}: {e}')
        return value

    def get(self, key: str, default=None) -> Any:
        """Safe cache get."""
        try:
            return cache.get(key, default)
        except Exception:
            return default

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Safe cache set."""
        try:
            cache.set(key, value, ttl)
            return True
        except Exception as e:
            logger.debug(f'Cache set failed for {key}: {e}')
            return False

    def delete(self, key: str):
        """Safe cache delete."""
        try:
            cache.delete(key)
        except Exception:
            pass

    def delete_many(self, keys: list):
        """Delete multiple cache keys."""
        try:
            cache.delete_many(keys)
        except Exception:
            for key in keys:
                self.delete(key)

    # ── Gateway caching ────────────────────────────────────────────────────────
    def get_gateway_list(self) -> Optional[list]:
        return self.get(CacheKey.GATEWAY_LIST)

    def set_gateway_list(self, gateways: list):
        self.set(CacheKey.GATEWAY_LIST, gateways, CacheTTL.GATEWAY_LIST)

    def get_gateway_health(self, gateway: str) -> Optional[dict]:
        return self.get(CacheKey.GATEWAY_HEALTH.format(gateway=gateway))

    def set_gateway_health(self, gateway: str, health_data: dict):
        self.set(
            CacheKey.GATEWAY_HEALTH.format(gateway=gateway),
            health_data, CacheTTL.GATEWAY_HEALTH
        )

    def invalidate_gateway(self, gateway: str):
        self.delete_many([
            CacheKey.GATEWAY_LIST,
            CacheKey.GATEWAY_HEALTH.format(gateway=gateway),
            CacheKey.GATEWAY_STATUS.format(gateway=gateway),
            CacheKey.GATEWAY_FEE.format(gateway=gateway),
        ])

    # ── Exchange rate caching ──────────────────────────────────────────────────
    def get_exchange_rate(self, from_currency: str,
                           to_currency: str) -> Optional[Decimal]:
        key = CacheKey.EXCHANGE_RATE.format(
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
        )
        value = self.get(key)
        return Decimal(str(value)) if value is not None else None

    def set_exchange_rate(self, from_currency: str, to_currency: str,
                           rate: Decimal):
        key = CacheKey.EXCHANGE_RATE.format(
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
        )
        self.set(key, float(rate), CacheTTL.EXCHANGE_RATE)

    def get_all_rates(self) -> Optional[dict]:
        return self.get(CacheKey.ALL_RATES)

    def set_all_rates(self, rates: dict):
        self.set(CacheKey.ALL_RATES, rates, CacheTTL.EXCHANGE_RATE)

    def invalidate_exchange_rates(self):
        self.delete(CacheKey.ALL_RATES)
        # Also delete individual rate keys
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            keys = conn.keys('pg:fx:*')
            if keys:
                conn.delete(*keys)
        except Exception:
            pass

    # ── Offer caching ──────────────────────────────────────────────────────────
    def get_offer_list(self, country: str = '', device: str = '') -> Optional[list]:
        key = CacheKey.OFFER_LIST.format(country=country.upper(), device=device.lower())
        return self.get(key)

    def set_offer_list(self, offers: list, country: str = '', device: str = ''):
        key = CacheKey.OFFER_LIST.format(country=country.upper(), device=device.lower())
        self.set(key, offers, CacheTTL.OFFER_LIST)

    def get_offer_caps(self, offer_id: int) -> Optional[dict]:
        return self.get(CacheKey.OFFER_CAPS.format(offer_id=offer_id))

    def set_offer_caps(self, offer_id: int, caps: dict):
        self.set(CacheKey.OFFER_CAPS.format(offer_id=offer_id), caps, CacheTTL.OFFER_CAPS)

    def invalidate_offer(self, offer_id: int):
        self.delete_many([
            CacheKey.OFFER_EPC.format(offer_id=offer_id),
            CacheKey.OFFER_CAPS.format(offer_id=offer_id),
        ])
        # Invalidate all offer lists (country+device combos)
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            keys = conn.keys('pg:offers:active:*')
            if keys:
                conn.delete(*keys)
        except Exception:
            self.delete(CacheKey.OFFER_LIST.format(country='', device=''))

    # ── Publisher caching ──────────────────────────────────────────────────────
    def get_publisher_balance(self, user_id: int) -> Optional[Decimal]:
        value = self.get(CacheKey.PUBLISHER_BALANCE.format(user_id=user_id))
        return Decimal(str(value)) if value is not None else None

    def set_publisher_balance(self, user_id: int, balance: Decimal):
        self.set(
            CacheKey.PUBLISHER_BALANCE.format(user_id=user_id),
            float(balance), CacheTTL.PUBLISHER_BALANCE
        )

    def get_publisher_stats(self, user_id: int, period: str) -> Optional[dict]:
        return self.get(CacheKey.PUBLISHER_STATS.format(user_id=user_id, period=period))

    def set_publisher_stats(self, user_id: int, period: str, stats: dict):
        self.set(
            CacheKey.PUBLISHER_STATS.format(user_id=user_id, period=period),
            stats, CacheTTL.PUBLISHER_STATS
        )

    def invalidate_publisher(self, user_id: int):
        self.delete_many([
            CacheKey.PUBLISHER_BALANCE.format(user_id=user_id),
            CacheKey.PUBLISHER_PROFILE.format(user_id=user_id),
            CacheKey.USER_CAPABILITIES.format(user_id=user_id),
        ])
        # Invalidate stats for all periods
        for period in ('today', 'this_week', 'this_month', 'all_time'):
            self.delete(CacheKey.PUBLISHER_STATS.format(user_id=user_id, period=period))

    # ── Fraud / Rate limit caching ─────────────────────────────────────────────
    def get_fraud_risk(self, user_id: int) -> Optional[dict]:
        return self.get(CacheKey.FRAUD_RISK.format(user_id=user_id))

    def set_fraud_risk(self, user_id: int, risk_data: dict):
        self.set(CacheKey.FRAUD_RISK.format(user_id=user_id), risk_data, CacheTTL.FRAUD_RISK)

    def check_rate_limit(self, operation: str, user_id: int,
                          max_count: int, window_seconds: int) -> tuple:
        """
        Check and increment rate limit counter.

        Returns:
            tuple: (is_allowed: bool, current_count: int, max_count: int)
        """
        key   = CacheKey.RATE_LIMIT.format(operation=operation, user_id=user_id)
        count = self.get(key, 0) or 0
        if count >= max_count:
            return False, count, max_count
        # Increment
        try:
            from django_redis import get_redis_connection
            conn     = get_redis_connection('default')
            new_count= conn.incr(key)
            if new_count == 1:
                conn.expire(key, window_seconds)
            return new_count <= max_count, new_count, max_count
        except Exception:
            new_count = count + 1
            self.set(key, new_count, window_seconds)
            return new_count <= max_count, new_count, max_count

    def is_click_duplicate(self, click_id: str, offer_id: int) -> bool:
        key = CacheKey.CLICK_DUPLICATE.format(click_id=click_id, offer_id=offer_id)
        return bool(self.get(key))

    def record_click(self, click_id: str, offer_id: int):
        key = CacheKey.CLICK_DUPLICATE.format(click_id=click_id, offer_id=offer_id)
        self.set(key, True, CacheTTL.CLICK_DUPLICATE)

    # ── SmartLink caching ──────────────────────────────────────────────────────
    def get_smartlink_rotation(self, smart_link_id: int) -> Optional[list]:
        return self.get(CacheKey.SMARTLINK_ROTATION.format(smart_link_id=smart_link_id))

    def set_smartlink_rotation(self, smart_link_id: int, candidates: list):
        self.set(
            CacheKey.SMARTLINK_ROTATION.format(smart_link_id=smart_link_id),
            candidates, 60  # 1 minute — rotation data changes
        )

    # ── Dashboard stats caching ────────────────────────────────────────────────
    def get_dashboard_stats(self, admin_id: int) -> Optional[dict]:
        return self.get(CacheKey.DASHBOARD_STATS.format(admin_id=admin_id))

    def set_dashboard_stats(self, admin_id: int, stats: dict):
        self.set(
            CacheKey.DASHBOARD_STATS.format(admin_id=admin_id),
            stats, CacheTTL.DASHBOARD_STATS
        )

    def get_leaderboard(self, period: str) -> Optional[list]:
        return self.get(CacheKey.LEADERBOARD.format(period=period))

    def set_leaderboard(self, period: str, data: list):
        self.set(CacheKey.LEADERBOARD.format(period=period), data, CacheTTL.LEADERBOARD)

    # ── Full cache flush ───────────────────────────────────────────────────────
    def flush_all(self, prefix: str = 'pg:'):
        """
        Flush all payment_gateways cache keys.
        USE WITH CAUTION — causes cache stampede.
        """
        try:
            from django_redis import get_redis_connection
            conn  = get_redis_connection('default')
            keys  = conn.keys(f'{prefix}*')
            count = len(keys)
            if keys:
                conn.delete(*keys)
            logger.warning(f'Flushed {count} cache keys with prefix {prefix}')
            return count
        except Exception as e:
            logger.error(f'Cache flush failed: {e}')
            return 0

    def get_stats(self) -> dict:
        """Get cache hit/miss statistics."""
        try:
            from django_redis import get_redis_connection
            conn  = get_redis_connection('default')
            info  = conn.info('stats')
            keys  = len(conn.keys('pg:*'))
            return {
                'total_pg_keys':   keys,
                'keyspace_hits':   info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate':        round(
                    info.get('keyspace_hits', 0) /
                    max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0)) * 100, 1
                ),
            }
        except Exception:
            return {'available': False}


# Global cache instance
payment_cache = PaymentCache()
