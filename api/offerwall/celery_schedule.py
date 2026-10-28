"""
api/offerwall/celery_schedule.py

Celery Beat schedule for offerwall tasks.

Paste CELERY_BEAT_SCHEDULE into your Django settings, or import it:

    # config/settings.py
    from api.offerwall.celery_schedule import OFFERWALL_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {
        **CELERY_BEAT_SCHEDULE,           # existing schedules
        **OFFERWALL_BEAT_SCHEDULE,        # offerwall schedules
    }

Requirements:
    pip install django-celery-beat celery redis
    INSTALLED_APPS += ['django_celery_beat']
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
"""
from celery.schedules import crontab

OFFERWALL_BEAT_SCHEDULE = {

    # ── Offer lifecycle ───────────────────────────────────────────
    'offerwall-expire-offers': {
        'task':     'offerwall.expire_offers',
        'schedule': crontab(minute='*/15'),          # every 15 min
        'kwargs':   {'batch_size': 200},
        'options':  {'expires': 600},
    },
    'offerwall-recalculate-quality-scores': {
        'task':     'offerwall.recalculate_quality_scores',
        'schedule': crontab(hour='*/6', minute=0),   # every 6 hours
        'kwargs':   {'batch_size': 100},
    },
    'offerwall-sync-all-providers': {
        'task':     'offerwall.sync_all_providers',
        'schedule': crontab(minute=0),               # every hour
        'kwargs':   {'force': False},
    },

    # ── Conversion lifecycle ──────────────────────────────────────
    'offerwall-auto-approve-conversions': {
        'task':     'offerwall.auto_approve_pending_conversions',
        'schedule': crontab(minute='*/30'),           # every 30 min
        'kwargs':   {'review_hours': 24, 'batch_size': 50},
    },
    'offerwall-expire-pending-conversions': {
        'task':     'offerwall.expire_pending_conversions',
        'schedule': crontab(hour=2, minute=0),        # daily at 02:00
        'kwargs':   {'timeout_hours': 72},
    },
    'offerwall-retry-failed-postbacks': {
        'task':     'offerwall.retry_failed_postbacks',
        'schedule': crontab(minute='*/10'),            # every 10 min
        'kwargs':   {'max_retries': 3},
    },

    # ── Fraud & security ──────────────────────────────────────────
    'offerwall-refresh-fraud-scores': {
        'task':     'offerwall.refresh_fraud_scores',
        'schedule': crontab(hour='*/6', minute=30),   # every 6 hours offset
        'kwargs':   {'batch_size': 100},
    },
    'offerwall-cleanup-old-clicks': {
        'task':     'offerwall.cleanup_old_clicks',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # weekly Sunday 03:00
        'kwargs':   {'days': 90},
    },

    # ── B2B billing ───────────────────────────────────────────────
    'offerwall-generate-monthly-invoices': {
        'task':     'offerwall.generate_monthly_invoices',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # 1st of month 01:00
    },
    'offerwall-mark-overdue-invoices': {
        'task':     'offerwall.mark_overdue_invoices',
        'schedule': crontab(hour=9, minute=0),         # daily at 09:00
    },
    'offerwall-reset-monthly-usage': {
        'task':     'offerwall.reset_monthly_usage',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),  # 1st of month midnight
    },

    # ── Analytics & cache ─────────────────────────────────────────
    'offerwall-warm-analytics-cache': {
        'task':     'offerwall.warm_analytics_cache',
        'schedule': crontab(minute='*/30'),            # every 30 min
    },
    'offerwall-update-provider-stats': {
        'task':     'offerwall.update_provider_stats',
        'schedule': crontab(minute=45),                # every hour at :45
    },

    # ── Anomaly monitoring (AlertAdapter wired) ───────────────
    'offerwall-check-fraud-anomalies': {
        'task':     'offerwall.check_fraud_anomalies',
        'schedule': crontab(minute=0),                 # every hour
        'kwargs':   {'window_minutes': 60, 'chargeback_threshold': 0.1},
    },
    'offerwall-check-provider-health': {
        'task':     'offerwall.check_provider_health',
        'schedule': crontab(minute='*/30'),             # every 30 min
    },
    'offerwall-check-adapter-health': {
        'task':     'offerwall.check_adapter_health',
        'schedule': crontab(minute='*/15'),             # every 15 min
    },
}
