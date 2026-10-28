# api/wallet/caching.py
"""Advanced caching strategies for the wallet app."""
import logging
from decimal import Decimal
from functools import wraps
from django.core.cache import cache

logger = logging.getLogger("wallet.caching")

BALANCE_TTL  = 30    # seconds — hot data
SUMMARY_TTL  = 60
STATS_TTL    = 300
FX_TTL       = 3600
LIST_TTL     = 120


class WalletCache:
    """Structured cache manager with type-safe keys."""

    # ── Balance ───────────────────────────────────────────────
    @staticmethod
    def get_balance(wallet_id: int) -> Decimal:
        v = cache.get(f"w:bal:{wallet_id}")
        return Decimal(str(v)) if v is not None else None

    @staticmethod
    def set_balance(wallet_id: int, bal: Decimal):
        cache.set(f"w:bal:{wallet_id}", str(bal), BALANCE_TTL)

    @staticmethod
    def del_balance(wallet_id: int):
        cache.delete(f"w:bal:{wallet_id}")

    # ── Summary ───────────────────────────────────────────────
    @staticmethod
    def get_summary(wallet_id: int) -> dict:
        return cache.get(f"w:sum:{wallet_id}")

    @staticmethod
    def set_summary(wallet_id: int, data: dict):
        cache.set(f"w:sum:{wallet_id}", data, SUMMARY_TTL)

    # ── FX rates ──────────────────────────────────────────────
    @staticmethod
    def get_fx(from_cur: str, to_cur: str = "BDT") -> Decimal:
        v = cache.get(f"fx:{from_cur}:{to_cur}")
        return Decimal(str(v)) if v else None

    @staticmethod
    def set_fx(from_cur: str, to_cur: str, rate: Decimal):
        cache.set(f"fx:{from_cur}:{to_cur}", str(rate), FX_TTL)

    # ── Platform stats ────────────────────────────────────────
    @staticmethod
    def get_platform_stats() -> dict:
        return cache.get("w:platform_stats")

    @staticmethod
    def set_platform_stats(data: dict):
        cache.set("w:platform_stats", data, STATS_TTL)

    # ── Leaderboard ───────────────────────────────────────────
    @staticmethod
    def get_leaderboard(period: str = "today") -> list:
        return cache.get(f"w:leaderboard:{period}")

    @staticmethod
    def set_leaderboard(period: str, data: list):
        cache.set(f"w:leaderboard:{period}", data, 600)

    # ── Invalidation ──────────────────────────────────────────
    @staticmethod
    def invalidate_wallet(wallet_id: int):
        for key in [f"w:bal:{wallet_id}", f"w:sum:{wallet_id}",
                    f"w:stats:{wallet_id}"]:
            try: cache.delete(key)
            except Exception: pass

    @staticmethod
    def invalidate_all():
        try:
            if hasattr(cache, "delete_pattern"):
                cache.delete_pattern("w:*")
                cache.delete_pattern("fx:*")
        except Exception: pass


def cached(key_func, ttl: int = 60):
    """Generic caching decorator for functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            cached_val = cache.get(key)
            if cached_val is not None:
                return cached_val
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator
