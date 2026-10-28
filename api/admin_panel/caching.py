# api/admin_panel/caching.py
"""
Admin Panel Caching Strategy — centralized cache management.
Cache key registry, TTL management, cache warming, cache busting,
Redis Pub/Sub integration, cache analytics.
"""
from __future__ import annotations
import logging
from typing import Any, Callable, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================================================
# CACHE KEY REGISTRY
# ===========================================================================

class CacheKeys:
    """Centralized cache key registry — all keys in one place."""

    # System config
    CONFIG          = 'admin_panel:config:{key}'
    CONFIG_GROUP    = 'admin_panel:config_group:{group}'
    CONFIG_ALL      = 'admin_panel:config_all'

    # Feature flags
    FLAG            = 'admin_panel:feature_flag:{key}'
    FLAGS_ALL       = 'admin_panel:feature_flags_all'
    FLAG_DEF        = 'admin_panel:flag_def:{key}'

    # Dashboard KPIs
    LIVE_KPIS       = 'admin:live_kpis'
    SYSTEM_KPIS     = 'admin_panel:system_kpis'
    WALLET_OVERVIEW = 'admin_panel:wallet_overview'

    # Maintenance
    MAINTENANCE_ON  = 'admin_panel:maintenance_mode_active'
    MAINTENANCE_MSG = 'admin_panel:maintenance_message'

    # Integration health
    INTEGRATION_HEALTH = 'admin_panel:integration_health_full'
    INTEGRATION_HEALTH_SUMMARY = 'admin_panel:integration_health'

    # Analytics
    REVENUE_OVERVIEW  = 'analytics:revenue_overview:{days}'
    USER_OVERVIEW     = 'analytics:user_overview'
    OFFER_ANALYTICS   = 'analytics:offer:{days}'
    FRAUD_ANALYTICS   = 'analytics:fraud:{days}'

    # Performance
    PERF_STATS      = 'admin_panel:perf_stats'

    # User
    USER_PROFILE    = 'admin_panel:user_profile:{user_id}'
    USER_RISK       = 'fraud:user_risk:{user_id}'

    # Sanctions
    SANCTIONS       = 'sanctions:screen:{user_id}:{hash}'
    SANCTIONS_LIST  = 'sanctions:names_cache'

    # Search
    SEARCH          = 'admin_panel:search:{hash}'
    SEARCH_POPULAR  = 'admin_panel:search_popular'

    # Push stats
    PUSH_STATS      = 'admin_panel:push_stats:{date}'

    # Rate limit
    RATE_LIMIT      = 'admin_panel:throttle:{scope}:{id}'

    # Circuit breaker
    CIRCUIT_BREAKER = 'admin_panel:circuit_breaker:{app}'

    @classmethod
    def format(cls, key_template: str, **kwargs) -> str:
        return key_template.format(**kwargs)


# ===========================================================================
# TTL REGISTRY
# ===========================================================================

class CacheTTL:
    """Standard TTL values in seconds."""
    REALTIME    = 5        # Live data: 5 seconds
    FAST        = 30       # Fast-changing: 30 seconds
    SHORT       = 60       # 1 minute
    MEDIUM      = 300      # 5 minutes
    STANDARD    = 600      # 10 minutes
    LONG        = 3600     # 1 hour
    DAY         = 86400    # 24 hours
    WEEK        = 604800   # 7 days


# ===========================================================================
# CACHE MANAGER
# ===========================================================================

