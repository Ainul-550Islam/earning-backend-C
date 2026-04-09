# api/djoyalty/events/event_middleware.py
"""
Django middleware to attach loyalty event context to each request।
"""
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class LoyaltyEventMiddleware(MiddlewareMixin):
    """
    Middleware that provides per-request loyalty event tracking।
    Attach to MIDDLEWARE in settings.py if needed.
    """

    def process_request(self, request):
        """Initialize event queue for this request।"""
        request._loyalty_events = []

    def process_response(self, request, response):
        """Flush any queued loyalty events after response is ready।"""
        events = getattr(request, '_loyalty_events', [])
        if events:
            logger.debug('Flushing %d loyalty events after response', len(events))
            for event in events:
                try:
                    from .event_dispatcher import EventDispatcher
                    EventDispatcher.dispatch(
                        event['event_type'],
                        customer=event.get('customer'),
                        data=event.get('data', {}),
                    )
                except Exception as e:
                    logger.error('Event flush error: %s', e)
        return response

    @staticmethod
    def queue_event(request, event_type: str, customer=None, data: dict = None):
        """Queue a loyalty event to be dispatched after the response।"""
        if hasattr(request, '_loyalty_events'):
            request._loyalty_events.append({
                'event_type': event_type,
                'customer': customer,
                'data': data or {},
            })
        else:
            try:
                from .event_dispatcher import EventDispatcher
                EventDispatcher.dispatch(event_type, customer=customer, data=data or {})
            except Exception as e:
                logger.error('Direct event dispatch error: %s', e)
