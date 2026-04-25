# earning_backend/api/notifications/celery_beat_config.py
"""
Celery Beat Config — Complete periodic task schedule for notifications.
Alias for celery_beat_schedule.py with additional runtime helpers.
"""
from .celery_beat_schedule import NOTIFICATION_BEAT_SCHEDULE, NOTIFICATION_QUEUES
from .tasks_cap import TASK_REGISTRY


def get_beat_schedule() -> dict:
    """Return the complete Celery Beat schedule."""
    return NOTIFICATION_BEAT_SCHEDULE


def get_queues() -> list:
    """Return all notification queue names."""
    return NOTIFICATION_QUEUES


def get_all_task_names() -> list:
    """Return all registered notification task names."""
    return list(TASK_REGISTRY.keys())


def apply_to_settings(settings_module):
    """
    Apply notification Celery config to a Django settings module.

    Usage in settings.py:
        from api.notifications.celery_beat_config import apply_to_settings
        apply_to_settings(globals())
    """
    existing = settings_module.get('CELERY_BEAT_SCHEDULE', {})
    existing.update(NOTIFICATION_BEAT_SCHEDULE)
    settings_module['CELERY_BEAT_SCHEDULE'] = existing

    existing_routes = settings_module.get('CELERY_TASK_ROUTES', {})
    from .celery_config import NOTIFICATION_TASK_ROUTES
    existing_routes.update(NOTIFICATION_TASK_ROUTES)
    settings_module['CELERY_TASK_ROUTES'] = existing_routes
