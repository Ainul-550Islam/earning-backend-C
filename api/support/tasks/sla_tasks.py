# api/support/tasks/sla_tasks.py  — WORLD #1 COMPLETE
"""SLA breach detection and notification tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.sla_tasks.check_sla_breaches")
def check_sla_breaches():
    """Every 15 minutes — check all active tickets for SLA breaches."""
    from api.support.services import sla_service
    result = sla_service.check_breaches()
    logger.info(f"SLA check complete: {result}")
    return result

@shared_task(name="support.tasks.sla_tasks.warn_upcoming_sla")
def warn_upcoming_sla():
    """Warn agents about tickets approaching SLA deadline (1 hour before)."""
    from api.support.models import TicketSLA, SupportTicket
    from api.support.services import notify_sla_warning
    now      = timezone.now()
    warning_window = now + timedelta(hours=1)
    slas = TicketSLA.objects.filter(
        first_response_at__isnull=True,
        first_response_due__lte=warning_window,
        first_response_breached=False,
        warning_sent=False,
    ).select_related("ticket", "ticket__assigned_to")
    count = 0
    for sla in slas:
        try:
            notify_sla_warning(sla.ticket)
            sla.warning_sent = True
            sla.save(update_fields=["warning_sent"])
            count += 1
        except Exception as e:
            logger.error(f"SLA warning failed for {sla.ticket.ticket_id}: {e}")
    logger.info(f"SLA warnings sent: {count}")
    return {"warnings_sent": count}