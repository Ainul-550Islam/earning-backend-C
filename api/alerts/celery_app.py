"""
alerts/celery.py — NEWLY CREATED (was completely missing)
Without this file, none of the 112 Celery tasks can register.
celery_beat_config.py existed but had no Celery app to attach to.

Usage:
    # Start worker:
    celery -A alerts worker --loglevel=info

    # Start beat scheduler:
    celery -A alerts beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

    # Start both (dev only):
    celery -A alerts worker --beat --loglevel=info
"""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun, task_failure

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def _host_project_has_celery_app():
    """True when the project this package is installed in already created its own Celery app.

    Standalone, `alerts` must become Celery's current app (so @shared_task binds to it and
    CELERY_TASK_ALWAYS_EAGER is honoured).  Installed inside a bigger project (api.alerts)
    it must NOT take over: that silently re-binds every @shared_task in the whole project
    to this app's config and routes."""
    try:
        from celery._state import _get_active_apps
        return any(getattr(a, 'main', None) not in (None, 'default', 'alerts')
                   for a in _get_active_apps())
    except Exception:
        return False   # unknown -> behave like the standalone package


# Create Celery app
app = Celery('alerts', set_as_current=not _host_project_has_celery_app())

# Load config from Django settings under CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()


# ── Beat schedule (from celery_beat_config.py — previously floating) ─────────
try:
    from api.alerts.celery_beat_config import CELERY_BEAT_SCHEDULE
    app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
except Exception as e:
    import logging
    logging.getLogger(__name__).warning('celery: could not load beat schedule: %s', e)
    # Fallback minimal beat schedule
    app.conf.beat_schedule = {
        'process-pending-alerts': {
            'task': 'api.alerts.tasks.core.process_pending_alerts',
            'schedule': 60.0,
            'options': {'expires': 120},
        },
        'check-system-health': {
            'task': 'api.alerts.tasks.core.check_system_health',
            'schedule': 300.0,
        },
        'cleanup-old-alerts': {
            'task': 'api.alerts.tasks.core.cleanup_old_alerts',
            'schedule': 3600.0,
        },
    }


# ── Worker signal handlers ────────────────────────────────────────────────────
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    import logging
    logging.getLogger(__name__).info(
        'Celery worker ready — alerts task queue active. '
        'Tasks registered: %d', len(app.tasks)
    )


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    import logging
    logging.getLogger(__name__).info('Celery worker shutting down')


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    import logging
    logging.getLogger(__name__).error(
        'Task %s[%s] failed: %s', sender.name, task_id, exception
    )
    # Integrate with CeleryHeartbeatMonitor from celery_beat_config.py
    try:
        from api.alerts.celery_beat_config import heartbeat_monitor
        heartbeat_monitor.record_task_execution(
            task_name=sender.name,
            task_id=task_id,
            status='failure',
            error=str(exception),
        )
    except Exception:
        pass


@task_postrun.connect
def on_task_postrun(sender, task_id, task, args, kwargs, retval, state, **kw):
    try:
        from api.alerts.celery_beat_config import heartbeat_monitor
        heartbeat_monitor.record_task_execution(
            task_name=task.name,
            task_id=task_id,
            status=state.lower() if isinstance(state, str) else state,
        )
    except Exception:
        pass


# ── Celery app configuration ──────────────────────────────────────────────────
app.conf.update(
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'api.alerts.tasks.core.*':          {'queue': 'alerts'},
        'api.alerts.tasks.incident.*':      {'queue': 'incidents'},
        'api.alerts.tasks.reporting.*':     {'queue': 'reporting'},
        'api.alerts.tasks.intelligence.*':  {'queue': 'intelligence'},
        'api.alerts.tasks.notification.*':  {'queue': 'notifications'},
        'api.alerts.tasks.channel_health_tasks.*': {'queue': 'health'},
    },

    # Result backend
    result_expires=3600,

    # Task execution limits
    task_soft_time_limit=300,
    task_time_limit=600,
    worker_max_tasks_per_child=1000,

    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    import logging
    logging.getLogger(__name__).info('Celery debug task running. Request: %r', self.request)
