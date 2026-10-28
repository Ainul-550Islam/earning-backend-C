"""
api/support/tasks_extra.py
FIXED — Missing Celery tasks referenced in celery_schedule.py
Add these to existing tasks/ files.
"""

# ── Add to tasks/notification_tasks.py ──────────────────
PROCESS_EMAIL_INBOX_TASK = '''
@shared_task(name='support.tasks.notification_tasks.process_email_inbox')
def process_email_inbox():
    """Process support email inbox — create tickets from emails"""
    from api.support.integrations.email_to_ticket import email_to_ticket
    result = email_to_ticket.process_inbox()
    return result
'''

# ── Add to tasks/insight_tasks.py ───────────────────────
SAVE_AGENT_SNAPSHOTS_TASK = '''
@shared_task(name='support.tasks.insight_tasks.save_agent_snapshots')
def save_agent_snapshots():
    """Save daily agent performance snapshot + run churn scan"""
    from api.support.ai.ai_churn_predictor import churn_predictor
    churn_result = churn_predictor.run_daily_scan()
    
    from api.support.models import SupportAgent, SupportTicket
    from django.db.models import Count, Avg
    from django.utils import timezone
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    snapshots = []
    for agent in SupportAgent.objects.filter(is_active=True).select_related("user"):
        tickets = SupportTicket.objects.filter(assigned_to=agent.user, created_at__gte=today)
        snapshots.append({
            "agent": agent.user.username,
            "assigned": tickets.count(),
            "resolved": tickets.filter(status="resolved").count(),
        })
    
    return {"churn": churn_result, "snapshots": len(snapshots)}
'''

# ── Add to tasks/cleanup_tasks.py ───────────────────────
CLEANUP_OLD_CHAT_SESSIONS_TASK = '''
@shared_task(name="support.tasks.cleanup_tasks.cleanup_old_chat_sessions")
def cleanup_old_chat_sessions(days: int = 30) -> dict:
    """Archive old ended chat sessions"""
    from django.utils import timezone
    from datetime import timedelta
    from api.support.models import ChatSession  # Uses ChatSession model
    cutoff  = timezone.now() - timedelta(days=days)
    deleted, _ = ChatSession.objects.filter(
        status="ended", ended_at__lte=cutoff
    ).delete()
    return {"deleted": deleted, "older_than_days": days}
'''

# Task stubs — see tasks/ directory for actual task files