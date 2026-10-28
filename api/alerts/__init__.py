"""
alerts package init.

Ensures the Celery app defined in alerts/celery_app.py is imported as
soon as Django loads this app, so that:
  * `api.alerts.celery_app.app` becomes Celery's default/current app, which
    is required for `@shared_task`-decorated tasks (used throughout
    alerts/tasks/*) to bind to it instead of falling back to a
    default Celery() instance that never reads Django settings.
  * Django-sourced settings such as CELERY_TASK_ALWAYS_EAGER are
    actually honoured. Without this import, tasks silently fall back
    to celery's built-in defaults (eager mode OFF, default broker),
    which makes `.delay()` attempt a real broker connection on every
    call -- slow and broken in dev/test, and a correctness bug in any
    deployment that doesn't happen to start a worker process first.
  * `celery -A alerts worker` can discover the app.

This mirrors Celery's documented Django integration pattern.
"""
from .celery_app import app as celery_app

__all__ = ('celery_app',)
