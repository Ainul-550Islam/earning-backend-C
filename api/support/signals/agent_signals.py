# api/support/signals/agent_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.AgentStatus')
def on_agent_status_change(sender, instance, created, **kwargs):
    """When agent comes online → rebalance unassigned tickets."""
    if instance.status in ("online", "available"):
        try:
            from api.support.tasks.assignment_tasks import auto_assign_unassigned_tickets
            auto_assign_unassigned_tickets.apply_async(countdown=2)
        except Exception as e:
            logger.debug(f"Rebalance on agent online failed: {e}")