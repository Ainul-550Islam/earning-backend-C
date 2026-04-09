# api/djoyalty/signals/tier_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(post_save, sender='djoyalty.TierHistory')
def on_tier_changed(sender, instance, created, **kwargs):
    if created:
        try:
            from ..events.event_dispatcher import EventDispatcher
            EventDispatcher.dispatch(
                'tier.changed',
                customer=instance.customer,
                data={
                    'from_tier': instance.from_tier.name if instance.from_tier else None,
                    'to_tier': instance.to_tier.name,
                    'change_type': instance.change_type,
                },
            )
        except Exception as e:
            logger.warning('tier_signals error: %s', e)
