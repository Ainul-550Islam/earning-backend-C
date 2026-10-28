# api/support/tasks/escalation_tasks.py  — WORLD #1 COMPLETE
"""Auto-escalation tasks for breached SLA tickets."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.escalation_tasks.auto_escalate_breached_tickets")
def auto_escalate_breached_tickets():
    """Auto-escalate tickets where SLA is breached but not yet escalated."""
    from api.support.models import SupportTicket, TicketSLA
    from django.utils import timezone
    tickets = SupportTicket.objects.filter(
        status__in=["open","in_progress","waiting_user"],
        escalated=False,
        sla__first_response_breached=True,
    ).select_related("sla","assigned_to")
    count = 0
    for ticket in tickets[:50]:
        try:
            ticket.escalated    = True
            ticket.escalated_at = timezone.now()
            ticket.priority     = "urgent" if ticket.priority != "urgent" else ticket.priority
            ticket.save(update_fields=["escalated","escalated_at","priority"])
            # Notify
            try:
                from api.support.notifications.escalation_notifier import escalation_notifier
                escalation_notifier.notify_ticket_escalated(ticket, reason="SLA breach auto-escalation")
            except Exception:
                pass
            count += 1
        except Exception as e:
            logger.error(f"Auto-escalate failed for {ticket.ticket_id}: {e}")
    logger.info(f"Auto-escalated {count} tickets")
    return {"escalated": count}