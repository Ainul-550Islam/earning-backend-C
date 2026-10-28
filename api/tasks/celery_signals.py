"""
tasks/celery_signals.py
Hook into Celery's task_success, task_failure, task_retry signals
to automatically record TaskPerformanceLog and update TaskMonitor.
Also routes exhausted tasks to DeadLetterQueue.
"""
import logging
import time
from django.utils import timezone

logger = logging.getLogger(__name__)


def connect_celery_signals():
    """Connect all Celery signal handlers. Called from TasksConfig.ready()."""
    try:
        from celery.signals import (
            task_success,
            task_failure,
            task_retry,
            task_prerun,
            task_postrun,
            worker_ready,
            worker_shutdown,
            beat_init,
        )

        task_prerun.connect(on_task_prerun,    weak=False)
        task_postrun.connect(on_task_postrun,  weak=False)
        task_success.connect(on_task_success,  weak=False)
        task_failure.connect(on_task_failure,  weak=False)
        task_retry.connect(on_task_retry,      weak=False)
        worker_ready.connect(on_worker_ready,  weak=False)
        worker_shutdown.connect(on_worker_shutdown, weak=False)

        logger.info("[OK] Celery monitoring signals connected.")

    except ImportError as e:
        logger.warning(f"[WARN] Could not connect Celery signals: {e}")
    except Exception as e:
        logger.error(f"[ERROR] connect_celery_signals: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Signal Handlers
# ─────────────────────────────────────────────────────────────────────────────

# Per-request start-time storage (thread-local via task request)
_TASK_START_TIMES: dict = {}


def on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    """Record task start time when worker picks it up."""
    if task_id:
        _TASK_START_TIMES[task_id] = time.monotonic()
    try:
        from api.tasks.services.TaskMonitorService import TaskMonitorService
        TaskMonitorService().record_task_start(
            task_id=task_id or '',
            task_name=getattr(task, 'name', 'unknown'),
            queue=getattr(getattr(task, 'request', None), 'delivery_info', {}).get('routing_key', ''),
            worker=getattr(getattr(task, 'request', None), 'hostname', ''),
        )
    except Exception as e:
        logger.debug(f"[DEBUG] on_task_prerun monitor: {e}")


def on_task_postrun(sender=None, task_id=None, task=None, retval=None, state=None, **kw):
    """Clean up start-time tracking after task completes."""
    _TASK_START_TIMES.pop(task_id, None)


def on_task_success(sender=None, result=None, **kw):
    """Record successful task execution."""
    try:
        task_id   = getattr(sender.request, 'id', '') if sender else ''
        task_name = getattr(sender, 'name', 'unknown') if sender else 'unknown'
        start     = _TASK_START_TIMES.pop(task_id, None)
        duration  = (time.monotonic() - start) if start else 0.0

        from api.tasks.services.TaskMonitorService import TaskMonitorService
        TaskMonitorService().record_task_success(
            task_id=task_id,
            task_name=task_name,
            duration_seconds=duration,
            output=result if isinstance(result, dict) else None,
        )
    except Exception as e:
        logger.debug(f"[DEBUG] on_task_success: {e}")


def on_task_failure(
    sender=None, task_id=None, exception=None, traceback=None,
    einfo=None, args=None, kwargs=None, **kw
):
    """Record failed task and route to DLQ if max retries exhausted."""
    try:
        task_id   = task_id or (getattr(sender.request, 'id', '') if sender else '')
        task_name = getattr(sender, 'name', 'unknown') if sender else 'unknown'
        error_str = str(exception) if exception else 'Unknown error'
        tb_str    = str(einfo) if einfo else ''
        start     = _TASK_START_TIMES.pop(task_id, None)
        duration  = (time.monotonic() - start) if start else 0.0

        retry_count = getattr(getattr(sender, 'request', None), 'retries', 0) if sender else 0
        max_retries = getattr(sender, 'max_retries', 0) if sender else 0

        from api.tasks.services.TaskMonitorService import TaskMonitorService
        TaskMonitorService().record_task_failure(
            task_id=task_id,
            task_name=task_name,
            error=error_str,
            duration_seconds=duration,
            retry_count=retry_count,
        )

        # Route to DLQ if retries exhausted
        if retry_count >= max_retries:
            try:
                from api.tasks.services.RetryService import RetryService
                RetryService().handle_failure(
                    task_name=task_name,
                    task_id=task_id,
                    exception=exception or Exception(error_str),
                    traceback_str=tb_str,
                    retry_count=retry_count,
                    payload={
                        'args': list(args or []),
                        'kwargs': dict(kwargs or {}),
                    },
                )
            except Exception as retry_err:
                logger.error(f"[ERROR] RetryService.handle_failure: {retry_err}")

    except Exception as e:
        logger.debug(f"[DEBUG] on_task_failure: {e}")


def on_task_retry(sender=None, request=None, reason=None, einfo=None, **kw):
    """Log task retry event."""
    try:
        task_name   = getattr(sender, 'name', 'unknown') if sender else 'unknown'
        retry_count = getattr(request, 'retries', 0) if request else 0
        logger.info(f"[RETRY] {task_name} retry #{retry_count}: {reason}")
    except Exception as e:
        logger.debug(f"[DEBUG] on_task_retry: {e}")


def on_worker_ready(sender=None, **kw):
    """Record worker coming online."""
    try:
        from api.tasks.services.WorkerHealthService import WorkerHealthService
        WorkerHealthService().refresh(timeout=2.0)
        logger.info("[OK] Worker ready — WorkerHealth refreshed")
    except Exception as e:
        logger.debug(f"[DEBUG] on_worker_ready: {e}")


def on_worker_shutdown(sender=None, **kw):
    """Mark worker as offline when it shuts down."""
    try:
        from api.tasks.models.monitoring import WorkerHealth
        hostname = getattr(sender, 'hostname', '')
        if hostname:
            WorkerHealth.objects.filter(worker_id__icontains=hostname).update(
                status=WorkerHealth.Status.OFFLINE
            )
            logger.info(f"[OK] Worker {hostname} marked offline on shutdown")
    except Exception as e:
        logger.debug(f"[DEBUG] on_worker_shutdown: {e}")
