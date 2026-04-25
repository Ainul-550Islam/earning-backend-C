# api/wallet/cache_manager.py
"""
Centralized cache management for wallet balances, summaries, and rate data.
Uses Redis cache with proper key namespacing and TTLs.
"""
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger("wallet.cache")

# Cache TTLs (seconds)
BALANCE_TTL  = 30     # 30 seconds — balance changes frequently
SUMMARY_TTL  = 60     # 1 minute
RATE_TTL     = 3600   # 1 hour — exchange rates
STATS_TTL    = 300    # 5 minutes
LEADERBOARD_TTL = 600 # 10 minutes


class WalletCacheManager:
    """Manage all wallet-related cache keys."""

    # ── Balance ───────────────────────────────────────────
    @staticmethod
    def get_balance(wallet_id: int) -> Decimal:
        key = f"wallet:balance:{wallet_id}"
        val = cache.get(key)
        return Decimal(str(val)) if val is not None else None

    @staticmethod
    def set_balance(wallet_id: int, balance: Decimal):
        cache.set(f"wallet:balance:{wallet_id}", str(balance), BALANCE_TTL)

    # ── Wallet summary ────────────────────────────────────
    @staticmethod
    def get_summary(wallet_id: int) -> dict:
        return cache.get(f"wallet:summary:{wallet_id}")

    @staticmethod
    def set_summary(wallet_id: int, summary: dict):
        cache.set(f"wallet:summary:{wallet_id}", summary, SUMMARY_TTL)

    @staticmethod
    def invalidate_wallet(wallet_id: int):
        """Clear all cached data for a wallet (call after any mutation)."""
        keys = [
            f"wallet:balance:{wallet_id}",
            f"wallet:summary:{wallet_id}",
            f"wallet:stats:{wallet_id}",
        ]
        for key in keys:
            try: cache.delete(key)
            except Exception: pass
        logger.debug(f"Cache invalidated: wallet={wallet_id}")

    # ── User stats ────────────────────────────────────────
    @staticmethod
    def get_user_stats(user_id: int) -> dict:
        return cache.get(f"wallet:user_stats:{user_id}")

    @staticmethod
    def set_user_stats(user_id: int, stats: dict):
        cache.set(f"wallet:user_stats:{user_id}", stats, STATS_TTL)

    # ── Exchange rates ────────────────────────────────────
    @staticmethod
    def get_rate(from_cur: str, to_cur: str = "BDT") -> Decimal:
        val = cache.get(f"fx_rate:{from_cur.upper()}:{to_cur.upper()}")
        return Decimal(str(val)) if val else None

    @staticmethod
    def set_rate(from_cur: str, to_cur: str, rate: Decimal):
        cache.set(f"fx_rate:{from_cur.upper()}:{to_cur.upper()}", str(rate), RATE_TTL)

    # ── Leaderboard ───────────────────────────────────────
    @staticmethod
    def get_leaderboard(period: str = "today") -> list:
        return cache.get(f"wallet:leaderboard:{period}")

    @staticmethod
    def set_leaderboard(period: str, data: list):
        cache.set(f"wallet:leaderboard:{period}", data, LEADERBOARD_TTL)

    # ── Daily earning cap tracker ─────────────────────────
    @staticmethod
    def get_daily_earned(wallet_id: int, source_type: str) -> Decimal:
        """Get how much user has earned today from source_type."""
        from datetime import date
        key = f"wallet:daily_cap:{wallet_id}:{source_type}:{date.today()}"
        val = cache.get(key)
        return Decimal(str(val)) if val else Decimal("0")

    @staticmethod
    def add_daily_earned(wallet_id: int, source_type: str, amount: Decimal):
        """Add to today's earning total (atomic)."""
        from datetime import date
        key = f"wallet:daily_cap:{wallet_id}:{source_type}:{date.today()}"
        try:
            cache.incr(key, int(amount * 100))  # Store as paisa
        except Exception:
            cache.set(key, int(amount * 100), 86400)

    # ── Rate limiting ─────────────────────────────────────
    @staticmethod
    def get_rate_limit_count(user_id: int, action: str) -> int:
        return cache.get(f"ratelimit:{action}:user:{user_id}") or 0

    # ── Bulk invalidation ─────────────────────────────────
    @staticmethod
    def clear_all() -> None:
        """Clear all wallet caches (use with caution — dev/testing only)."""
        try:
            if hasattr(cache, "delete_pattern"):
                cache.delete_pattern("wallet:*")
                cache.delete_pattern("fx_rate:*")
                cache.delete_pattern("ratelimit:*")
        except Exception as e:
            logger.warning(f"Bulk cache clear failed: {e}")
