# api/referral/INTEGRATION_SYSTEM/message_queue.py
# High-traffic message queue manager — Celery-based
# Routes referral events to appropriate queues based on priority
# ============================================================

import logging
from typing import Any, Callable, Dict, List, Optional
from .integ_constants import (
    QUEUE_REFERRAL_HIGH, QUEUE_REFERRAL_NORMAL, QUEUE_REFERRAL_LOW,
    MAX_RETRIES, RETRY_BACKOFF,
    EVENT_TASK_COMPLETED, EVENT_OFFER_COMPLETED,
    EVENT_WITHDRAWAL_APPROVED, EVENT_USER_REGISTERED,
    EVENT_FRAUD_CONFIRMED,
)

logger = logging.getLogger(__name__)

# Event → queue priority mapping
EVENT_QUEUE_MAP = {
    EVENT_TASK_COMPLETED:       QUEUE_REFERRAL_HIGH,    # Commission must be fast
    EVENT_OFFER_COMPLETED:      QUEUE_REFERRAL_HIGH,
    EVENT_FRAUD_CONFIRMED:      QUEUE_REFERRAL_HIGH,    # Clawback is urgent
    EVENT_USER_REGISTERED:      QUEUE_REFERRAL_HIGH,    # Signup bonus must be fast
    EVENT_WITHDRAWAL_APPROVED:  QUEUE_REFERRAL_NORMAL,
    'referral.commission.held': QUEUE_REFERRAL_NORMAL,
    'referral.milestone.check': QUEUE_REFERRAL_NORMAL,
    'referral.ltv.recalc':      QUEUE_REFERRAL_LOW,
    'referral.analytics':       QUEUE_REFERRAL_LOW,
    'referral.cleanup':         QUEUE_REFERRAL_LOW,
    'referral.export':          QUEUE_REFERRAL_LOW,
}


