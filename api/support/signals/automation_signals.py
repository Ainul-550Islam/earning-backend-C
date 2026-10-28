# api/support/signals/automation_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.SupportTicket')
def on_ticket_for_automation(sender, instance, created, **kwargs):
    """Fire automation engine on every ticket save."""
    trigger = "ticket_created" if created else "ticket_updated"
    try:
        from api.support.automation.trigger_engine import trigger_engine
        trigger_engine.fire(trigger, ticket=instance)
    except Exception as e:
        logger.debug(f"Automation signal [{trigger}] failed: {e}")