class AdminCacheManager:
    """Manages all admin_panel cache operations."""

    def get(self, key: str, default: Any = None) -> Any:
        return cache.get(key, default)

    def set(self, key: str, value: Any, ttl: int = CacheTTL.STANDARD) -> bool:
        try:
            cache.set(key, value, ttl)
            return True
        except Exception as e:
            logger.error(f"[CacheManager.set] {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            cache.delete(key)
            return True
        except Exception:
            return False

    def delete_many(self, keys: List[str]) -> int:
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def get_or_set(self, key: str, fn: Callable, ttl: int = CacheTTL.STANDARD) -> Any:
        val = cache.get(key)
        if val is not None:
            return val
        val = fn()
        if val is not None:
            cache.set(key, val, ttl)
        return val

    # ── Config cache operations ──────────────────────────────────────────

    def clear_config_cache(self, key: str = '') -> None:
        if key:
            self.delete(CacheKeys.CONFIG.format(key=key))
        self.delete(CacheKeys.CONFIG_ALL)
        logger.info(f"[CacheManager] Config cache cleared: {key or 'all'}")

    def clear_flag_cache(self, flag_key: str = '') -> None:
        if flag_key:
            self.delete(CacheKeys.FLAG.format(key=flag_key))
            self.delete(CacheKeys.FLAG_DEF.format(key=flag_key))
        self.delete(CacheKeys.FLAGS_ALL)

    def clear_user_cache(self, user_id: Any) -> None:
        self.delete(CacheKeys.USER_PROFILE.format(user_id=user_id))
        self.delete(CacheKeys.USER_RISK.format(user_id=user_id))

    # ── Maintenance cache ────────────────────────────────────────────────

    def set_maintenance_active(self, message: str) -> None:
        cache.set(CacheKeys.MAINTENANCE_ON, True, CacheTTL.DAY)
        cache.set(CacheKeys.MAINTENANCE_MSG, message, CacheTTL.DAY)

    def clear_maintenance(self) -> None:
        self.delete(CacheKeys.MAINTENANCE_ON)
        self.delete(CacheKeys.MAINTENANCE_MSG)

    def is_maintenance_active(self) -> bool:
        return bool(cache.get(CacheKeys.MAINTENANCE_ON))

    # ── Analytics cache ──────────────────────────────────────────────────

    def clear_analytics_cache(self) -> None:
        for key in [CacheKeys.LIVE_KPIS, CacheKeys.SYSTEM_KPIS,
                    CacheKeys.WALLET_OVERVIEW, CacheKeys.USER_OVERVIEW]:
            self.delete(key)

    # ── Warm-up ──────────────────────────────────────────────────────────

    def warm_up(self) -> Dict[str, bool]:
        """Warm up critical caches."""
        results = {}
        # Config
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            SystemConfigService.get_all()
            results['config'] = True
        except Exception:
            results['config'] = False
        # Flags
        try:
            from api.admin_panel.services.FeatureFlagService import FeatureFlagService
            FeatureFlagService.get_all_states()
            results['flags'] = True
        except Exception:
            results['flags'] = False
        # KPIs
        try:
            from api.admin_panel.logic import get_dashboard_kpi_snapshot
            cache.set(CacheKeys.LIVE_KPIS, get_dashboard_kpi_snapshot(), CacheTTL.FAST)
            results['kpis'] = True
        except Exception:
            results['kpis'] = False
        logger.info(f"[CacheManager] Warm-up: {results}")
        return results

    # ── Stats ────────────────────────────────────────────────────────────

    def get_cache_stats(self) -> Dict:
        """Cache usage statistics."""
        key_stats = {
            'maintenance_active': bool(cache.get(CacheKeys.MAINTENANCE_ON)),
            'has_live_kpis':      cache.get(CacheKeys.LIVE_KPIS) is not None,
            'has_integration_health': cache.get(CacheKeys.INTEGRATION_HEALTH) is not None,
            'has_config':         cache.get(CacheKeys.CONFIG_ALL) is not None,
            'has_flags':          cache.get(CacheKeys.FLAGS_ALL) is not None,
        }
        return {'key_status': key_stats, 'checked_at': timezone.now().isoformat()}

    def flush_all(self, actor=None) -> bool:
        """Flush entire cache (superadmin only)."""
        try:
            cache.clear()
            logger.warning(f"[CacheManager] FULL CACHE FLUSH by {actor}")
            if actor:
                try:
                    from api.admin_panel.models.activity import AdminActivity
                    AdminActivity.log(actor=actor, action='flush_all_cache')
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"[CacheManager.flush_all] {e}")
            return False

    def flush_group(self, group: str, actor=None) -> List[str]:
        """Flush a named group of cache keys."""
        group_keys = {
            'config':      [CacheKeys.CONFIG_ALL],
            'flags':       [CacheKeys.FLAGS_ALL],
            'analytics':   [CacheKeys.LIVE_KPIS, CacheKeys.SYSTEM_KPIS,
                           CacheKeys.WALLET_OVERVIEW, CacheKeys.USER_OVERVIEW],
            'health':      [CacheKeys.INTEGRATION_HEALTH, CacheKeys.INTEGRATION_HEALTH_SUMMARY],
            'maintenance': [CacheKeys.MAINTENANCE_ON, CacheKeys.MAINTENANCE_MSG],
        }
        keys = group_keys.get(group, [])
        deleted = []
        for key in keys:
            if self.delete(key):
                deleted.append(key)
        logger.info(f"[CacheManager] Flushed group '{group}': {deleted}")
        return deleted


# Global cache manager
cache_manager = AdminCacheManager()