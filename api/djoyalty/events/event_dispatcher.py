# api/djoyalty/events/event_dispatcher.py
import logging
from .loyalty_events import LoyaltyEvent
from .event_registry import EventRegistry

logger = logging.getLogger(__name__)

class EventDispatcher:
    @staticmethod
    def dispatch(event_type: str, customer=None, tenant=None, data=None):
        event = LoyaltyEvent(
            event_type=event_type,
            customer=customer,
            tenant=tenant or (customer.tenant if customer else None),
            data=data or {},
        )
        handlers = EventRegistry.get_handlers(event_type)
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error('EventDispatcher handler error [%s]: %s', event_type, e)
        try:
            from ..webhooks.webhook_dispatcher import WebhookDispatcher
            WebhookDispatcher.dispatch(event)
        except Exception as e:
            logger.debug('Webhook dispatch skipped: %s', e)
        return event
