"""
api/support/automation/automation_scheduler.py
FILE 46/70 — Time-based Automation Scheduler

Celery beat schedule-এ register করো।
"""
import logging
logger = logging.getLogger(__name__)

CELERY_BEAT_SCHEDULE = {
    'sla-check-15min': {
        'task': 'support.tasks.sla_tasks.check_sla_breaches',
        'schedule': 900,  # 15 minutes
    },
    'auto-close-stale': {
        'task': 'support.tasks.cleanup_tasks.auto_close_stale_tickets',
        'schedule': 86400,  # daily
        'kwargs': {'waiting_days': 7},
    },
    'time-based-triggers': {
        'task': 'support.tasks.automation_tasks.run_automation_on_idle_tickets',
        'schedule': 3600,  # hourly
    },
    'daily-digest': {
        'task': 'support.tasks.insight_tasks.generate_daily_insight',
        'schedule': 86400,
    },
    'csat-reminders': {
        'task': 'support.tasks.csat_tasks.send_csat_rating_requests',
        'schedule': 86400,
    },
    'auto-assign': {
        'task': 'support.tasks.assignment_tasks.auto_assign_unassigned_tickets',
        'schedule': 600,  # 10 minutes
    },
    'cleanup-chat': {
        'task': 'support.tasks.cleanup_tasks.cleanup_old_chat_sessions',
        'schedule': 86400,
    },
    'churn-scan': {
        'task': 'support.tasks.insight_tasks.save_agent_snapshots',
        'schedule': 86400,
    },
}

def register_schedule(app):
    """Celery app-এ schedule register করো"""
    app.conf.beat_schedule.update(CELERY_BEAT_SCHEDULE)
    logger.info(f'Support automation: {len(CELERY_BEAT_SCHEDULE)} scheduled tasks registered.')