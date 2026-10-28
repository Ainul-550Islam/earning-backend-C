# api/support/signals/core_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.SupportTicket')
def ticket_saved(sender, instance, created, **kwargs):
    if created:
        logger.info(f"New ticket created: {instance.ticket_id}")
    else:
        if instance.status in ('resolved','closed') and not instance.resolved_at:
            sender.objects.filter(pk=instance.pk).update(resolved_at=timezone.now())