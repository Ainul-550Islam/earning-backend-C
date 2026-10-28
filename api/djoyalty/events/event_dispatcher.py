# api/djoyalty/events/event_dispatcher.py
"""
Djoyalty -- EventDispatcher।
Internal event dispatch -> webhook + logging।
"""
import logging
from .loyalty_events import LoyaltyEvent

logger = logging.getLogger(__name__)


class EventDispatcher:
    """
    Loyalty event dispatcher।
    Signal handlers থেকে call হয়।
    Webhooks + notifications trigger করে।
    """

    @staticmethod
    def dispatch(event_type: str, customer=None, data: dict = None, tenant=None):
        """
        Event dispatch করো।

        Args:
            event_type: Event type string (e.g. 'points.earned')
            customer: Customer model instance
            data: Event payload data dict
            tenant: Tenant instance (optional)
        """
        event = LoyaltyEvent(
            event_type=event_type,
            customer=customer,
            tenant=tenant or (getattr(customer, 'tenant', None) if customer else None),
            data=data or {},
        )

        # Webhook dispatch
        try:
            from ..webhooks.webhook_dispatcher import WebhookDispatcher
            WebhookDispatcher.dispatch(event)
        except Exception as e:
            logger.warning('EventDispatcher webhook error for %s: %s', event_type, e)

        # Notification trigger (non-blocking)
        try:
            EventDispatcher._trigger_notification(event)
        except Exception as e:
            logger.debug('EventDispatcher notification error for %s: %s', event_type, e)

        logger.debug('EventDispatcher: dispatched %s for customer=%s', event_type, customer)
        return event

    @staticmethod
    def _trigger_notification(event: LoyaltyEvent):
        """
        Relevant events এ notification create করো।
        """
        notif_events = {
            'points.expired': 'expiry',
            'tier.upgraded': 'tier_up',
            'tier.downgraded': 'tier_down',
            'badge.unlocked': 'badge',
            'streak.milestone': 'streak',
            'challenge.completed': 'challenge',
            'campaign.joined': 'campaign',
        }
        notif_type = notif_events.get(event.event_type)
        if not notif_type or not event.customer:
            return

        try:
            from ..models.advanced import LoyaltyNotification
            message = EventDispatcher._build_notification_message(event)
            LoyaltyNotification.objects.create(
                customer=event.customer,
                tenant=event.tenant,
                notification_type=notif_type,
                message=message,
                is_sent=False,
            )
        except Exception as e:
            logger.debug('EventDispatcher._trigger_notification error: %s', e)

    @staticmethod
    def _build_notification_message(event: LoyaltyEvent) -> str:
        data = event.data or {}
        if event.event_type == 'points.expired':
            return f"Your {data.get('points', '')} points have expired."
        elif event.event_type == 'tier.upgraded':
            return f"Congratulations! You've been upgraded to {data.get('to_tier', '')} tier."
        elif event.event_type == 'tier.downgraded':
            return f"Your tier has been updated to {data.get('to_tier', '')}."
        elif event.event_type == 'badge.unlocked':
            return f"You've unlocked the '{data.get('badge', '')}' badge!"
        elif event.event_type == 'streak.milestone':
            return f"Amazing! You've reached a {data.get('milestone_days', '')}-day streak!"
        elif event.event_type == 'challenge.completed':
            return f"Challenge completed! You've earned {data.get('points', '')} bonus points."
        return f"Loyalty update: {event.event_type}"
