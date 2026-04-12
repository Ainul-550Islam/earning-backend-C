import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.cache')


@shared_task(name='smartlink.warmup_resolver_cache', queue='default')
def warmup_resolver_cache():
    """
    Every 5 minutes: pre-warm Redis cache for all active SmartLinks.
    Ensures <1ms cache hit rate on redirect requests.
    """
    from ..services.core.SmartLinkCacheService import SmartLinkCacheService
    svc = SmartLinkCacheService()
    count = svc.warmup_all_active()
    logger.info(f"Cache warmup complete: {count} SmartLinks cached")
    return {'cached': count}


@shared_task(name='smartlink.invalidate_smartlink_cache', queue='default')
def invalidate_smartlink_cache(slug: str):
    """Invalidate cache for a single SmartLink (fired on update signal)."""
    from ..services.core.SmartLinkCacheService import SmartLinkCacheService
    SmartLinkCacheService().invalidate_smartlink(slug)
    logger.debug(f"Cache invalidated for slug: {slug}")


@shared_task(name='smartlink.warmup_offer_pool_cache', queue='default')
def warmup_offer_pool_cache():
    """Pre-warm offer pool cache for all active SmartLinks."""
    from ..models import SmartLink
    from ..services.core.SmartLinkCacheService import SmartLinkCacheService
    svc = SmartLinkCacheService()
    active = SmartLink.objects.filter(is_active=True, is_archived=False)
    count = 0
    for sl in active:
        try:
            pool_entries = list(
                sl.offer_pool.entries.filter(is_active=True).select_related('offer')
            )
            svc.set_offer_pool(sl.pk, pool_entries)
            count += 1
        except Exception:
            pass
    logger.info(f"Offer pool cache warmed: {count} pools")
    return {'warmed': count}