class ReferralMessageQueue:
    """
    High-traffic message queue manager.
    Routes referral events to Celery queues based on priority.
    Falls back to synchronous processing if Celery unavailable.
    """

    _celery_available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Celery is available."""
        if self._celery_available is not None:
            return self._celery_available
        try:
            from celery import current_app
            current_app.control.inspect().active()
            ReferralMessageQueue._celery_available = True
        except Exception:
            ReferralMessageQueue._celery_available = False
        return ReferralMessageQueue._celery_available

    def get_queue_for_event(self, event: str) -> str:
        """Determine which Celery queue to use for an event."""
        return EVENT_QUEUE_MAP.get(event, QUEUE_REFERRAL_NORMAL)

    def enqueue(self, event: str, queue: str = None, **kwargs) -> bool:
        """
        Enqueue an event for processing.
        Returns True if successfully enqueued.
        """
        target_queue = queue or self.get_queue_for_event(event)

        try:
            from api.referral.INTEGRATION_SYSTEM.queue_tasks import (
                process_referral_event
            )
            process_referral_event.apply_async(
                kwargs={'event': event, **{k: _serialize(v) for k, v in kwargs.items()}},
                queue=target_queue,
                retry=True,
                retry_policy={
                    'max_retries': MAX_RETRIES,
                    'interval_start': RETRY_BACKOFF,
                    'interval_step': 30,
                    'interval_max': 300,
                },
            )
            logger.debug(f'[MQ] Enqueued: {event} → {target_queue}')
            return True

        except Exception as e:
            logger.error(f'[MQ] Enqueue failed for {event}: {e}')
            return False

    def enqueue_commission(
        self,
        earner_id: int,
        earned_amount: str,
        source_type: str,
        source_id: str = '',
    ) -> bool:
        """
        Enqueue a commission calculation task.
        Used for high-volume commission processing.
        """
        try:
            from api.referral.tasks.commission_processing_tasks import (
                process_single_commission_event
            )
            process_single_commission_event.apply_async(
                kwargs={
                    'earner_id': earner_id,
                    'earned_amount': str(earned_amount),
                    'source_type': source_type,
                    'source_id': source_id,
                },
                queue=QUEUE_REFERRAL_HIGH,
            )
            return True
        except Exception as e:
            logger.error(f'[MQ] enqueue_commission failed: {e}')
            return False

    def enqueue_handlers(
        self, event: str, handlers: List[Callable], kwargs: dict
    ) -> int:
        """Enqueue multiple handlers for an event."""
        queued = 0
        for handler in handlers:
            try:
                from api.referral.INTEGRATION_SYSTEM.queue_tasks import (
                    run_event_handler
                )
                queue = self.get_queue_for_event(event)
                run_event_handler.apply_async(
                    kwargs={
                        'handler_module': handler.__module__,
                        'handler_name': handler.__name__,
                        'event': event,
                        'kwargs': {k: _serialize(v) for k, v in kwargs.items()},
                    },
                    queue=queue,
                )
                queued += 1
            except Exception as e:
                logger.error(f'[MQ] enqueue_handlers error for {handler.__name__}: {e}')
        return queued

    def enqueue_batch(self, events: List[Dict]) -> int:
        """Batch enqueue multiple events."""
        queued = 0
        for event_data in events:
            event = event_data.pop('event', '')
            if event and self.enqueue(event, **event_data):
                queued += 1
        return queued

    def get_queue_length(self, queue: str = QUEUE_REFERRAL_HIGH) -> int:
        """Get approximate queue length (Redis-based)."""
        try:
            from django.core.cache import cache
            return int(cache.get(f'mq:len:{queue}', 0))
        except Exception:
            return -1

    def purge_queue(self, queue: str) -> bool:
        """Purge a specific queue (use with caution!)."""
        try:
            from celery import current_app
            current_app.control.purge()
            logger.warning(f'[MQ] Queue purged: {queue}')
            return True
        except Exception as e:
            logger.error(f'[MQ] purge_queue failed: {e}')
            return False


def _serialize(value: Any) -> Any:
    """Serialize values for Celery (IDs instead of objects)."""
    if hasattr(value, 'pk'):
        return {'__model__': value.__class__.__name__, 'pk': value.pk}
    if hasattr(value, 'id'):
        return {'__model__': value.__class__.__name__, 'id': value.id}
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    return str(value)


# ── Celery Tasks (queue_tasks.py helper) ──────────────────────────────────────
# These are registered as Celery tasks for message queue processing

try:
    from celery import shared_task

    @shared_task(
        name='referral.process_referral_event',
        bind=True, max_retries=MAX_RETRIES,
        queue=QUEUE_REFERRAL_NORMAL,
    )
    def process_referral_event(self, event: str, **kwargs) -> dict:
        """Process a referral event from the queue."""
        try:
            from api.referral.INTEGRATION_SYSTEM.event_bus import get_event_bus
            bus = get_event_bus()
            count = bus.publish(event, async_mode=False, **kwargs)
            return {'event': event, 'handlers_called': count}
        except Exception as exc:
            logger.error(f'[MQ Task] process_referral_event failed: {exc}')
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF)

    @shared_task(
        name='referral.run_event_handler',
        bind=True, max_retries=MAX_RETRIES,
    )
    def run_event_handler(
        self, handler_module: str, handler_name: str,
        event: str, kwargs: dict
    ) -> dict:
        """Run a specific event handler from the queue."""
        try:
            import importlib
            mod = importlib.import_module(handler_module)
            handler = getattr(mod, handler_name)
            handler(event=event, **kwargs)
            return {'status': 'ok', 'handler': handler_name}
        except Exception as exc:
            logger.error(f'[MQ Task] run_event_handler {handler_name} failed: {exc}')
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF)

    @shared_task(
        name='referral.process_single_commission_event',
        bind=True, max_retries=MAX_RETRIES,
        queue=QUEUE_REFERRAL_HIGH,
    )
    def process_single_commission_event(
        self, earner_id: int, earned_amount: str,
        source_type: str, source_id: str = ''
    ) -> dict:
        """Process a single commission event."""
        from decimal import Decimal
        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralService import ReferralService
            User = get_user_model()
            earner = User.objects.get(id=earner_id)
            results = ReferralService.process_multilevel_commission(
                earner=earner,
                earned_amount=Decimal(earned_amount),
                source_type=source_type,
                source_id=source_id,
            )
            return {'status': 'ok', 'commissions': len(results)}
        except Exception as exc:
            logger.error(f'[MQ Task] commission event failed: {exc}')
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF)

except ImportError:
    # Celery not available — tasks defined as stubs
    logger.debug('[MQ] Celery not available, queue tasks not registered')