# engagement/celery_beat_config.py
"""
Celery Beat configuration for engagement system scheduled tasks.
Defines all periodic tasks for the engagement gamification engine.
"""
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Import all task modules to ensure tasks are registered
from .tasks import (
    # Daily tasks
    daily_checkin_reset, daily_spin_reset, process_daily_leaderboard,
    send_daily_notifications, cleanup_expired_sessions,
    
    # Weekly tasks
    weekly_leaderboard_reset, process_weekly_rewards,
    weekly_analytics_aggregation, cleanup_old_notifications,
    
    # Monthly tasks
    monthly_leaderboard_reset, generate_monthly_reports,
    cleanup_old_analytics, archive_completed_quests,
    
    # Hourly tasks
    hourly_analytics_update, process_pending_webhooks,
    update_seasonal_events, cache_warmup,
    
    # Maintenance tasks
    cleanup_expired_tokens, optimize_database_tables,
    backup_engagement_data, sync_external_systems
)

app = Celery('engagement')

# Beat schedule configuration
app.conf.beat_schedule = {
    # ── Daily Tasks ────────────────────────────────────────────────────────
    'daily-checkin-reset': {
        'task': 'engagement.tasks.daily_checkin_reset',
        'schedule': crontab(hour=0, minute=1),  # 12:01 AM
        'options': {'queue': 'engagement'}
    },
    
    'daily-spin-reset': {
        'task': 'engagement.tasks.daily_spin_reset',
        'schedule': crontab(hour=0, minute=2),  # 12:02 AM
        'options': {'queue': 'engagement'}
    },
    
    'daily-leaderboard-process': {
        'task': 'engagement.tasks.process_daily_leaderboard',
        'schedule': crontab(hour=23, minute=55),  # 11:55 PM
        'options': {'queue': 'engagement'}
    },
    
    'daily-notifications': {
        'task': 'engagement.tasks.send_daily_notifications',
        'schedule': crontab(hour=9, minute=0),  # 9:00 AM
        'options': {'queue': 'notifications'}
    },
    
    'cleanup-expired-sessions': {
        'task': 'engagement.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    # ── Weekly Tasks ────────────────────────────────────────────────────────
    'weekly-leaderboard-reset': {
        'task': 'engagement.tasks.weekly_leaderboard_reset',
        'schedule': crontab(hour=0, minute=5, day_of_week=0),  # Sunday 12:05 AM
        'options': {'queue': 'engagement'}
    },
    
    'weekly-rewards-process': {
        'task': 'engagement.tasks.process_weekly_rewards',
        'schedule': crontab(hour=1, minute=0, day_of_week=1),  # Monday 1:00 AM
        'options': {'queue': 'engagement'}
    },
    
    'weekly-analytics': {
        'task': 'engagement.tasks.weekly_analytics_aggregation',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3:00 AM
        'options': {'queue': 'analytics'}
    },
    
    'cleanup-old-notifications': {
        'task': 'engagement.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Monday 4:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    # ── Monthly Tasks ────────────────────────────────────────────────────────
    'monthly-leaderboard-reset': {
        'task': 'engagement.tasks.monthly_leaderboard_reset',
        'schedule': crontab(hour=0, minute=10, day_of_month=1),  # 1st of month 12:10 AM
        'options': {'queue': 'engagement'}
    },
    
    'monthly-reports': {
        'task': 'engagement.tasks.generate_monthly_reports',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),  # 1st of month 6:00 AM
        'options': {'queue': 'analytics'}
    },
    
    'cleanup-old-analytics': {
        'task': 'engagement.tasks.cleanup_old_analytics',
        'schedule': crontab(hour=2, minute=0, day_of_month=2),  # 2nd of month 2:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    'archive-completed-quests': {
        'task': 'engagement.tasks.archive_completed_quests',
        'schedule': crontab(hour=3, minute=0, day_of_month=2),  # 2nd of month 3:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    # ── Hourly Tasks ────────────────────────────────────────────────────────
    'hourly-analytics-update': {
        'task': 'engagement.tasks.hourly_analytics_update',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'analytics'}
    },
    
    'process-pending-webhooks': {
        'task': 'engagement.tasks.process_pending_webhooks',
        'schedule': crontab(minute=5),  # Every hour at 5 minutes past
        'options': {'queue': 'webhooks'}
    },
    
    'update-seasonal-events': {
        'task': 'engagement.tasks.update_seasonal_events',
        'schedule': crontab(minute=10),  # Every hour at 10 minutes past
        'options': {'queue': 'engagement'}
    },
    
    'cache-warmup': {
        'task': 'engagement.tasks.cache_warmup',
        'schedule': crontab(minute=15),  # Every hour at 15 minutes past
        'options': {'queue': 'cache'}
    },
    
    # ── Maintenance Tasks ────────────────────────────────────────────────────
    'cleanup-expired-tokens': {
        'task': 'engagement.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=3, minute=30),  # Daily 3:30 AM
        'options': {'queue': 'maintenance'}
    },
    
    'optimize-database': {
        'task': 'engagement.tasks.optimize_database_tables',
        'schedule': crontab(hour=4, minute=0, day_of_week=6),  # Saturday 4:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    'backup-engagement-data': {
        'task': 'engagement.tasks.backup_engagement_data',
        'schedule': crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    'sync-external-systems': {
        'task': 'engagement.tasks.sync_external_systems',
        'schedule': crontab(hour=6, minute=0),  # Daily 6:00 AM
        'options': {'queue': 'sync'}
    },
}

# Additional Celery configuration
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

# Task routing configuration
app.conf.task_routes = {
    'engagement.tasks.daily_*': {'queue': 'engagement'},
    'engagement.tasks.weekly_*': {'queue': 'engagement'},
    'engagement.tasks.monthly_*': {'queue': 'engagement'},
    'engagement.tasks.hourly_*': {'queue': 'analytics'},
    'engagement.tasks.send_*': {'queue': 'notifications'},
    'engagement.tasks.cleanup_*': {'queue': 'maintenance'},
    'engagement.tasks.process_*': {'queue': 'engagement'},
    'engagement.tasks.webhook*': {'queue': 'webhooks'},
    'engagement.tasks.cache*': {'queue': 'cache'},
    'engagement.tasks.sync*': {'queue': 'sync'},
}

# Task priority configuration
app.conf.task_default_priority = 5
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True

# Error handling
app.conf.task_reject_on_worker_lost = True
app.conf.task_ignore_result = False
