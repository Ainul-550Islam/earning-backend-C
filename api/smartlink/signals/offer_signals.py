import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.smartlink.models import OfferCapTracker

logger = logging.getLogger('smartlink.signals.offer')


@receiver(post_save, sender=OfferCapTracker)
def on_cap_reached(sender, instance, **kwargs):
    """
    When an offer cap is reached:
    1. Invalidate offer pool cache (was already wired)
    2. Warm the updated pool cache       ← FIX: was missing (cache left stale)
    3. Fire webhook 'cap_reached' event  ← FIX: was missing
    4. Notify publisher                  ← FIX: was missing
    5. Fire alert_cap_nearly_reached when approaching ← FIX: was missing
    """
    if not instance.is_capped:
        # Check if approaching cap (>= 80%) — alert before it's too late
        if instance.cap_limit and instance.clicks_count >= instance.cap_limit * 0.8:
            try:
                from ..tasks.cap_reset_tasks import alert_cap_nearly_reached
                alert_cap_nearly_reached.delay(
                    pool_entry_id=instance.pool_entry_id,
                    used=instance.clicks_count,
                    limit=instance.cap_limit,
                )
            except Exception as e:
                logger.warning(f"Cap nearly-reached alert task failed: {e}")
        return

    # 1. Invalidate pool cache (was already wired)
    try:
        from ..services.core.SmartLinkCacheService import SmartLinkCacheService
        sl_id = instance.pool_entry.pool.smartlink_id
        SmartLinkCacheService().invalidate_offer_pool(sl_id)
        logger.info(
            f"Offer cap reached: offer#{instance.pool_entry.offer_id} "
            f"pool cache invalidated for sl#{sl_id}"
        )
    except Exception as e:
        logger.warning(f"Cap signal cache invalidation failed: {e}")

    # 2. Warm updated pool cache — FIX: was missing
    try:
        from ..tasks.cache_warmup_tasks import warmup_offer_pool_cache
        warmup_offer_pool_cache.delay(instance.pool_entry.pool.smartlink_id)
    except Exception as e:
        logger.warning(f"Cap signal pool warmup failed: {e}")

    # 3. Webhook dispatch — FIX: was completely missing
    try:
        from ..tasks.webhook_tasks import deliver_webhook_event
        sl = instance.pool_entry.pool.smartlink
        publisher = sl.publisher
        deliver_webhook_event.delay(
            event='cap_reached',
            publisher_id=publisher.pk,
            smartlink_id=sl.pk,
            offer_id=str(instance.pool_entry.offer_id),
            cap_limit=instance.cap_limit,
            clicks_used=instance.clicks_count,
            period=instance.period if hasattr(instance, 'period') else 'daily',
        )
    except Exception as e:
        logger.warning(f"Cap signal webhook dispatch failed: {e}")

    # 4. Publisher notification — FIX: was missing
    try:
        from ..services.notification.NotificationService import NotificationService
        sl = instance.pool_entry.pool.smartlink
        publisher = sl.publisher
        NotificationService().notify_cap_reached(
            publisher=publisher,
            smartlink=sl,
            offer=instance.pool_entry.offer,
            usage={
                'clicks_used': instance.clicks_count,
                'cap_limit': instance.cap_limit,
            },
        )
    except Exception as e:
        logger.warning(f"Cap signal notification failed: {e}")
