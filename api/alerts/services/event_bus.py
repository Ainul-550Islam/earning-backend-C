# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging
from django.dispatch import Signal
from django.db import transaction

logger = logging.getLogger(__name__)

# Define custom signals
alert_triggered = Signal()
alert_resolved = Signal()
alert_escalated = Signal()
notification_sent = Signal()
rule_created = Signal()


class EventService:
    """
    Consolidates event handling logic.
    Eliminates duplicates from: event_bus.py + integration/event_bus.py
    """

    _handlers = {}

    @staticmethod
    def register_handler(event_type, handler):
        """
        Register an event handler.
        
        Args:
            event_type: Type of event ('alert_triggered', 'alert_resolved', etc.)
            handler: Callable that handles the event
        """
        if event_type not in EventService._handlers:
            EventService._handlers[event_type] = []
        
        EventService._handlers[event_type].append(handler)
        logger.info(f"Registered handler for event: {event_type}")

    @staticmethod
    @transaction.atomic
    def emit_event(event_type, **kwargs):
        """
        Emit an event.
        
        Previously duplicated in:
        - alerts/event_bus.py
        - alerts/integration/event_bus.py
        
        Args:
            event_type: Type of event
            **kwargs: Event data
        """
        logger.info(f"Emitting event: {event_type}")
        
        # Call registered handlers
        if event_type in EventService._handlers:
            for handler in EventService._handlers[event_type]:
                try:
                    handler(**kwargs)
                except Exception as e:
                    logger.error(f"Error calling handler for {event_type}: {str(e)}")
        
        # Send Django signal
        if event_type == 'alert_triggered':
            alert_triggered.send(sender=None, **kwargs)
        elif event_type == 'alert_resolved':
            alert_resolved.send(sender=None, **kwargs)
        elif event_type == 'alert_escalated':
            alert_escalated.send(sender=None, **kwargs)
        elif event_type == 'notification_sent':
            notification_sent.send(sender=None, **kwargs)
        elif event_type == 'rule_created':
            rule_created.send(sender=None, **kwargs)
        
        logger.info(f"Event {event_type} emitted successfully")

    @staticmethod
    def handle_alert_triggered(alert):
        """Handle alert triggered event"""
        logger.info(f"Alert triggered: {alert.id}")
        EventService.emit_event('alert_triggered', alert=alert)

    @staticmethod
    def handle_alert_resolved(alert):
        """Handle alert resolved event"""
        logger.info(f"Alert resolved: {alert.id}")
        EventService.emit_event('alert_resolved', alert=alert)

    @staticmethod
    def handle_alert_escalated(alert, escalation_level):
        """Handle alert escalated event"""
        logger.info(f"Alert escalated: {alert.id} to level {escalation_level}")
        EventService.emit_event('alert_escalated', alert=alert, level=escalation_level)

    @staticmethod
    def handle_notification_sent(notification):
        """Handle notification sent event"""
        logger.info(f"Notification sent: {notification.id}")
        EventService.emit_event('notification_sent', notification=notification)

    @staticmethod
    def get_event_history(event_type=None, limit=100):
        """Get event history"""
        from api.alerts.models import EventLog
        
        query = EventLog.objects.all()
        
        if event_type:
            query = query.filter(event_type=event_type)
        
        return list(query.order_by('-created_at')[:limit])


__all__ = ['EventService', 'alert_triggered', 'alert_resolved', 'alert_escalated']
