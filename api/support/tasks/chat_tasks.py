# api/support/tasks/chat_tasks.py  — WORLD #1 COMPLETE
"""Live chat session management tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.chat_tasks.timeout_idle_chat_sessions")
def timeout_idle_chat_sessions(idle_minutes: int = 30):
    """End chat sessions idle for X minutes."""
    from api.support.models import LiveChatSession
    cutoff  = timezone.now() - timedelta(minutes=idle_minutes)
    sessions = LiveChatSession.objects.filter(status="active", started_at__lte=cutoff)
    count   = sessions.count()
    sessions.update(status="ended", ended_at=timezone.now())
    logger.info(f"Timed out {count} idle chat sessions")
    return {"ended": count}

@shared_task(name="support.tasks.chat_tasks.cleanup_old_chat_sessions")
def cleanup_old_chat_sessions(days: int = 90):
    """Archive/delete chat sessions older than X days."""
    from api.support.models import LiveChatSession
    cutoff  = timezone.now() - timedelta(days=days)
    deleted, _ = LiveChatSession.objects.filter(status="ended", started_at__lte=cutoff).delete()
    logger.info(f"Deleted {deleted} old chat sessions (older than {days} days)")
    return {"deleted": deleted}

@shared_task(name="support.tasks.chat_tasks.notify_waiting_users")
def notify_waiting_users():
    """Notify users who have been waiting for chat for too long."""
    from api.support.models import LiveChatSession
    from datetime import timedelta
    cutoff  = timezone.now() - timedelta(minutes=5)
    waiting = LiveChatSession.objects.filter(status="waiting", started_at__lte=cutoff).select_related("user")
    for session in waiting[:20]:
        try:
            # In-app notification that no agents are available
            from api.support.notifications.push_notifier import push_notifier
            push_notifier.send_to_user(
                session.user,
                title="No agents available",
                body="All agents are busy. Please leave a ticket instead.",
                data={"type": "chat_no_agents"},
            )
        except Exception:
            pass
    return {"notified": waiting.count()}