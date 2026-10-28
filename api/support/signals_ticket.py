# api/support/signals_ticket.py
"""Ticket-specific Django signals."""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='support.SupportTicket')
def on_ticket_pre_save(sender, instance, **kwargs):
    """Before ticket save — ensure ticket_id is set."""
    if not instance.ticket_id:
        from api.support.logic import generate_ticket_id
        instance.ticket_id = generate_ticket_id()


@receiver(post_save, sender='support.SupportTicket')
def on_ticket_created_analytics(sender, instance, created, **kwargs):
    """Track new ticket in analytics."""
    if not created:
        return
    try:
        from api.support.analytics import support_analytics
        support_analytics.track_ticket_created(instance)
    except Exception as e:
        logger.debug(f'on_ticket_created_analytics: {e}')


@receiver(post_save, sender='support.SupportTicket')
def on_ticket_resolved_analytics(sender, instance, created, **kwargs):
    """Track ticket resolution in analytics."""
    if created or instance.status not in ('resolved', 'closed'):
        return
    try:
        from api.support.analytics import support_analytics
        from api.support.logic import get_ticket_wait_hours
        hours = get_ticket_wait_hours(instance)
        support_analytics.track_ticket_resolved(instance, resolution_hours=hours)
    except Exception as e:
        logger.debug(f'on_ticket_resolved_analytics: {e}')


@receiver(post_save, sender='support.SupportTicket')
def on_ticket_status_changed_cache(sender, instance, created, **kwargs):
    """Invalidate caches when ticket status changes."""
    if created:
        return
    try:
        from api.support.cache import invalidate_stats, invalidate_user_tickets
        invalidate_stats(getattr(instance, 'tenant', None))
        if instance.user:
            invalidate_user_tickets(instance.user_id)
    except Exception as e:
        logger.debug(f'on_ticket_status_changed_cache: {e}')