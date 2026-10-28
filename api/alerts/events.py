"""
Event system for alerts app - handles event-driven architecture
"""
from django.dispatch import Signal, receiver
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
import logging

logger = logging.getLogger(__name__)

# Custom signals for alert events
alert_triggered = Signal()
alert_resolved = Signal()
alert_escalated = Signal()
notification_sent = Signal()
notification_failed = Signal()
rule_created = Signal()
rule_updated = Signal()
rule_deleted = Signal()
system_health_changed = Signal()
threshold_breached = Signal()
incident_created = Signal()
incident_resolved = Signal()


class AlertEventHandler:
    """Central handler for alert events"""
    
    @staticmethod
    def on_alert_triggered(sender, alert_log, **kwargs):
        """Handle alert triggered event"""
        logger.info(f"Alert triggered: {alert_log.id} - {alert_log.message}")
        
        # Trigger downstream processes
        from .services import NotificationService
        NotificationService.send_pending_notifications()
        
        # Check for escalation
        from .services import LegacyAlertProcessorService as AlertProcessorService
        (lambda: None)()  # process_alert moved to Celery task
    
    @staticmethod
    def on_alert_resolved(sender, alert_log, **kwargs):
        """Handle alert resolved event"""
        logger.info(f"Alert resolved: {alert_log.id}")
        
        # Update analytics
        from .services import AnalyticsService
        AnalyticsService.generate_daily_analytics()
        
        # Clear related caches
        from django.core.cache import cache
        cache.delete_pattern('alert_stats_*')
    
    @staticmethod
    def on_notification_sent(sender, notification, **kwargs):
        """Handle notification sent event"""
        logger.info(f"Notification sent: {notification.id} to {notification.recipient}")
        
        # Update metrics
        from .models import ChannelHealthLog
        ChannelHealthLog.log_successful_send(
            channel_type=notification.notification_type,
            recipient=notification.recipient
        )
    
    @staticmethod
    def on_notification_failed(sender, notification, error, **kwargs):
        """Handle notification failed event"""
        logger.error(f"Notification failed: {notification.id} - {error}")
        
        # Update channel health
        from .models import ChannelHealthLog
        ChannelHealthLog.log_failed_send(
            channel_type=notification.notification_type,
            recipient=notification.recipient,
            error_message=str(error)
        )
    
    @staticmethod
    def on_threshold_breached(sender, threshold_config, current_value, **kwargs):
        """Handle threshold breached event"""
        logger.warning(f"Threshold breached: {threshold_config.name} - {current_value}")
        
        # Create alert if rule exists
        if threshold_config.alert_rule:
            from .services import LegacyAlertProcessorService as AlertProcessorService
            try:
                AlertProcessorService.process_alert(
                    rule_id=threshold_config.alert_rule.id,
                    trigger_value=0, message="Threshold breached"
                )
            except Exception:
                pass


# Signal receivers
@receiver(alert_triggered)
def handle_alert_triggered(sender, alert_log, **kwargs):
    """Receiver for alert triggered signal"""
    AlertEventHandler.on_alert_triggered(sender, alert_log, **kwargs)


@receiver(alert_resolved)
def handle_alert_resolved(sender, alert_log, **kwargs):
    """Receiver for alert resolved signal"""
    AlertEventHandler.on_alert_resolved(sender, alert_log, **kwargs)


@receiver(notification_sent)
def handle_notification_sent(sender, notification, **kwargs):
    """Receiver for notification sent signal"""
    AlertEventHandler.on_notification_sent(sender, notification, **kwargs)


@receiver(notification_failed)
def handle_notification_failed(sender, notification, error, **kwargs):
    """Receiver for notification failed signal"""
    AlertEventHandler.on_notification_failed(sender, notification, error, **kwargs)


@receiver(threshold_breached)
def handle_threshold_breached(sender, threshold_config, current_value, **kwargs):
    """Receiver for threshold breached signal"""
    AlertEventHandler.on_threshold_breached(sender, threshold_config, current_value, **kwargs)


# Django model signal receivers
@receiver(post_save, sender='alerts.AlertRule')
def on_alert_rule_save(sender, instance, created, **kwargs):
    """Handle AlertRule save events"""
    if created:
        rule_created.send(sender=sender, rule=instance)
        logger.info(f"Alert rule created: {instance.name}")
    else:
        rule_updated.send(sender=sender, rule=instance)
        logger.info(f"Alert rule updated: {instance.name}")


@receiver(post_delete, sender='alerts.AlertRule')
def on_alert_rule_delete(sender, instance, **kwargs):
    """Handle AlertRule delete events"""
    rule_deleted.send(sender=sender, rule=instance)
    logger.info(f"Alert rule deleted: {instance.name}")


@receiver(post_save, sender='alerts.AlertLog')
def on_alert_log_save(sender, instance, created, **kwargs):
    """Handle AlertLog save events"""
    if created:
        alert_triggered.send(sender=sender, alert_log=instance)


@receiver(post_save, sender='alerts.Notification')
def on_notification_save(sender, instance, created, **kwargs):
    """Handle Notification save events"""
    if instance.status == 'sent':
        notification_sent.send(sender=sender, notification=instance)
    elif instance.status == 'failed':
        notification_failed.send(sender=sender, notification=instance, error=instance.error_message)


class EventAggregator:
    """Aggregates events for analytics and reporting"""
    
    def __init__(self):
        self.events = []
    
    def add_event(self, event_type, data):
        """Add event to aggregation"""
        self.events.append({
            'type': event_type,
            'data': data,
            'timestamp': timezone.now()
        })
    
    def get_events_by_type(self, event_type, hours=24):
        """Get events of specific type within time window"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return [
            event for event in self.events
            if event['type'] == event_type and event['timestamp'] >= cutoff
        ]
    
    def get_event_summary(self, hours=24):
        """Get summary of all events"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        recent_events = [
            event for event in self.events
            if event['timestamp'] >= cutoff
        ]
        
        summary = {}
        for event in recent_events:
            event_type = event['type']
            if event_type not in summary:
                summary[event_type] = 0
            summary[event_type] += 1
        
        return summary
