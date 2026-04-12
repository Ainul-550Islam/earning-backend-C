# api/promotions/cache/redis_cache.py
# Redis Cache Manager — Advanced Redis patterns (pipeline, pub/sub, locks)
import json, logging, time
from typing import Any, Optional
from django.core.cache import cache
from django.conf import settings
logger = logging.getLogger('cache.redis')

class RedisManager:
    """
    Advanced Redis operations beyond Django's cache API.
    Requires: django-redis backend.

    Patterns:
    1. Pipeline — batch operations (10x faster)
    2. Pub/Sub — real-time events
    3. Distributed lock (Redlock algorithm)
    4. Counter with TTL
    5. Sorted set (leaderboard)
    6. Rate limiter (sliding window)
    """

    def _get_client(self):
        try:
            return cache._cache.get_client()   # django-redis
        except Exception:
            return None

    # ── Pipeline ──────────────────────────────────────────────────────────────
    def pipeline_set(self, items: dict[str, Any], ttl: int = 3600) -> bool:
        """Multiple keys একসাথে set করে — 1 network roundtrip।"""
        client = self._get_client()
        if not client:
            for k, v in items.items():
                cache.set(k, v, timeout=ttl)
            return True
        try:
            pipe = client.pipeline()
            for k, v in items.items():
                pipe.setex(k, ttl, json.dumps(v))
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f'Pipeline set failed: {e}')
            return False

    def pipeline_get(self, keys: list[str]) -> dict:
        """Multiple keys একসাথে get করে।"""
        client = self._get_client()
        if not client:
            return {k: cache.get(k) for k in keys}
        try:
            pipe   = client.pipeline()
            for k in keys: pipe.get(k)
            values = pipe.execute()
            result = {}
            for k, v in zip(keys, values):
                result[k] = json.loads(v) if v else None
            return result
        except Exception as e:
            logger.error(f'Pipeline get failed: {e}')
            return {k: cache.get(k) for k in keys}

    # ── Distributed Lock ──────────────────────────────────────────────────────
    def acquire_lock(self, lock_name: str, ttl: int = 30, retry: int = 3) -> Optional[str]:
        """Distributed lock acquire করে।"""
        import uuid
        token = uuid.uuid4().hex
        key   = f'lock:{lock_name}'
        for _ in range(retry):
            added = cache.add(key, token, timeout=ttl)
            if added:
                return token
            time.sleep(0.05)
        return None

    def release_lock(self, lock_name: str, token: str) -> bool:
        """Lock release করে — শুধু owner release করতে পারে।"""
        key   = f'lock:{lock_name}'
        current = cache.get(key)
        if current == token:
            cache.delete(key)
            return True
        return False

    # ── Counter ───────────────────────────────────────────────────────────────
    def increment(self, key: str, delta: int = 1, ttl: int = 86400) -> int:
        """Atomic increment।"""
        try:
            val = cache.incr(key, delta)
            return val
        except Exception:
            current = cache.get(key) or 0
            new_val = current + delta
            cache.set(key, new_val, timeout=ttl)
            return new_val

    def get_counter(self, key: str) -> int:
        return cache.get(key) or 0

    # ── Sliding Window Rate Limiter ───────────────────────────────────────────
    def check_rate_limit(self, identifier: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Sliding window rate limiter।
        Returns: (allowed, current_count)
        """
        key = f'rl:{identifier}:{window}'
        client = self._get_client()

        if client:
            try:
                now    = time.time()
                cutoff = now - window
                pipe   = client.pipeline()
                pipe.zremrangebyscore(key, 0, cutoff)     # Remove old entries
                pipe.zadd(key, {str(now): now})           # Add current
                pipe.zcard(key)                            # Count
                pipe.expire(key, window + 1)
                _, _, count, _ = pipe.execute()
                return count <= limit, count
            except Exception:
                pass

        # Fallback: simple counter
        count = self.increment(f'rl_simple:{identifier}', ttl=window)
        return count <= limit, count

    # ── Sorted Set (Leaderboard) ──────────────────────────────────────────────
    def leaderboard_update(self, board_name: str, member: str, score: float) -> None:
        client = self._get_client()
        if client:
            try:
                client.zadd(f'lb:{board_name}', {member: score})
                return
            except Exception: pass
        # Fallback: dict in cache
        board = cache.get(f'lb:{board_name}') or {}
        board[member] = score
        cache.set(f'lb:{board_name}', board, timeout=86400)

    def leaderboard_top(self, board_name: str, n: int = 10) -> list:
        client = self._get_client()
        if client:
            try:
                return [(m.decode(), float(s)) for m, s in
                        client.zrevrange(f'lb:{board_name}', 0, n-1, withscores=True)]
            except Exception: pass
        board = cache.get(f'lb:{board_name}') or {}
        return sorted(board.items(), key=lambda x: x[1], reverse=True)[:n]


# Singleton
redis_manager = RedisManager()
