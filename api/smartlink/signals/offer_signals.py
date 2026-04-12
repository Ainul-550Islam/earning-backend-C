import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import OfferCapTracker

logger = logging.getLogger('smartlink.signals.offer')


@receiver(post_save, sender=OfferCapTracker)
def on_cap_reached(sender, instance, **kwargs):
    """When an offer cap is reached: invalidate the offer pool cache."""
    if instance.is_capped:
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
