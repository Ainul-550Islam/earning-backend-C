"""
Celery application entry point for the Earnify / Realtime Dashboard project.

USAGE
-----
This file belongs at the PROJECT ROOT alongside manage.py / settings.py.
Copy it there and rename it to config/celery.py (or wherever your project
keeps its Celery app).

Start a worker:
    celery -A config.celery worker -l info

Start the beat scheduler (for periodic tasks):
    celery -A config.celery beat -l info

Or combine (development only — not recommended for production):
    celery -A config.celery worker --beat -l info


REQUIRED SETTINGS
-----------------
FIX (v1.3.0): Previous version referenced `REALTIME_DASHBOARD` before
it was defined, causing a NameError when settings.py was loaded. The
beat_schedule now reads env vars or uses safe hardcoded defaults so it
works in any environment with zero extra configuration.

Add to your settings.py:

    import os
    from celery.schedules import crontab

    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'

    # Tune these via REALTIME_DASHBOARD settings dict:
    #   REALTIME_DASHBOARD = {'WEBSOCKET_TIMEOUT': 3600, 'METRIC_BROADCAST_INTERVAL': 30}
    _rd = getattr(settings, 'REALTIME_DASHBOARD', {})

    CELERY_BEAT_SCHEDULE = {
        'realtime-dashboard-cleanup-stale-connections': {
            'task': 'api.realtime_dashboard.tasks.cleanup_stale_connections',
            'schedule': crontab(minute='*/15'),
            'kwargs': {'timeout_seconds': _rd.get('WEBSOCKET_TIMEOUT', 3600)},
        },
        'realtime-dashboard-broadcast-active-metrics': {
            'task': 'api.realtime_dashboard.tasks.broadcast_active_metrics',
            'schedule': _rd.get('METRIC_BROADCAST_INTERVAL', 30),
        },
    }

    REST_FRAMEWORK = {
        ...
        'DEFAULT_THROTTLE_RATES': {
            'anon':                 '60/hour',
            'user':                 '1000/hour',
            'metric_update':        '120/minute',
            'dashboard_render':     '30/minute',
            'websocket_connect':    '10/minute',
            'health_check':         '120/minute',
            'burst_user':           '20/minute',
        },
    }
"""
import os

from celery import Celery

# Set the default Django settings module BEFORE importing anything Django.
# This must happen before `app.config_from_object` is called below.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Load Celery config from Django settings using the CELERY_ namespace prefix.
# e.g. CELERY_BROKER_URL → broker_url,  CELERY_BEAT_SCHEDULE → beat_schedule
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover @shared_task definitions in every INSTALLED_APP's tasks.py.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Development helper: prints the Celery request context."""
    print(f'Request: {self.request!r}')
