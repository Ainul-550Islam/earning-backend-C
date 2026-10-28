# api/support/tasks/csat_tasks.py  — WORLD #1 COMPLETE
"""CSAT rating request tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.csat_tasks.send_csat_rating_requests")
def send_csat_rating_requests():
    """Daily — send CSAT requests to users whose ticket was resolved 24h ago."""
    from api.support.models import SupportTicket
    from api.support.services import notification_service
    since_24h = timezone.now() - timedelta(hours=24)
    since_48h = timezone.now() - timedelta(hours=48)
    tickets = SupportTicket.objects.filter(
        status="resolved",
        resolved_at__gte=since_48h,
        resolved_at__lte=since_24h,
        satisfaction_rating__isnull=True,
    ).select_related("user")
    sent = 0
    for ticket in tickets[:100]:
        try:
            notification_service._send_email(
                to      = ticket.user.email,
                subject = f"Rate your support experience — #{ticket.ticket_id}",
                body    = (
                    f"Hello {ticket.user.username},\n\n"
                    f"Your ticket #{ticket.ticket_id} was resolved.\n"
                    f"Please rate us (1-5): {ticket.ticket_id}\n\n"
                    f"Thank you!\n{logger.name}"
                )
            )
            sent += 1
        except Exception as e:
            logger.error(f"CSAT request failed for {ticket.ticket_id}: {e}")
    logger.info(f"CSAT requests sent: {sent}")
    return {"sent": sent}

@shared_task(name="support.tasks.csat_tasks.send_single_csat_request")
def send_single_csat_request(ticket_id: int):
    """Send CSAT request for a single ticket (delayed by 24h)."""
    try:
        from api.support.models import SupportTicket
        from api.support.notifications.email_notifier import email_notifier
        ticket = SupportTicket.objects.get(id=ticket_id)
        if not ticket.satisfaction_rating:
            email_notifier.csat_request(ticket)
        return {"sent": True}
    except Exception as e:
        logger.error(f"Single CSAT request failed: {e}")
        return {"error": str(e)}