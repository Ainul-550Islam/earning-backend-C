# api/support/signals/sla_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.TicketSLA')
def on_sla_save(sender, instance, created, **kwargs):
    """On SLA breach detected → notify + escalate."""
    if not created:
        if instance.first_response_breached or instance.resolution_breached:
            try:
                from api.support.services import notify_sla_breach
                breach_type = "first_response" if instance.first_response_breached else "resolution"
                notify_sla_breach(instance.ticket, breach_type)
            except Exception as e:
                logger.warning(f"SLA breach notification failed: {e}")
            # Auto-escalate
            try:
                ticket = instance.ticket
                if not ticket.escalated:
                    ticket.escalated = True
                    from django.utils import timezone
                    ticket.escalated_at = timezone.now()
                    ticket.save(update_fields=["escalated","escalated_at"])
            except Exception:
                pass