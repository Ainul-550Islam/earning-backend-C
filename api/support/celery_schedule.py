"""
api/support/celery_schedule.py
FILE 67/70 — Complete Celery Beat Schedule

settings.py-তে add করো:
    from api.support.celery_schedule import SUPPORT_CELERY_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(SUPPORT_CELERY_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

SUPPORT_CELERY_BEAT_SCHEDULE = {
    # SLA — every 15 min
    'support-sla-check': {
        'task':     'support.tasks.sla_tasks.check_sla_breaches',
        'schedule': 900,
    },
    # Email-to-ticket — every 5 min
    'support-email-inbox': {
        'task':     'support.tasks.notification_tasks.process_email_inbox',
        'schedule': 300,
    },
    # Auto-assign — every 10 min
    'support-auto-assign': {
        'task':     'support.tasks.assignment_tasks.auto_assign_unassigned_tickets',
        'schedule': 600,
    },
    # Auto-close stale — daily at 2 AM
    'support-auto-close': {
        'task':     'support.tasks.cleanup_tasks.auto_close_stale_tickets',
        'schedule': crontab(hour=2, minute=0),
    },
    # Daily digest — midnight
    'support-daily-digest': {
        'task':     'support.tasks.insight_tasks.generate_daily_insight',
        'schedule': crontab(hour=0, minute=0),
    },
    # CSAT reminders — daily 10 AM
    'support-csat-reminders': {
        'task':     'support.tasks.csat_tasks.send_csat_rating_requests',
        'schedule': crontab(hour=10, minute=0),
    },
    # Reminder emails — daily 9 AM
    'support-reminders': {
        'task':     'support.tasks.notification_tasks.send_ticket_reply_email',
        'schedule': crontab(hour=9, minute=0),
    },
    # Idle ticket automation — hourly
    'support-idle-automation': {
        'task':     'support.tasks.automation_tasks.run_automation_on_idle_tickets',
        'schedule': crontab(minute=0),
    },
    # Chat idle timeout — every 30 min
    'support-chat-timeout': {
        'task':     'support.tasks.chat_tasks.timeout_idle_chat_sessions',
        'schedule': 1800,
    },
    # KB category count update — every 6 hours
    'support-kb-index': {
        'task':     'support.tasks.kb_tasks.update_kb_category_counts',
        'schedule': crontab(hour='*/6', minute=0),
    },
    # Churn risk scan — daily 8 AM
    'support-churn-scan': {
        'task':     'support.tasks.insight_tasks.save_agent_snapshots',
        'schedule': crontab(hour=8, minute=0),
    },
    # Weekly report — Monday 7 AM
    'support-weekly-report': {
        'task':     'support.tasks.insight_tasks.generate_daily_insight',
        'schedule': crontab(day_of_week='monday', hour=7, minute=0),
    },
    # Cleanup old sessions — daily 3 AM
    'support-cleanup-sessions': {
        'task':     'support.tasks.cleanup_tasks.cleanup_old_chat_sessions',
        'schedule': crontab(hour=3, minute=0),
    },
}