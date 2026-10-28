# api/support/signals_agent.py
"""Agent-specific signals."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.SupportAgent')
def on_agent_created(sender, instance, created, **kwargs):
    """When agent profile created — create AgentStatus record."""
    if not created:
        return
    try:
        from api.support.models import AgentStatus
        AgentStatus.objects.get_or_create(
            agent=instance,
            defaults={'status': 'offline'},
        )
        logger.info(f'AgentStatus created for {instance.user.username}')
    except Exception as e:
        logger.debug(f'on_agent_created: {e}')


@receiver(post_save, sender='support.AgentStatus')
def on_agent_status_changed(sender, instance, created, **kwargs):
    """When agent status changes — update availability."""
    if created:
        return
    try:
        agent = instance.agent
        is_available = instance.status == 'online'
        if agent.is_available != is_available:
            from api.support.models import SupportAgent
            SupportAgent.objects.filter(pk=agent.pk).update(is_available=is_available)
    except Exception as e:
        logger.debug(f'on_agent_status_changed: {e}')