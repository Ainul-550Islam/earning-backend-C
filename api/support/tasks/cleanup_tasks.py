# api/support/tasks/cleanup_tasks.py  — WORLD #1 COMPLETE
"""Cleanup and housekeeping tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.cleanup_tasks.auto_close_stale_tickets")
def auto_close_stale_tickets(waiting_days: int = 7):
    """Daily — auto-close tickets waiting for user reply."""
    from api.support.models import SupportTicket
    cutoff  = timezone.now() - timedelta(days=waiting_days)
    tickets = SupportTicket.objects.filter(status="waiting_user", updated_at__lte=cutoff)
    count   = tickets.count()
    tickets.update(status="closed")
    logger.info(f"Auto-closed {count} stale tickets (waiting >{waiting_days} days)")
    return {"closed": count}

@shared_task(name="support.tasks.cleanup_tasks.cleanup_old_chat_sessions")
def cleanup_old_chat_sessions(days: int = 30):
    """Archive ended chat sessions older than X days."""
    from api.support.models import LiveChatSession
    cutoff  = timezone.now() - timedelta(days=days)
    deleted, _ = LiveChatSession.objects.filter(status="ended", ended_at__lte=cutoff).delete()
    logger.info(f"Cleaned up {deleted} old chat sessions")
    return {"deleted": deleted}

@shared_task(name="support.tasks.cleanup_tasks.auto_offline_inactive_agents")
def auto_offline_inactive_agents(inactive_minutes: int = 60):
    """Set agents as offline if not seen in X minutes."""
    from api.support.models import SupportAgent, AgentStatus
    cutoff = timezone.now() - timedelta(minutes=inactive_minutes)
    updated = AgentStatus.objects.filter(
        status__in=["online","busy"],
        last_seen__lte=cutoff,
    ).update(status="offline")
    logger.info(f"Set {updated} inactive agents to offline")
    return {"set_offline": updated}

@shared_task(name="support.tasks.cleanup_tasks.cleanup_notification_logs")
def cleanup_notification_logs(days: int = 90):
    """Purge notification logs older than X days."""
    from api.support.models import SupportNotificationLog
    cutoff  = timezone.now() - timedelta(days=days)
    deleted, _ = SupportNotificationLog.objects.filter(created_at__lte=cutoff).delete()
    logger.info(f"Cleaned {deleted} old notification log entries")
    return {"deleted": deleted}