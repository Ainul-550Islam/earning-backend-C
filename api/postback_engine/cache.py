"""
cache.py
─────────
Centralised cache management for Postback Engine.
All cache key definitions, TTLs, and helper methods in one place.
Uses Django's cache framework (Redis backend recommended).
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Cache Key Templates ────────────────────────────────────────────────────────
KEYS = {
    "network_config":     "pe:net:{network_id}:config",
    "nonce_used":         "pe:nonce:{nonce}",
    "click":              "pe:click:{click_id}",
    "dedup_lead":         "pe:dedup:lead:{network_id}:{lead_hash}",
    "dedup_txn":          "pe:dedup:txn:{txn_hash}",
    "dedup_lock":         "pe:dedup:lock:{network_id}:{lead_hash}",
    "ip_blacklist":       "pe:bl:ip:{ip_hash}",
    "proxy_check":        "pe:proxy:{ip_hash}",
    "rate_limit":         "pe:rl:{scope}:{identifier}",
    "vel_ip_1m":          "pe:vel:ip:1m:{ip_hash}",
    "vel_ip_1h":          "pe:vel:ip:1h:{ip_hash}",
    "vel_ip_24h":         "pe:vel:ip:24h:{ip_hash}",
    "vel_user_1h":        "pe:vel:user:1h:{user_id}",
    "vel_net_1m":         "pe:vel:net:1m:{network_id}",
    "worker_heartbeat":   "pe:worker:{worker_id}:heartbeat",
    "webhook_registry":   "pe:webhook:registry:{network_id}:{event}",
    "ip_whitelist":       "pe:wl:{network_id}",
    "realtime_clicks":    "pe:rt:clicks:now",
    "realtime_convs":     "pe:rt:convs:now",
    "realtime_revenue":   "pe:rt:revenue:now",
    "realtime_fraud":     "pe:rt:fraud:now",
    "hourly_stat":        "pe:stat:hourly:{network_id}:{date}:{hour}",
}

# ── TTLs (seconds) ─────────────────────────────────────────────────────────────
TTL = {
    "network_config":   600,        # 10 minutes
    "nonce":            360,        # 6 minutes (> signature tolerance)
    "click":            86400,      # 24 hours
    "dedup":            2592000,    # 30 days
    "dedup_lock":       30,         # 30 seconds
    "blacklist":        3600,       # 1 hour
    "proxy":            86400,      # 24 hours
    "rate_limit_1m":    60,
    "velocity_1m":      60,
    "velocity_1h":      3600,
    "velocity_24h":     86400,
    "worker":           30,
    "webhook_registry": 300,
    "ip_whitelist":     600,
    "realtime":         300,        # 5 minutes
    "hourly_stat":      300,
}


class PostbackEngineCache:
    """Cache helper for all Postback Engine cache operations."""

    # ── Generic CRUD ──────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        try:
            return cache.get(key)
        except Exception as exc:
            logger.debug("cache.get failed key=%s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int) -> bool:
        try:
            cache.set(key, value, timeout=ttl)
            return True
        except Exception as exc:
            logger.debug("cache.set failed key=%s: %s", key, exc)
            return False

    def delete(self, key: str) -> None:
        try:
            cache.delete(key)
        except Exception:
            pass

    def delete_many(self, keys: list) -> None:
        try:
            cache.delete_many(keys)
        except Exception:
            pass

    def incr(self, key: str, ttl: int) -> int:
        """Atomic increment with TTL on first write."""
        try:
            try:
                return cache.incr(key)
            except ValueError:
                cache.add(key, 1, timeout=ttl)
                return cache.incr(key)
        except Exception:
            return 0

    def add(self, key: str, value: Any, ttl: int) -> bool:
        """Set only if key doesn't exist (SETNX). Returns True if set."""
        try:
            return bool(cache.add(key, value, timeout=ttl))
        except Exception:
            return False

    # ── Specific helpers ──────────────────────────────────────────────────────

    def cache_network_config(self, network_id: str, config_dict: dict) -> None:
        key = KEYS["network_config"].format(network_id=network_id)
        self.set(key, json.dumps(config_dict), TTL["network_config"])

    def get_network_config(self, network_id: str) -> Optional[dict]:
        key = KEYS["network_config"].format(network_id=network_id)
        raw = self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    def invalidate_network_config(self, network_id: str) -> None:
        key = KEYS["network_config"].format(network_id=network_id)
        self.delete(key)

    def mark_nonce_used(self, nonce: str) -> bool:
        """Mark nonce as used. Returns True if this is the first use."""
        import hashlib
        nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()[:32]
        key = KEYS["nonce_used"].format(nonce=nonce_hash)
        return self.add(key, "1", TTL["nonce"])

    def is_nonce_used(self, nonce: str) -> bool:
        import hashlib
        nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()[:32]
        key = KEYS["nonce_used"].format(nonce=nonce_hash)
        return self.get(key) is not None

    def get_or_set(self, key: str, loader_fn, ttl: int) -> Any:
        """Cache-aside pattern: try cache, call loader on miss."""
        value = self.get(key)
        if value is None:
            value = loader_fn()
            if value is not None:
                self.set(key, value, ttl)
        return value

    def flush_all_postback_engine_keys(self) -> None:
        """
        WARNING: Flushes all pe: prefixed keys.
        Only use in development/testing.
        """
        try:
            client = cache.client.get_client()
            keys = client.keys("pe:*")
            if keys:
                client.delete(*keys)
            logger.warning("PostbackEngineCache: flushed %d keys", len(keys))
        except Exception as exc:
            logger.warning("flush_all failed: %s", exc)


# Module-level singleton
pe_cache = PostbackEngineCache()
