# api/notifications/integration_system/tasks.py
"""Celery tasks for the integration system (sub-package of notifications)."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, max_retries=3,
    queue='notifications_high',
    name='notifications.integration.dispatch_event',
)
def dispatch_event_task(self, event_dict: dict):
    """Dispatch an event to all subscribers (called by EventBus async path)."""
    try:
        from api.notifications.integration_system.event_bus import event_bus
        event_bus.execute_event(event_dict)
    except Exception as exc:
        logger.error(f'dispatch_event_task: {exc}')
        try:
            self.retry(exc=exc, countdown=60)
        except Exception:
            pass


@shared_task(
    bind=True, max_retries=3,
    queue='notifications_high',
    name='notifications.integration.retry_integration',
)
def retry_integration_task(self, integration_name: str, payload: dict):
    """Retry a failed integration operation."""
    try:
        from api.notifications.integration_system.integ_handler import handler
        return handler.trigger(integration_name, payload)
    except Exception as exc:
        logger.error(f'retry_integration_task {integration_name}: {exc}')
        try:
            self.retry(exc=exc, countdown=120)
        except Exception:
            return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_batch',
    name='notifications.integration.process_queue_message',
)
def process_queue_message_task(msg_dict: dict):
    """Process a single message from the integration message queue."""
    try:
        from api.notifications.integration_system.message_queue import message_queue
        return message_queue.process_message(msg_dict)
    except Exception as exc:
        logger.error(f'process_queue_message_task: {exc}')
        return False


@shared_task(
    queue='notifications_maintenance',
    name='notifications.integration.persist_audit_log',
)
def persist_audit_log_task(entry_dict: dict):
    """Persist an audit log entry to the database."""
    try:
        logger.info(
            f"[AuditLog] {entry_dict.get('action')} | "
            f"{entry_dict.get('module')} | "
            f"actor={entry_dict.get('actor_id')} | "
            f"success={entry_dict.get('success')}"
        )
        # TODO: Save to AuditLog DB model when model is created
    except Exception as exc:
        logger.warning(f'persist_audit_log_task: {exc}')


@shared_task(
    queue='notifications_maintenance',
    name='notifications.integration.run_health_checks',
)
def run_health_checks_task():
    """Run health checks for all integrated services."""
    try:
        from api.notifications.integration_system.health_check import health_checker
        summary = health_checker.get_summary()
        overall = summary.get('overall', 'unknown')
        logger.info(f'[HealthCheck] overall={overall}')

        # Alert if degraded or unhealthy
        if overall in ('degraded', 'unhealthy'):
            from api.notifications.integration_system.event_bus import event_bus
            from api.notifications.integration_system.integ_constants import Events
            event_bus.publish(
                Events.SYSTEM_HEALTH_DEGRADED,
                data=summary,
                source_module='health_check',
                async_dispatch=False,
            )
        return summary
    except Exception as exc:
        logger.error(f'run_health_checks_task: {exc}')
        return {'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.integration.sync_event_bus_stats',
)
def sync_event_bus_stats_task():
    """Log EventBus statistics for monitoring."""
    try:
        from api.notifications.integration_system.event_bus import event_bus
        stats = event_bus.stats()
        logger.info(
            f"[EventBus] published={stats['published_count']} "
            f"failed={stats['failed_count']} "
            f"event_types={stats['total_event_types']}"
        )
        return stats
    except Exception as exc:
        logger.error(f'sync_event_bus_stats_task: {exc}')
        return {}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.integration.auto_discover',
)
def auto_discover_task():
    """Re-run auto-discovery (useful in dev after adding a new module)."""
    try:
        from api.notifications.integration_system.auto_discovery import auto_discovery
        results = auto_discovery.discover_all()
        discovered = [k for k, v in results.items() if v]
        return {'discovered': discovered, 'total': len(discovered)}
    except Exception as exc:
        logger.error(f'auto_discover_task: {exc}')
        return {'error': str(exc)}
