# api/djoyalty/signals/badge_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(post_save, sender='djoyalty.UserBadge')
def on_badge_unlocked(sender, instance, created, **kwargs):
    if created:
        try:
            from ..events.event_dispatcher import EventDispatcher
            EventDispatcher.dispatch(
                'badge.unlocked',
                customer=instance.customer,
                data={'badge': instance.badge.name, 'icon': instance.badge.icon},
            )
        except Exception as e:
            logger.warning('badge_signals error: %s', e)
