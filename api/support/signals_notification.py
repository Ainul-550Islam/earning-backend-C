# api/support/signals_notification.py
"""Notification-specific signals — fire after ticket events."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.TicketMessage')
def on_message_notify(sender, instance, created, **kwargs):
    """When agent posts a reply — notify user via push."""
    if not created or not instance.is_agent or instance.is_internal:
        return
    try:
        from api.support.notifications_push import push_notifications
        push_notifications.push_ticket_replied(instance.ticket)
    except Exception as e:
        logger.debug(f'on_message_notify push: {e}')

    try:
        from api.support.notifications import notification_service
        notification_service.notify_ticket_replied(
            instance.ticket,
            instance.content[:200]
        )
    except Exception as e:
        logger.debug(f'on_message_notify email: {e}')