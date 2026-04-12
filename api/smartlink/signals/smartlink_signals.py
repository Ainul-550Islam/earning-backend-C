import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from ..models import SmartLink

logger = logging.getLogger('smartlink.signals')


@receiver(post_save, sender=SmartLink)
def on_smartlink_save(sender, instance, created, **kwargs):
    """On SmartLink create/update: invalidate Redis cache."""
    from ..tasks.cache_warmup_tasks import invalidate_smartlink_cache
    try:
        invalidate_smartlink_cache.delay(instance.slug)
    except Exception as e:
        logger.warning(f"Cache invalidation signal failed for [{instance.slug}]: {e}")

    if created:
        logger.info(f"SmartLink created: [{instance.slug}] by publisher#{instance.publisher_id}")
    else:
        logger.debug(f"SmartLink updated: [{instance.slug}]")


@receiver(post_delete, sender=SmartLink)
def on_smartlink_delete(sender, instance, **kwargs):
    """On SmartLink delete: clear all cache entries."""
    from ..services.core.SmartLinkCacheService import SmartLinkCacheService
    SmartLinkCacheService().invalidate_smartlink(instance.slug)
    logger.info(f"SmartLink deleted: [{instance.slug}]")


@receiver(pre_save, sender=SmartLink)
def on_smartlink_slug_change(sender, instance, **kwargs):
    """If slug changed: invalidate old slug cache too."""
    if instance.pk:
        try:
            old = SmartLink.objects.get(pk=instance.pk)
            if old.slug != instance.slug:
                from ..services.core.SmartLinkCacheService import SmartLinkCacheService
                SmartLinkCacheService().invalidate_smartlink(old.slug)
                logger.info(f"Slug changed: [{old.slug}] → [{instance.slug}], old cache cleared")
        except SmartLink.DoesNotExist:
            pass
