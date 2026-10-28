# api/support/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.SupportTicket')
def on_ticket_post_save(sender, instance, created, **kwargs):
    if not created:
        if instance.status in ('resolved', 'closed') and not instance.resolved_at:
            sender.objects.filter(pk=instance.pk).update(resolved_at=timezone.now())
    try:
        from api.support.integrations.integ_handler import integ_handler
        if created:
            integ_handler.on_ticket_created(instance)
        elif instance.status == 'resolved':
            integ_handler.on_ticket_resolved(instance)
    except Exception as e:
        logger.debug(f'Integration event: {e}')


@receiver(post_save, sender='support.TicketSLA')
def on_sla_update(sender, instance, created, **kwargs):
    if not created and (instance.first_response_breached or instance.resolution_breached):
        try:
            from api.support.integrations.integ_handler import integ_handler
            breach_type = 'first_response' if instance.first_response_breached else 'resolution'
            integ_handler.on_sla_breach(instance.ticket, breach_type)
        except Exception as e:
            logger.debug(f'SLA breach event: {e}')


@receiver(post_save, sender='support.TicketMessage')
def on_message_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from api.support.models import SupportTicket
        SupportTicket.objects.filter(pk=instance.ticket_id).update(
            message_count=instance.ticket.messages.count()
        )
    except Exception:
        pass
    if not instance.is_agent:
        try:
            from api.support.integrations.project_specific.ai_sentiment_realtime import sentiment_analyzer
            sentiment_analyzer.on_message_received(instance.ticket, instance.content)
        except Exception:
            pass