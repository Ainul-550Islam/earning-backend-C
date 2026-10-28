# api/support/signals_sla.py
"""SLA-specific signals."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.TicketSLA')
def on_sla_post_save(sender, instance, created, **kwargs):
    """When SLA record saved — check breach and fire events."""
    if created:
        return
    if instance.first_response_breached or instance.resolution_breached:
        try:
            from api.support.notifications import notification_service
            breach_type = 'first_response' if instance.first_response_breached else 'resolution'
            notification_service.notify_sla_breach(instance.ticket, breach_type)
        except Exception as e:
            logger.debug(f'on_sla_post_save notify: {e}')
        try:
            from api.support.webhooks import webhook_sender
            breach_type = 'first_response' if instance.first_response_breached else 'resolution'
            webhook_sender.send_sla_breach(instance.ticket, breach_type)
        except Exception as e:
            logger.debug(f'on_sla_post_save webhook: {e}')


@receiver(post_save, sender='support.SLABreach')
def on_sla_breach_created(sender, instance, created, **kwargs):
    """When SLA breach record created — log to audit."""
    if not created:
        return
    try:
        from api.support.integrations.project_specific.audit_log_bridge import audit_bridge
        audit_bridge.log_sla_breach(instance.ticket, instance.breach_type)
    except Exception as e:
        logger.debug(f'on_sla_breach_created audit: {e}')