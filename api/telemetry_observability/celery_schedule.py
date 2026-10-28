"""
Celery beat schedule for Telemetry Observability.

Merge this into your main project's celery.py:

    from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE
    app.conf.beat_schedule.update(TELEMETRY_BEAT_SCHEDULE)

Or in your Django settings (if you use CELERY_BEAT_SCHEDULE):

    from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {
        **CELERY_BEAT_SCHEDULE,  # your existing tasks
        **TELEMETRY_BEAT_SCHEDULE,
    }
"""

TELEMETRY_BEAT_SCHEDULE = {
    'telemetry-cleanup-old-data': {
        'task':     'api.telemetry_observability.tasks.cleanup_old_telemetry',
        'schedule': 86400,
        'options':  {'expires': 3600},
    },
    'telemetry-health-check-ping': {
        'task':     'api.telemetry_observability.tasks.run_health_checks',
        'schedule': 300,
        'options':  {'expires': 60},
    },
    'telemetry-flush-metric-cache': {
        'task':     'api.telemetry_observability.tasks.flush_metric_aggregation_cache',
        'schedule': 3600,
        'options':  {'expires': 300},
    },
    'telemetry-internet-connectivity-check': {
        'task':     'api.telemetry_observability.tasks.check_internet_connectivity',
        'schedule': 60,
        'options':  {'expires': 55},
    },
}
