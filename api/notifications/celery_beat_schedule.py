# earning_backend/api/notifications/celery_beat_schedule.py
"""
Celery Beat periodic task schedule for the notification system.

Add to Django settings.py:
    from api.notifications.celery_beat_schedule import NOTIFICATION_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {**CELERY_BEAT_SCHEDULE, **NOTIFICATION_BEAT_SCHEDULE}
"""
from celery.schedules import crontab

NOTIFICATION_BEAT_SCHEDULE = {
    # Every minute
    'notifications-send-scheduled': {
        'task': 'notifications.send_scheduled_notifications',
        'schedule': 60,
        'options': {'queue': 'notifications_scheduled'},
    },
    'notifications-start-campaigns': {
        'task': 'notifications.start_scheduled_campaigns',
        'schedule': 60,
        'options': {'queue': 'notifications_campaigns'},
    },

    # Every 5 minutes
    'notifications-process-retries': {
        'task': 'notifications.process_all_retries',
        'schedule': 300,
        'options': {'queue': 'notifications_retry'},
    },
    'notifications-cancel-overdue': {
        'task': 'notifications.cancel_overdue_schedules',
        'schedule': 300,
        'options': {'queue': 'notifications_scheduled'},
    },

    # Every 30 minutes
    'notifications-poll-delivery': {
        'task': 'notifications.poll_delivery_status',
        'schedule': 1800,
        'options': {'queue': 'notifications_tracking'},
    },
    'notifications-check-campaign-completion': {
        'task': 'notifications.check_campaign_completion',
        'schedule': 1800,
        'options': {'queue': 'notifications_campaigns'},
    },

    # Every 6 hours
    'notifications-recalculate-fatigue': {
        'task': 'notifications.recalculate_fatigue_flags',
        'schedule': 21600,
        'options': {'queue': 'notifications_maintenance'},
    },
    'notifications-retry-failed-queue': {
        'task': 'notifications.retry_failed_queue_entries',
        'schedule': 21600,
        'options': {'queue': 'notifications_retry'},
    },

    # Daily at 00:01 UTC — reset daily fatigue
    'notifications-reset-daily-fatigue': {
        'task': 'notifications.reset_daily_fatigue_counters',
        'schedule': crontab(hour=0, minute=1),
        'options': {'queue': 'notifications_maintenance'},
    },
    # Daily at 01:00 UTC — generate analytics
    'notifications-daily-analytics': {
        'task': 'notifications.run_all_daily_analytics',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'notifications_analytics'},
    },
    # Daily at 01:30 UTC — refresh delivery rates
    'notifications-refresh-delivery-rates': {
        'task': 'notifications.refresh_delivery_rates',
        'schedule': crontab(hour=1, minute=30),
        'options': {'queue': 'notifications_analytics'},
    },
    # Daily at 02:00 UTC — refresh stale FCM tokens
    'notifications-token-refresh': {
        'task': 'notifications.refresh_stale_fcm_tokens',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'notifications_maintenance'},
    },
    # Daily at 03:00 UTC — run all cleanup
    'notifications-cleanup': {
        'task': 'notifications.run_all_cleanup',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'notifications_maintenance'},
    },

    # Weekly Monday 00:05 UTC — reset weekly fatigue
    'notifications-reset-weekly-fatigue': {
        'task': 'notifications.reset_weekly_fatigue_counters',
        'schedule': crontab(hour=0, minute=5, day_of_week=1),
        'options': {'queue': 'notifications_maintenance'},
    },
    # Weekly Sunday 05:00 UTC — cleanup inactive devices
    'notifications-cleanup-devices': {
        'task': 'notifications.cleanup_inactive_devices',
        'schedule': crontab(hour=5, minute=0, day_of_week=0),
        'options': {'queue': 'notifications_maintenance'},
    },
    # Weekly Monday 06:00 UTC — evaluate A/B tests
    'notifications-evaluate-abtests': {
        'task': 'notifications.evaluate_all_pending_ab_tests',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),
        'options': {'queue': 'notifications_campaigns'},
    },
    # Weekly Monday 07:00 UTC — sync SendGrid unsubscribes
    'notifications-sync-sendgrid-unsubs': {
        'task': 'notifications.sync_sendgrid_unsubscribes',
        'schedule': crontab(hour=7, minute=0, day_of_week=1),
        'options': {'queue': 'notifications_optout'},
    },
    # Weekly Monday 08:00 UTC — deactivate duplicate tokens
    'notifications-dedup-tokens': {
        'task': 'notifications.deactivate_duplicate_tokens',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),
        'options': {'queue': 'notifications_maintenance'},
    },

    # Monthly — 1st of month at 00:10 UTC
    'notifications-reset-monthly-fatigue': {
        'task': 'notifications.reset_monthly_fatigue_counters',
        'schedule': crontab(hour=0, minute=10, day_of_month=1),
        'options': {'queue': 'notifications_maintenance'},
    },
    'notifications-create-missing-fatigue': {
        'task': 'notifications.create_missing_fatigue_records',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),
        'options': {'queue': 'notifications_maintenance'},
    },

    # Integration System tasks
    'integration-health-checks': {
        'task': 'notifications.integration.run_health_checks',
        'schedule': 300,  # Every 5 minutes
        'options': {'queue': 'notifications_maintenance'},
    },
    'integration-event-bus-stats': {
        'task': 'notifications.integration.sync_event_bus_stats',
        'schedule': 3600,  # Every hour
        'options': {'queue': 'notifications_maintenance'},
    },
}

# Celery queue definitions — add to CELERY_TASK_QUEUES in settings.py
NOTIFICATION_QUEUES = [
    'notifications_high',
    'notifications_push',
    'notifications_email',
    'notifications_sms',
    'notifications_campaigns',
    'notifications_scheduled',
    'notifications_retry',
    'notifications_tracking',
    'notifications_analytics',
    'notifications_maintenance',
    'notifications_batch',
    'notifications_optout',
]

# Additional scheduled tasks (added after initial schedule)
NOTIFICATION_BEAT_SCHEDULE_EXTRA = {
    # Workflow engine tasks
    'notifications-inactive-user-workflows': {
        'task': 'notifications.trigger_inactive_workflows',
        'schedule': crontab(hour=10, minute=0),  # Daily 10am
        'options': {'queue': 'notifications_maintenance'},
    },

    # RFM segmentation (weekly)
    'notifications-compute-rfm-segments': {
        'task': 'notifications.compute_rfm_segments',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3am
        'options': {'queue': 'notifications_analytics'},
    },

    # Data retention enforcement (monthly)
    'notifications-data-retention': {
        'task': 'notifications.run_data_retention',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # 1st of month
        'options': {'queue': 'notifications_maintenance'},
    },

    # System monitoring (every 5 minutes)
    'notifications-monitoring-check': {
        'task': 'notifications.run_monitoring_check',
        'schedule': 300,
        'options': {'queue': 'notifications_maintenance'},
    },
}