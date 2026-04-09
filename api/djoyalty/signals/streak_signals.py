# api/djoyalty/signals/streak_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(post_save, sender='djoyalty.StreakReward')
def on_streak_milestone(sender, instance, created, **kwargs):
    if created:
        try:
            from ..events.event_dispatcher import EventDispatcher
            EventDispatcher.dispatch(
                'streak.milestone',
                customer=instance.customer,
                data={'milestone_days': instance.milestone_days, 'points': str(instance.points_awarded)},
            )
        except Exception as e:
            logger.warning('streak_signals error: %s', e)
