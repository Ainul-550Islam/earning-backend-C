import pickle
import logging
from django.core.cache import cache
from ...constants import CACHE_PREFIX_SMARTLINK, CACHE_TTL_SMARTLINK, CACHE_TTL_TARGETING

logger = logging.getLogger('smartlink.cache')


class SmartLinkCacheService:
    """
    Redis cache layer for SmartLink resolver.
    Caches full SmartLink objects to achieve <1ms lookup times.
    """

    def get_smartlink(self, slug: str):
        """Retrieve SmartLink from cache. Returns None on miss."""
        key = self._sl_key(slug)
        try:
            cached = cache.get(key)
            if cached:
                logger.debug(f"Cache HIT: {slug}")
                return cached
        except Exception as e:
            logger.warning(f"Cache GET error for {slug}: {e}")
        return None

    def set_smartlink(self, slug: str, smartlink, ttl: int = CACHE_TTL_SMARTLINK):
        """Store SmartLink in cache."""
        key = self._sl_key(slug)
        try:
            cache.set(key, smartlink, ttl)
            logger.debug(f"Cache SET: {slug} TTL={ttl}s")
        except Exception as e:
            logger.warning(f"Cache SET error for {slug}: {e}")

    def invalidate_smartlink(self, slug: str):
        """Remove SmartLink from cache (call on update/delete)."""
        key = self._sl_key(slug)
        cache.delete(key)
        # Also invalidate the simple redirect cache
        cache.delete(f"{CACHE_PREFIX_SMARTLINK}{slug}:simple")
        logger.debug(f"Cache INVALIDATED: {slug}")

    def set_simple_redirect(self, slug: str, url: str, ttl: int = 60):
        """
        Cache a simple (no-targeting) redirect URL for ultra-fast middleware lookup.
        Only used for SmartLinks with no geo/device targeting rules.
        """
        key = f"{CACHE_PREFIX_SMARTLINK}{slug}:simple"
        cache.set(key, url, ttl)

    def get_offer_pool(self, smartlink_id: int):
        """Cache offer pool entries for a smartlink."""
        key = f"sl_pool:{smartlink_id}"
        return cache.get(key)

    def set_offer_pool(self, smartlink_id: int, pool_data, ttl: int = 60):
        key = f"sl_pool:{smartlink_id}"
        cache.set(key, pool_data, ttl)

    def invalidate_offer_pool(self, smartlink_id: int):
        cache.delete(f"sl_pool:{smartlink_id}")

    def get_targeting_rules(self, smartlink_id: int):
        """Cache full targeting rule set for a smartlink."""
        key = f"sl_targeting:{smartlink_id}"
        return cache.get(key)

    def set_targeting_rules(self, smartlink_id: int, rules, ttl: int = CACHE_TTL_TARGETING):
        key = f"sl_targeting:{smartlink_id}"
        cache.set(key, rules, ttl)

    def invalidate_targeting(self, smartlink_id: int):
        cache.delete(f"sl_targeting:{smartlink_id}")

    def warmup(self, slugs: list):
        """
        Pre-warm cache for a list of slugs.
        Called by warmup_cache management command and cache_warmup_tasks.
        """
        from ...models import SmartLink
        smartlinks = SmartLink.objects.filter(
            slug__in=slugs, is_active=True, is_archived=False
        ).select_related('offer_pool', 'targeting_rule', 'fallback', 'rotation_config')

        count = 0
        for sl in smartlinks:
            self.set_smartlink(sl.slug, sl)
            count += 1

        logger.info(f"Cache warmup: {count}/{len(slugs)} SmartLinks cached.")
        return count

    def warmup_all_active(self):
        """Pre-warm cache for all active SmartLinks."""
        from ...models import SmartLink
        slugs = list(SmartLink.objects.filter(
            is_active=True, is_archived=False
        ).values_list('slug', flat=True))
        return self.warmup(slugs)

    # ── Private ──────────────────────────────────────────────────────

    def _sl_key(self, slug: str) -> str:
        return f"{CACHE_PREFIX_SMARTLINK}{slug}"
