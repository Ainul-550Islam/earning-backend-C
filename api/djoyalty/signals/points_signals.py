# api/djoyalty/signals/points_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(post_save, sender='djoyalty.PointsLedger')
def on_points_ledger_created(sender, instance, created, **kwargs):
    if created:
        try:
            from ..events.event_dispatcher import EventDispatcher
            EventDispatcher.dispatch(
                'points.earned' if instance.txn_type == 'credit' else 'points.burned',
                customer=instance.customer,
                data={'points': str(instance.points), 'source': instance.source},
            )
        except Exception as e:
            logger.warning('points_signals error: %s', e)
