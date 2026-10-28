"""
tasks/celery_tasks.py
Celery task functions that drive internal task-system operations:
  - execute_workflow_instance    → run a WorkflowInstance step-by-step
  - run_task_monitor_refresh     → periodic TaskMonitor refresh
  - run_alert_evaluation         → evaluate all TaskAlerts
  - run_queue_depth_snapshot     → snapshot all queue depths
  - run_worker_health_refresh    → refresh WorkerHealth records
  - run_analytics_rollup         → daily analytics rollup
  - run_cost_estimation          → refresh TaskCostEstimate records
  - send_dlq_summary_email       → email DLQ stats to admins
  - cleanup_abandoned_task_locks → cleanup expired task locks (PART 9)
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PART 9: CLEANUP ABANDONED TASK LOCKS
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    name='tasks.celery_tasks.cleanup_abandoned_task_locks',
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes hard limit
)
def cleanup_abandoned_task_locks(self):
    """
    Remove expired locks (runs every 5 minutes via celery beat).
    
    Design:
    ✓ Finds locks WHERE expires_at < NOW()
    ✓ Deletes expired locks (releases task for new users)
    ✓ Logs each cleanup in TaskEventLog for audit trail
    ✓ Batches operations to prevent long database locks
    
    Scheduled in: celery_beat_config.py
    Schedule: Every 5 minutes
    
    Example log entry:
    {
        "event_type": "LOCK_EXPIRED",
        "task_id": 123,
        "user_id": 456,
        "event_data": {
            "lock_id": "abc-123-def",
            "held_duration_seconds": 1800,
            "reason": "expired"
        }
    }
    """
    try:
        from api.tasks.services_lock import TaskLockService
        
        service = TaskLockService()
        cleaned_count = service.cleanup_expired_locks(batch_size=1000)
        
        logger.info(f"✓ Task lock cleanup: removed {cleaned_count} expired locks")
        
        return {
            'success': True,
            'cleaned_count': cleaned_count,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"✗ Error in cleanup_abandoned_task_locks: {str(e)}", exc_info=True)
        
        # Retry up to 2 times with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


# ─────────────────────────────────────────────────────────────────────────────
# execute_workflow_instance
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=0,
    name='tasks.celery_tasks.execute_workflow_instance',
    soft_time_limit=7200,
    time_limit=7500,
)
def execute_workflow_instance(self, instance_id: int) -> dict:
    """
    Execute a WorkflowInstance step-by-step synchronously on the worker.
    Called by WorkflowService.trigger_workflow() when async_execute=True.
    Iterates steps in order, passes outputs through context,
    handles on_failure behaviour (stop / continue / rollback).
    """
    try:
        from api.tasks.models.workflow import WorkflowInstance, WorkflowStep
        from api.tasks.services.WorkflowStepService import WorkflowStepService

        inst = WorkflowInstance.objects.select_related('workflow').get(pk=instance_id)
    except Exception as e:
        logger.error(f"[ERROR] execute_workflow_instance: instance {instance_id} not found: {e}")
        return {'success': False, 'error': str(e)}

    # Already done or cancelled
    if inst.status in ('success', 'failed', 'cancelled'):
        return {'success': True, 'status': inst.status, 'note': 'already_terminal'}

    inst.start()
    svc    = WorkflowStepService()
    steps  = list(
        WorkflowStep.objects.filter(
            workflow=inst.workflow, is_active=True
        ).order_by('step_number')
    )

    workflow_success = True
    stop_reason      = ''

    for step in steps:
        logger.info(
            f"[WF] Instance #{instance_id} executing step {step.step_number}: {step.task_name}"
        )

        result = svc.execute_step(instance_id=inst.pk, step_number=step.step_number)

        if result.get('skipped'):
            logger.info(f"[WF] Step {step.step_number} skipped (condition false)")
            continue

        if not result.get('success'):
            logger.error(
                f"[WF] Step {step.step_number} failed: {result.get('error')}"
            )
            on_failure = step.on_failure

            if on_failure == 'stop':
                workflow_success = False
                stop_reason      = result.get('error', 'step_failed')
                break

            elif on_failure == 'continue':
                logger.warning(f"[WF] on_failure=continue — skipping step {step.step_number}")
                continue

            elif on_failure == 'retry':
                # Already retried inside execute_step per step.max_retries
                workflow_success = False
                stop_reason      = result.get('error', 'step_failed_after_retries')
                break

            elif on_failure == 'rollback':
                logger.warning(f"[WF] Rollback triggered at step {step.step_number}")
                workflow_success = False
                stop_reason      = 'rollback'
                break

    inst.complete(success=workflow_success, error=stop_reason)

    logger.info(
        f"[WF] Instance #{instance_id} {'SUCCESS' if workflow_success else 'FAILED'}: {stop_reason or 'ok'}"
    )
    return {
        'success': workflow_success,
        'instance_id': instance_id,
        'status': inst.status,
        'error': stop_reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# run_task_monitor_refresh
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.celery_tasks.run_task_monitor_refresh',
)
def run_task_monitor_refresh(self) -> dict:
    """Recompute TaskMonitor health snapshots for all tasks."""
    try:
        from api.tasks.services.TaskMonitorService import TaskMonitorService
        updated = TaskMonitorService().refresh_all_monitors()
        logger.info(f"[OK] TaskMonitor refresh: {updated} monitors updated")
        return {'status': 'success', 'updated': updated, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        logger.error(f"[ERROR] run_task_monitor_refresh: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# run_alert_evaluation
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.celery_tasks.run_alert_evaluation',
)
def run_alert_evaluation(self) -> dict:
    """Evaluate all active TaskAlert rules and fire notifications."""
    try:
        from api.tasks.services.TaskAlertService import TaskAlertService
        fired = TaskAlertService().evaluate_all()
        logger.info(f"[OK] Alert evaluation: {len(fired)} alerts fired")
        return {'status': 'success', 'alerts_fired': len(fired), 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        logger.error(f"[ERROR] run_alert_evaluation: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# run_queue_depth_snapshot
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.celery_tasks.run_queue_depth_snapshot',
)
def run_queue_depth_snapshot(self) -> dict:
    """Snapshot all queue depths to QueueDepth model."""
    try:
        from api.tasks.services.QueueDepthService import QueueDepthService
        snapshots = QueueDepthService().snapshot_all()
        logger.info(f"[OK] Queue depth snapshot: {len(snapshots)} queues")
        return {'status': 'success', 'queues': len(snapshots), 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        logger.error(f"[ERROR] run_queue_depth_snapshot: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# run_worker_health_refresh
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=15,
    name='tasks.celery_tasks.run_worker_health_refresh',
)
def run_worker_health_refresh(self) -> dict:
    """Refresh WorkerHealth records from Celery inspect."""
    try:
        from api.tasks.services.WorkerHealthService import WorkerHealthService
        summary = WorkerHealthService().refresh(timeout=3.0)
        logger.info(f"[OK] Worker health refresh: {summary.get('online', 0)} online")
        return {'status': 'success', **summary}
    except Exception as exc:
        logger.error(f"[ERROR] run_worker_health_refresh: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# run_analytics_rollup
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='tasks.celery_tasks.run_analytics_rollup',
)
def run_analytics_rollup(self, date_str: str = None) -> dict:
    """Daily analytics rollup — delegates to analytics_tasks.daily_analytics_rollup."""
    try:
        from api.tasks.analytics_tasks import daily_analytics_rollup
        result = daily_analytics_rollup.apply(kwargs={'date_str': date_str})
        data   = result.get()
        logger.info(f"[OK] Analytics rollup: {data}")
        return data
    except Exception as exc:
        logger.error(f"[ERROR] run_analytics_rollup: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# run_cost_estimation
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.celery_tasks.run_cost_estimation',
)
def run_cost_estimation(self) -> dict:
    """Refresh TaskCostEstimate records for all tasks."""
    try:
        from api.tasks.services.TaskCostService import TaskCostService
        result = TaskCostService().refresh_all()
        logger.info(f"[OK] Cost estimation: {result}")
        return {'status': 'success', **result, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        logger.error(f"[ERROR] run_cost_estimation: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# send_dlq_summary_email
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.celery_tasks.send_dlq_summary_email',
)
def send_dlq_summary_email(self) -> dict:
    """Email DLQ statistics to all admin users."""
    try:
        from api.tasks.services.DeadLetterService import DeadLetterService
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model
        from django.conf import settings

        stats  = DeadLetterService().get_stats()
        total  = stats.get('total', 0)
        pending = stats.get('pending', 0)

        if pending == 0:
            logger.info("[OK] DLQ email: no pending entries — skipping.")
            return {'status': 'skipped', 'reason': 'no_pending'}

        User   = get_user_model()
        emails = list(
            User.objects.filter(is_staff=True, is_active=True)
            .exclude(email='')
            .values_list('email', flat=True)
        )

        if not emails:
            return {'status': 'skipped', 'reason': 'no_admin_emails'}

        top_tasks = '\n'.join(
            f"  {t['count']:>5}x  {t['task_name']}"
            for t in stats.get('top_failing_tasks', [])[:5]
        )

        subject = f"[DLQ Alert] {pending} Pending Dead Letter Queue Entries"
        body    = (
            f"Dead Letter Queue Summary — {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"  Total entries : {total}\n"
            f"  Pending       : {pending}\n"
            f"  Requeued      : {stats.get('requeued', 0)}\n"
            f"  Discarded     : {stats.get('discarded', 0)}\n\n"
            f"Top failing tasks:\n{top_tasks or '  (none)'}\n\n"
            f"Please log in to the admin panel to review and retry/discard entries."
        )

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=emails,
            fail_silently=False,
        )

        logger.info(f"[OK] DLQ summary emailed to {len(emails)} admins.")
        return {
            'status': 'success',
            'pending': pending,
            'emails_sent_to': len(emails),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] send_dlq_summary_email: {exc}")
        raise self.retry(exc=exc)
