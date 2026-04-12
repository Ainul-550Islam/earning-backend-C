# kyc/celery_config/beat_schedule.py  ── WORLD #1
"""
Complete Celery Beat schedule for KYC system.
Add to settings.py:
    from kyc.celery_config.beat_schedule import KYC_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {**CELERY_BEAT_SCHEDULE, **KYC_BEAT_SCHEDULE}
"""
from celery.schedules import crontab

KYC_BEAT_SCHEDULE = {

    # ── Daily tasks (run at night) ─────────────────────────

    'kyc-expire-overdue': {
        'task':     'api.kyc.tasks.kyc_tasks.expire_overdue_kycs',
        'schedule': crontab(hour=1, minute=0),
        'options':  {'queue': 'kyc_maintenance'},
    },
    'kyc-daily-analytics': {
        'task':     'api.kyc.tasks.kyc_tasks.generate_daily_analytics',
        'schedule': crontab(hour=0, minute=30),
        'options':  {'queue': 'kyc_analytics'},
    },
    'kyc-cleanup-exports': {
        'task':     'api.kyc.tasks.kyc_tasks.cleanup_old_export_jobs',
        'schedule': crontab(hour=2, minute=0),
        'options':  {'queue': 'kyc_maintenance'},
    },
    'kyc-cleanup-otps': {
        'task':     'api.kyc.tasks.kyc_tasks.cleanup_old_otp_logs',
        'schedule': crontab(hour=3, minute=0),
        'options':  {'queue': 'kyc_maintenance'},
    },

    # ── Expiry warning (morning) ───────────────────────────

    'kyc-expiry-warnings': {
        'task':     'api.kyc.tasks.kyc_tasks.notify_expiring_soon_kycs',
        'schedule': crontab(hour=9, minute=0),
        'kwargs':   {'days': 30},
        'options':  {'queue': 'kyc_notifications'},
    },

    # ── Weekly tasks ───────────────────────────────────────

    'kyc-periodic-aml-screening': {
        'task':     'api.kyc.tasks.kyc_tasks.run_risk_scoring',
        'schedule': crontab(day_of_week='monday', hour=2, minute=0),
        'options':  {'queue': 'kyc_compliance'},
    },
    'kyc-sanctions-list-update': {
        'task':     'api.kyc.tasks.kyc_tasks.update_sanctions_lists',
        'schedule': crontab(day_of_week='sunday', hour=1, minute=0),
        'options':  {'queue': 'kyc_compliance'},
    },
    'kyc-duplicate-detection-sweep': {
        'task':     'api.kyc.tasks.kyc_tasks.detect_duplicates',
        'schedule': crontab(day_of_week='wednesday', hour=3, minute=0),
        'options':  {'queue': 'kyc_fraud'},
    },

    # ── Monthly tasks ──────────────────────────────────────

    'kyc-generate-invoices': {
        'task':     'api.kyc.tasks.kyc_tasks.generate_monthly_invoices',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
        'options':  {'queue': 'kyc_billing'},
    },
    'kyc-gdpr-retention': {
        'task':     'api.kyc.tasks.kyc_tasks.enforce_data_retention',
        'schedule': crontab(day_of_month=1, hour=4, minute=0),
        'options':  {'queue': 'kyc_compliance'},
    },

    # ── Hourly tasks ───────────────────────────────────────

    'kyc-pending-timeout': {
        'task':     'api.kyc.tasks.kyc_tasks.timeout_stale_pending',
        'schedule': crontab(minute=0),
        'options':  {'queue': 'kyc_maintenance'},
    },
}


# ── Celery queue configuration ─────────────────────────────

KYC_TASK_ROUTES = {
    'api.kyc.tasks.kyc_tasks.run_ocr_extraction':          {'queue': 'kyc_ai'},
    'api.kyc.tasks.kyc_tasks.run_face_match':               {'queue': 'kyc_ai'},
    'api.kyc.tasks.kyc_tasks.run_risk_scoring':             {'queue': 'kyc_fraud'},
    'api.kyc.tasks.kyc_tasks.send_kyc_notification':        {'queue': 'kyc_notifications'},
    'api.kyc.tasks.kyc_tasks.export_kyc_data':              {'queue': 'kyc_exports'},
    'api.kyc.tasks.kyc_tasks.generate_daily_analytics':     {'queue': 'kyc_analytics'},
    'api.kyc.tasks.kyc_tasks.process_batch_job':            {'queue': 'kyc_batch'},
    'api.kyc.tasks.kyc_tasks.expire_overdue_kycs':          {'queue': 'kyc_maintenance'},
    'api.kyc.tasks.kyc_tasks.cleanup_old_export_jobs':      {'queue': 'kyc_maintenance'},
    'api.kyc.tasks.kyc_tasks.generate_monthly_invoices':    {'queue': 'kyc_billing'},
    'api.kyc.tasks.kyc_tasks.enforce_data_retention':       {'queue': 'kyc_compliance'},
    'api.kyc.tasks.kyc_tasks.update_sanctions_lists':       {'queue': 'kyc_compliance'},
}


# ── Settings snippet (copy to settings.py) ────────────────

CELERY_SETTINGS_SNIPPET = """
# Add to settings.py:

CELERY_BROKER_URL   = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_ENABLE_UTC = True

# Worker concurrency per queue
CELERY_WORKER_CONCURRENCY = 4

# KYC task queues
CELERY_TASK_QUEUES = {
    'kyc_ai':            {'exchange': 'kyc', 'routing_key': 'kyc.ai'},
    'kyc_fraud':         {'exchange': 'kyc', 'routing_key': 'kyc.fraud'},
    'kyc_notifications': {'exchange': 'kyc', 'routing_key': 'kyc.notifications'},
    'kyc_compliance':    {'exchange': 'kyc', 'routing_key': 'kyc.compliance'},
    'kyc_batch':         {'exchange': 'kyc', 'routing_key': 'kyc.batch'},
    'kyc_exports':       {'exchange': 'kyc', 'routing_key': 'kyc.exports'},
    'kyc_analytics':     {'exchange': 'kyc', 'routing_key': 'kyc.analytics'},
    'kyc_maintenance':   {'exchange': 'kyc', 'routing_key': 'kyc.maintenance'},
    'kyc_billing':       {'exchange': 'kyc', 'routing_key': 'kyc.billing'},
}

from kyc.celery_config.beat_schedule import KYC_BEAT_SCHEDULE, KYC_TASK_ROUTES
CELERY_BEAT_SCHEDULE = KYC_BEAT_SCHEDULE
CELERY_TASK_ROUTES   = KYC_TASK_ROUTES

# Start workers:
# celery -A your_project worker -Q kyc_ai,kyc_fraud --concurrency=2
# celery -A your_project worker -Q kyc_notifications,kyc_maintenance --concurrency=4
# celery -A your_project beat --loglevel=info
"""
