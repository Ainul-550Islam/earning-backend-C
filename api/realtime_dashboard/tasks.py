"""
Celery tasks for Real-time Dashboard Backend.

Register the Celery app in your project's celery.py and add
CELERY_BEAT_SCHEDULE to settings.py, e.g.:\n

    # settings.py
    from celery.schedules import crontab

    CELERY_BEAT_SCHEDULE = {
        'cleanup-stale-websocket-connections': {
            'task': 'api.realtime_dashboard.tasks.cleanup_stale_connections',
            'schedule': crontab(minute='*/15'),   # every 15 minutes
            'kwargs': {'timeout_seconds': 3600},
        },
        'broadcast-active-metrics': {
            'task': 'api.realtime_dashboard.tasks.broadcast_active_metrics',
            'schedule': 30.0,  # every 30 seconds
        },
    }
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name='api.realtime_dashboard.tasks.cleanup_stale_connections',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_stale_connections(self, timeout_seconds: int = 3600) -> dict:
    """
    Periodic Celery task: mark WebSocketConnection rows whose last_ping
    is older than `timeout_seconds` as disconnected.

    Without this task, the WebSocketConnection table grows indefinitely
    and the `.active()` queryset returns ghost rows for crashed clients
    that never sent a clean disconnect frame.

    Args:
        timeout_seconds: Connections silent for longer than this are
                         considered stale (default 1 hour).

    Returns:
        dict with 'cleaned' count and 'timeout_seconds' used.
    """
    try:
        # OWNERSHIP FIX: previously imported WebSocketManager() directly,
        # bypassing the service layer. WebSocketManagerService is the
        # single owner of connection-lifecycle operations; tasks must call
        # it the same way consumers and signals do.
        from .services.websocket_manager_service import WebSocketManagerService
        count = WebSocketManagerService().cleanup_old_connections(timeout_seconds)
        logger.info(
            'cleanup_stale_connections: marked %d connection(s) as disconnected '
            '(timeout=%ds)', count, timeout_seconds
        )
        return {'cleaned': count, 'timeout_seconds': timeout_seconds}
    except Exception as exc:
        logger.exception('cleanup_stale_connections failed, retrying: %s', exc)
        raise self.retry(exc=exc)


@shared_task(
    name='api.realtime_dashboard.tasks.broadcast_active_metrics',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def broadcast_active_metrics(self) -> dict:
    """
    Periodic Celery task: push the current value of every active metric
    to all subscribed WebSocket clients via EventStreamingService.

    This ensures clients receive a periodic refresh even when no
    RealTimeMetric.save() signal fires (e.g. the metric value has not
    changed but the client just connected and needs current state).

    Returns:
        dict with 'metric_count' broadcast.
    """
    try:
        from .models.real_time_metric import RealTimeMetric
        from .services.event_streaming_service import EventStreamingService

        active_ids = list(
            RealTimeMetric.objects.active().values_list('id', flat=True)
        )
        if active_ids:
            EventStreamingService().stream_metric_updates(active_ids)
        logger.info('broadcast_active_metrics: broadcast %d active metric(s)', len(active_ids))
        return {'metric_count': len(active_ids)}
    except Exception as exc:
        logger.exception('broadcast_active_metrics failed, retrying: %s', exc)
        raise self.retry(exc=exc)
