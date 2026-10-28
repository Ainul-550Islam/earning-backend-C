# api/support/tasks/assignment_tasks.py  — WORLD #1 COMPLETE
"""Auto-assignment tasks for unassigned tickets."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.assignment_tasks.auto_assign_unassigned_tickets")
def auto_assign_unassigned_tickets():
    """Every 10 minutes — assign tickets that have no agent."""
    from api.support.models import SupportTicket
    from api.support.services import ticket_service
    tickets = SupportTicket.objects.filter(
        assigned_to__isnull=True,
        status__in=["open","in_progress"],
    ).select_related("user")[:20]
    assigned = 0
    for ticket in tickets:
        try:
            ticket_service._auto_assign(ticket)
            if ticket.assigned_to:
                assigned += 1
        except Exception as e:
            logger.error(f"Auto-assign failed for {ticket.ticket_id}: {e}")
    logger.info(f"Auto-assigned {assigned} tickets")
    return {"assigned": assigned}