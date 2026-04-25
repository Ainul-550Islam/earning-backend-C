# earning_backend/api/notifications/tasks/background_tasks.py
"""Background Celery tasks — workflow execution and misc background jobs."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, max_retries=2,
    queue='notifications_campaigns',
    name='notifications.execute_workflow',
)
def execute_workflow_task(self, workflow_id: str, user_id: int, data: dict):
    """Execute a workflow for a user (called by WorkflowEngine async path)."""
    try:
        from django.contrib.auth import get_user_model
        from api.notifications.workflow import workflow_engine
        User = get_user_model()
        user = User.objects.get(pk=user_id) if user_id else None
        return workflow_engine._execute_sync(
            workflow_engine.get_workflow(workflow_id),
            user, data
        )
    except Exception as exc:
        logger.error(f'execute_workflow_task {workflow_id}: {exc}')
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            return {'executed': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.run_data_retention',
)
def run_data_retention_task(dry_run: bool = False):
    """Enforce data retention policy — delete expired notification data."""
    try:
        from api.notifications.compliance import data_retention_service
        return data_retention_service.enforce_retention(dry_run=dry_run)
    except Exception as exc:
        logger.error(f'run_data_retention_task: {exc}')
        return {'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.trigger_inactive_workflows',
)
def trigger_inactive_user_workflows():
    """Find users inactive for 3+ days and trigger reengagement workflows."""
    try:
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        from api.notifications.workflow import workflow_engine

        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=3)
        inactive_users = User.objects.filter(
            is_active=True,
            last_login__lt=cutoff,
        ).exclude(last_login=None)[:1000]

        triggered = 0
        for user in inactive_users:
            result = workflow_engine.trigger('inactive_user_3d', user=user, data={}, async_exec=False)
            if result.get('executed'):
                triggered += 1

        logger.info(f'trigger_inactive_user_workflows: triggered for {triggered} users')
        return {'triggered': triggered}
    except Exception as exc:
        logger.error(f'trigger_inactive_user_workflows: {exc}')
        return {'error': str(exc)}


@shared_task(
    queue='notifications_analytics',
    name='notifications.compute_rfm_segments',
)
def compute_rfm_segments_task(limit: int = 5000):
    """Pre-compute RFM segments and cache results for fast campaign targeting."""
    try:
        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        from api.notifications.funnel import rfm_service

        User = get_user_model()
        segment_map = {}

        for user in User.objects.filter(is_active=True)[:limit].iterator():
            score = rfm_service.score_user(user)
            segment = score['segment']
            segment_map.setdefault(segment, []).append(user.pk)

        # Cache each segment for 6 hours
        for segment, user_ids in segment_map.items():
            cache.set(f'rfm:segment:{segment}', user_ids, 21600)

        total = sum(len(v) for v in segment_map.values())
        logger.info(f'compute_rfm_segments: processed {total} users across {len(segment_map)} segments')
        return {
            'segments': {k: len(v) for k, v in segment_map.items()},
            'total': total
        }
    except Exception as exc:
        logger.error(f'compute_rfm_segments_task: {exc}')
        return {'error': str(exc)}


@shared_task(
    queue='notifications_analytics',
    name='notifications.run_monitoring_check',
)
def run_monitoring_check_task():
    """Run system-wide monitoring checks."""
    try:
        from api.notifications.monitoring import run_monitoring_check
        return run_monitoring_check()
    except Exception as exc:
        logger.error(f'run_monitoring_check_task: {exc}')
        return {'error': str(exc)}
