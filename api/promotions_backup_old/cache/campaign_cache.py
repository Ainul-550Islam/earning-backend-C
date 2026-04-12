# api/promotions/cache/campaign_cache.py
# Campaign Cache — Smart campaign data caching with invalidation strategies
import logging
from decimal import Decimal
from typing import Optional
from django.core.cache import cache
logger = logging.getLogger('cache.campaign')

CACHE_VERSION      = 'v1'
CACHE_PREFIX       = f'camp:{CACHE_VERSION}:'
CACHE_TTL_ACTIVE   = 300    # 5 min — active campaigns change often
CACHE_TTL_DETAIL   = 600    # 10 min — campaign details
CACHE_TTL_STATS    = 120    # 2 min — real-time stats
CACHE_TTL_LIST     = 60     # 1 min — campaign lists


class CampaignCache:
    """
    Smart campaign caching layer.
    Automatic invalidation on model save (via signals).

    Key patterns:
    camp:v1:active:{platform}          → active campaigns per platform
    camp:v1:detail:{campaign_id}       → full campaign data
    camp:v1:stats:{campaign_id}        → real-time stats
    camp:v1:worker:{user_id}:eligible  → eligible campaigns for worker
    camp:v1:list:page:{page}:{filters} → paginated campaign lists
    """

    def get_active(self, platform: str = None, country: str = None) -> Optional[list]:
        key = CACHE_PREFIX + f'active:{platform or "all"}:{country or "all"}'
        return cache.get(key)

    def set_active(self, campaigns: list, platform: str = None, country: str = None) -> None:
        key = CACHE_PREFIX + f'active:{platform or "all"}:{country or "all"}'
        cache.set(key, campaigns, timeout=CACHE_TTL_ACTIVE)

    def get_detail(self, campaign_id: int) -> Optional[dict]:
        return cache.get(CACHE_PREFIX + f'detail:{campaign_id}')

    def set_detail(self, campaign_id: int, data: dict) -> None:
        cache.set(CACHE_PREFIX + f'detail:{campaign_id}', data, timeout=CACHE_TTL_DETAIL)

    def get_stats(self, campaign_id: int) -> Optional[dict]:
        return cache.get(CACHE_PREFIX + f'stats:{campaign_id}')

    def set_stats(self, campaign_id: int, stats: dict) -> None:
        cache.set(CACHE_PREFIX + f'stats:{campaign_id}', stats, timeout=CACHE_TTL_STATS)

    def get_eligible_for_worker(self, user_id: int, platform: str) -> Optional[list]:
        return cache.get(CACHE_PREFIX + f'worker:{user_id}:eligible:{platform}')

    def set_eligible_for_worker(self, user_id: int, platform: str, campaigns: list) -> None:
        cache.set(CACHE_PREFIX + f'worker:{user_id}:eligible:{platform}', campaigns, timeout=60)

    def invalidate_campaign(self, campaign_id: int) -> None:
        """Campaign update হলে সব related cache clear করে।"""
        keys = [
            CACHE_PREFIX + f'detail:{campaign_id}',
            CACHE_PREFIX + f'stats:{campaign_id}',
            CACHE_PREFIX + 'active:all:all',
        ]
        cache.delete_many(keys)
        # Clear platform-specific active cache
        for platform in ['youtube', 'facebook', 'instagram', 'tiktok', 'play_store']:
            cache.delete(CACHE_PREFIX + f'active:{platform}:all')
        logger.debug(f'Campaign cache invalidated: {campaign_id}')

    def invalidate_all(self) -> None:
        """Full cache flush — emergency use only।"""
        from django.core.cache import caches
        try:
            caches['default'].clear()
            logger.warning('Campaign cache fully cleared')
        except Exception as e:
            logger.error(f'Cache clear failed: {e}')

    def get_or_set_detail(self, campaign_id: int, fetcher) -> dict:
        """Cache-aside pattern — miss হলে fetcher call করে।"""
        data = self.get_detail(campaign_id)
        if data is None:
            data = fetcher(campaign_id)
            if data:
                self.set_detail(campaign_id, data)
        return data

    def increment_view_count(self, campaign_id: int) -> int:
        """Atomic view counter।"""
        key = CACHE_PREFIX + f'views:{campaign_id}'
        try:
            return cache.incr(key)
        except Exception:
            cache.set(key, 1, timeout=86400)
            return 1

    def get_popular_campaigns(self, limit: int = 10) -> list:
        """View count দিয়ে popular campaigns।"""
        return cache.get(CACHE_PREFIX + f'popular:{limit}') or []

    def set_popular_campaigns(self, campaigns: list, limit: int = 10) -> None:
        cache.set(CACHE_PREFIX + f'popular:{limit}', campaigns, timeout=300)


# Singleton
campaign_cache = CampaignCache()
