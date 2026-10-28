# api/support/tasks/notification_tasks.py  — WORLD #1 COMPLETE
"""Notification delivery tasks."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.notification_tasks.send_ticket_reply_email")
def send_ticket_reply_email(ticket_id: int, is_agent: bool = True):
    """Send reply notification email."""
    try:
        from api.support.models import SupportTicket
        from api.support.services import notification_service
        ticket = SupportTicket.objects.get(id=ticket_id)
        if is_agent:
            notification_service.notify_new_reply(ticket, None, is_agent=True)
        else:
            notification_service.notify_new_reply(ticket, None, is_agent=False)
        return {"success": True}
    except Exception as e:
        logger.error(f"Reply email failed for ticket {ticket_id}: {e}")
        return {"error": str(e)}

@shared_task(name="support.tasks.notification_tasks.process_email_inbox")
def process_email_inbox():
    """Process support email inbox — create tickets from emails."""
    try:
        from api.support.integrations.email_to_ticket import email_to_ticket
        return email_to_ticket.process_inbox()
    except Exception as e:
        logger.warning(f"Email inbox processing: {e}")
        return {"error": str(e)}

@shared_task(name="support.tasks.notification_tasks.send_daily_digest")
def send_daily_digest():
    """Send daily digest to admin."""
    try:
        from api.support.notifications.digest_sender import digest_sender
        return digest_sender.send_daily_digest()
    except Exception as e:
        logger.error(f"Daily digest failed: {e}")
        return {"error": str(e)}

@shared_task(name="support.tasks.notification_tasks.send_agent_summaries")
def send_agent_summaries():
    """Send daily performance summary to each agent."""
    try:
        from api.support.notifications.digest_sender import digest_sender
        count = digest_sender.send_agent_daily_summary()
        return {"sent": count}
    except Exception as e:
        logger.error(f"Agent summaries failed: {e}")
        return {"error": str(e)}