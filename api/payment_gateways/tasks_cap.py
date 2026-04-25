# api/payment_gateways/tasks_cap.py
# Celery tasks for capacity management

from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


@shared_task
def reset_daily_offer_caps():
    """Reset daily conversion caps for all offers at midnight."""
    from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
    reactivated = ConversionCapEngine().reset_daily_caps()
    logger.info(f'Daily cap reset: {reactivated} offers reactivated')
    return {'reactivated': reactivated}


@shared_task
def check_queue_depths():
    """Alert if any queue depth exceeds 80%."""
    from api.payment_gateways.integration_system.message_queue import message_queue
    from api.payment_gateways.integration_system.integ_constants import MAX_QUEUE_SIZE
    depths  = message_queue.get_all_depths()
    alerts  = []
    for name, d in depths.items():
        if d.get('pct_full', 0) >= 80:
            alerts.append(f'{name}: {d["total"]}/{MAX_QUEUE_SIZE} ({d["pct_full"]}%)')
            from api.payment_gateways.signals_cap import emit_cap_reached
    if alerts:
        logger.warning(f'Queue depth alerts: {alerts}')
    return {'alerts': len(alerts)}


@shared_task
def reprocess_dlq_messages():
    """Re-process failed messages from Dead Letter Queue."""
    from api.payment_gateways.integration_system.event_bus import event_bus
    replayed = 0
    for event_type in ['deposit.completed', 'withdrawal.processed', 'conversion.approved']:
        replayed += event_bus.replay_failed(event_type)
    logger.info(f'DLQ reprocessed: {replayed} messages')
    return {'replayed': replayed}
