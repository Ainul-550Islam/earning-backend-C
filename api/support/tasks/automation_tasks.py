# api/support/tasks/automation_tasks.py  — WORLD #1 COMPLETE
"""Automation rule execution tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.automation_tasks.run_automation_on_idle_tickets")
def run_automation_on_idle_tickets():
    """Hourly — fire idle triggers on stale tickets."""
    from api.support.models import SupportTicket
    from api.support.automation.trigger_engine import trigger_engine
    stats = {"fired": 0}
    for hours, trigger in [(1,"ticket_idle_1h"),(4,"ticket_idle_4h"),(24,"ticket_idle_24h"),(72,"ticket_idle_72h")]:
        cutoff  = timezone.now() - timedelta(hours=hours)
        tickets = SupportTicket.objects.filter(
            status__in=["open","in_progress","waiting_user"],
            updated_at__lte=cutoff,
        )[:20]
        for ticket in tickets:
            results = trigger_engine.fire(trigger, ticket=ticket)
            stats["fired"] += len(results)
    return stats

@shared_task(name="support.tasks.automation_tasks.run_automation_on_ticket")
def run_automation_on_ticket(ticket_id: str, trigger: str):
    """Run automation for a specific ticket and trigger."""
    try:
        from api.support.models import SupportTicket
        from api.support.automation.trigger_engine import trigger_engine
        if str(ticket_id).startswith("TKT"):
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(id=ticket_id)
        results = trigger_engine.fire(trigger, ticket=ticket)
        return {"results": len(results)}
    except Exception as e:
        logger.error(f"Automation task failed: {e}")
        return {"error": str(e)}