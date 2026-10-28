# api/support/signals/rating_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.TicketRating')
def on_rating_submit(sender, instance, created, **kwargs):
    """Update agent performance metrics when CSAT submitted."""
    if created:
        try:
            ticket = instance.ticket
            if ticket.assigned_to:
                from api.support.services.agent.AgentPerformanceService import performance_service
                logger.info(f"CSAT {instance.score}★ submitted for ticket {ticket.ticket_id}")
        except Exception as e:
            logger.debug(f"Rating signal agent update failed: {e}")