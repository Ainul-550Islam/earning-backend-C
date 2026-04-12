import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import Click

logger = logging.getLogger('smartlink.signals.conversion')


@receiver(post_save, sender=Click)
def on_conversion(sender, instance, created, **kwargs):
    """When a click is marked as converted: fire postback pixel and update stats."""
    if not created and instance.is_converted and float(instance.payout) > 0:
        try:
            from ..tasks.epc_update_tasks import update_epc_for_smartlink
            update_epc_for_smartlink.delay(instance.smartlink_id)
        except Exception as e:
            logger.warning(f"Conversion signal EPC update failed: {e}")
