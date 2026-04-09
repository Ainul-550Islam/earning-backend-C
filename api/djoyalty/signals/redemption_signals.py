# api/djoyalty/signals/redemption_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(post_save, sender='djoyalty.RedemptionRequest')
def on_redemption_status_changed(sender, instance, created, **kwargs):
    if not created:
        try:
            from ..events.event_dispatcher import EventDispatcher
            EventDispatcher.dispatch(
                'redemption.status_changed',
                customer=instance.customer,
                data={'status': instance.status, 'points_used': str(instance.points_used)},
            )
        except Exception as e:
            logger.warning('redemption_signals error: %s', e)
