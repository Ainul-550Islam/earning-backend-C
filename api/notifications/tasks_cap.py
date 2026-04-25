# earning_backend/api/notifications/tasks_cap.py
"""
Tasks CAP (Capacity) — Celery task registry and task metadata manager.

"CAP" = Capacity layer:
  1. Registers all notification Celery tasks in one place
  2. Provides task_exists(), get_task(), revoke_task() helpers
  3. Tracks task metadata (queue, priority, max_retries)
  4. Provides bulk task management (cancel_user_tasks, retry_failed)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task metadata registry
# ---------------------------------------------------------------------------

TASK_REGISTRY: Dict[str, dict] = {
    # Core send tasks
    'notifications.send_push_batch':      {'queue': 'notifications_push', 'max_retries': 3, 'priority': 'high'},
    'notifications.send_push_multicast':  {'queue': 'notifications_push', 'max_retries': 3, 'priority': 'high'},
    'notifications.send_email_batch':     {'queue': 'notifications_email', 'max_retries': 3, 'priority': 'high'},
    'notifications.send_sms_batch':       {'queue': 'notifications_sms', 'max_retries': 2, 'priority': 'high'},

    # Campaign tasks
    'notifications.process_campaign':         {'queue': 'notifications_campaigns', 'max_retries': 2},
    'notifications.start_scheduled_campaigns':{'queue': 'notifications_campaigns', 'max_retries': 1},
    'notifications.evaluate_ab_test':         {'queue': 'notifications_campaigns', 'max_retries': 1},
    'notifications.process_batch':            {'queue': 'notifications_batch', 'max_retries': 2},

    # Retry / scheduling tasks
    'notifications.retry_notification':            {'queue': 'notifications_retry', 'max_retries': 3},
    'notifications.process_all_retries':           {'queue': 'notifications_retry', 'max_retries': 1},
    'notifications.send_scheduled_notifications':  {'queue': 'notifications_scheduled', 'max_retries': 1},
    'notifications.cancel_overdue_schedules':      {'queue': 'notifications_scheduled', 'max_retries': 1},

    # Analytics and maintenance
    'notifications.run_all_daily_analytics':    {'queue': 'notifications_analytics', 'max_retries': 1},
    'notifications.refresh_delivery_rates':     {'queue': 'notifications_analytics', 'max_retries': 1},
    'notifications.run_all_cleanup':            {'queue': 'notifications_maintenance', 'max_retries': 1},
    'notifications.reset_daily_fatigue_counters':{'queue': 'notifications_maintenance', 'max_retries': 1},
    'notifications.refresh_stale_fcm_tokens':   {'queue': 'notifications_maintenance', 'max_retries': 1},

    # Integration system tasks
    'notifications.integration.dispatch_event':   {'queue': 'notifications_high', 'max_retries': 3},
    'notifications.integration.retry_integration':{'queue': 'notifications_high', 'max_retries': 3},
    'notifications.integration.run_health_checks':{'queue': 'notifications_maintenance', 'max_retries': 1},

    # Journey tasks
    'notifications.execute_journey_step':         {'queue': 'notifications_campaigns', 'max_retries': 2},
    'notifications.enroll_users_in_journey':      {'queue': 'notifications_campaigns', 'max_retries': 1},
}


# ---------------------------------------------------------------------------
# Task management helpers
# ---------------------------------------------------------------------------

def task_exists(task_name: str) -> bool:
    """Check if a named task is registered."""
    return task_name in TASK_REGISTRY


def get_task_meta(task_name: str) -> Optional[dict]:
    """Get metadata for a task."""
    return TASK_REGISTRY.get(task_name)


def get_task_queue(task_name: str) -> str:
    """Get the queue name for a task."""
    return TASK_REGISTRY.get(task_name, {}).get('queue', 'default')


def list_tasks(queue: str = None) -> List[str]:
    """List all registered task names, optionally filtered by queue."""
    if queue:
        return [n for n, m in TASK_REGISTRY.items() if m.get('queue') == queue]
    return list(TASK_REGISTRY.keys())


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """Revoke a Celery task by ID."""
    try:
        from celery import current_app
        current_app.control.revoke(task_id, terminate=terminate)
        logger.info(f'tasks_cap: revoked task {task_id}')
        return True
    except Exception as exc:
        logger.warning(f'tasks_cap.revoke_task {task_id}: {exc}')
        return False


def cancel_user_notification_tasks(user_id: int) -> int:
    """
    Cancel all pending notification tasks for a specific user.
    Useful when a user account is suspended or deleted.
    """
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=3)
        scheduled = inspector.scheduled() or {}
        revoked = 0
        for worker_tasks in scheduled.values():
            for task in worker_tasks:
                args = task.get('request', {}).get('args', [])
                if args and args[0] == user_id:
                    revoke_task(task['request']['id'])
                    revoked += 1
        return revoked
    except Exception as exc:
        logger.warning(f'tasks_cap.cancel_user_notification_tasks: {exc}')
        return 0


def get_queue_stats() -> Dict[str, dict]:
    """Get stats for all notification queues."""
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=3)
        active = inspector.active() or {}
        scheduled = inspector.scheduled() or {}
        reserved = inspector.reserved() or {}

        queues = {}
        for task_list in list(active.values()) + list(scheduled.values()) + list(reserved.values()):
            for task in task_list:
                queue = task.get('delivery_info', {}).get('routing_key', 'unknown')
                queues.setdefault(queue, {'active': 0, 'scheduled': 0, 'reserved': 0})

        return queues
    except Exception as exc:
        logger.warning(f'tasks_cap.get_queue_stats: {exc}')
        return {}


def enqueue_notification_send(notification_id: int, channel: str = 'in_app', priority: str = 'medium') -> Optional[str]:
    """
    Enqueue a notification for sending via the appropriate Celery task.
    Returns the Celery task ID or None on failure.
    """
    try:
        from notifications.tasks.send_push_tasks import send_push_batch_task
        from notifications.tasks.send_email_tasks import send_email_batch_task
        from notifications.tasks.send_sms_tasks import send_sms_batch_task

        queue_map = {
            'push': ('notifications_push', send_push_batch_task),
            'email': ('notifications_email', send_email_batch_task),
            'sms': ('notifications_sms', send_sms_batch_task),
        }

        if channel in queue_map:
            queue_name, task = queue_map[channel]
            result = task.apply_async(
                args=[[notification_id]],
                queue=queue_name,
            )
            return result.id
        else:
            # in_app / all — use the high priority queue
            from notifications.tasks.delivery_tracking_tasks import mark_notification_delivered_task
            result = mark_notification_delivered_task.apply_async(
                args=[notification_id],
                queue='notifications_high',
            )
            return result.id
    except Exception as exc:
        logger.error(f'tasks_cap.enqueue_notification_send: {exc}')
        return None
