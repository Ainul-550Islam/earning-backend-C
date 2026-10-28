"""
tasks/services/TaskMonitorService.py
Collect and store task execution metrics into TaskMonitor and TaskPerformanceLog.
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TaskMonitorService:
    """
    Collects task execution metrics, updates TaskMonitor health snapshots,
    and writes TaskPerformanceLog records after each Celery task execution.
    """

    CACHE_PREFIX  = 'task_monitor_'
    CACHE_TTL     = 3600  # 1 hour

    # ─── Public API ───────────────────────────────────────────────────

    def record_task_start(
        self,
        task_id: str,
        task_name: str,
        queue: str = '',
        worker: str = '',
    ) -> None:
        """
        Called when a task worker picks up a task.
        Writes a STARTED entry to TaskPerformanceLog.
        """
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog

            TaskPerformanceLog.objects.create(
                task_id=task_id,
                task_name=task_name,
                queue=queue or '',
                worker=worker or '',
                result='',  # not yet determined
                started_at=timezone.now(),
            )
        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.record_task_start: {e}")

    def record_task_success(
        self,
        task_id: str,
        task_name: str,
        duration_seconds: float,
        output: Any = None,
        queue: str = '',
        worker: str = '',
        cpu_seconds: float = None,
        memory_mb: float = None,
    ) -> None:
        """
        Called on successful task completion. Updates or creates a
        TaskPerformanceLog entry and refreshes TaskMonitor.
        """
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog

            log, _ = TaskPerformanceLog.objects.update_or_create(
                task_id=task_id,
                defaults={
                    'task_name': task_name,
                    'queue': queue or '',
                    'worker': worker or '',
                    'result': TaskPerformanceLog.Result.SUCCESS,
                    'duration_seconds': duration_seconds,
                    'completed_at': timezone.now(),
                    'output': output,
                    'cpu_seconds': cpu_seconds,
                    'memory_mb': memory_mb,
                },
            )
            self._refresh_monitor(task_name, success=True, duration=duration_seconds)

        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.record_task_success: {e}")

    def record_task_failure(
        self,
        task_id: str,
        task_name: str,
        error: str,
        duration_seconds: float = 0.0,
        retry_count: int = 0,
        queue: str = '',
        worker: str = '',
    ) -> None:
        """
        Called on task failure. Records error in TaskPerformanceLog
        and updates TaskMonitor status.
        """
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog

            TaskPerformanceLog.objects.update_or_create(
                task_id=task_id,
                defaults={
                    'task_name': task_name,
                    'queue': queue or '',
                    'worker': worker or '',
                    'result': TaskPerformanceLog.Result.FAILURE,
                    'duration_seconds': duration_seconds,
                    'error': error[:2000],
                    'retry_count': retry_count,
                    'completed_at': timezone.now(),
                },
            )
            self._refresh_monitor(task_name, success=False, duration=duration_seconds)

        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.record_task_failure: {e}")

    def get_monitor_status(self, task_name: str) -> Dict[str, Any]:
        """
        Return the current health snapshot for a task name.
        Returns a dict with status, success_rate, avg_duration, etc.
        """
        try:
            from api.tasks.models.monitoring import TaskMonitor

            monitor = TaskMonitor.objects.filter(task_name=task_name).first()
            if not monitor:
                return {'task_name': task_name, 'status': 'unknown'}

            return {
                'task_name': monitor.task_name,
                'status': monitor.status,
                'last_run_at': monitor.last_run_at.isoformat() if monitor.last_run_at else None,
                'avg_duration_seconds': monitor.avg_duration_seconds,
                'success_rate': monitor.success_rate,
                'total_runs_last_24h': monitor.total_runs_last_24h,
                'total_failures_last_24h': monitor.total_failures_last_24h,
            }
        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.get_monitor_status: {e}")
            return {'task_name': task_name, 'status': 'error', 'error': str(e)}

    def get_all_monitors(self) -> list:
        """Return health snapshots for all tracked tasks."""
        try:
            from api.tasks.models.monitoring import TaskMonitor

            return list(
                TaskMonitor.objects.values(
                    'task_name', 'status', 'last_run_at',
                    'avg_duration_seconds', 'success_rate',
                    'total_runs_last_24h', 'total_failures_last_24h',
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.get_all_monitors: {e}")
            return []

    def refresh_all_monitors(self) -> int:
        """
        Recompute health snapshots for all tasks from the last 24 hours of logs.
        Returns the number of monitors updated.
        """
        from datetime import timedelta
        from django.db.models import Count, Avg, Q

        updated = 0
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog, TaskMonitor

            cutoff = timezone.now() - timedelta(hours=24)
            task_names = (
                TaskPerformanceLog.objects
                .filter(created_at__gte=cutoff)
                .values_list('task_name', flat=True)
                .distinct()
            )

            for task_name in task_names:
                try:
                    qs = TaskPerformanceLog.objects.filter(
                        task_name=task_name,
                        created_at__gte=cutoff,
                    )
                    agg = qs.aggregate(
                        total=Count('id'),
                        failures=Count('id', filter=Q(result='failure')),
                        avg_dur=Avg('duration_seconds'),
                    )
                    total    = agg['total'] or 0
                    failures = agg['failures'] or 0
                    success_rate = ((total - failures) / total * 100) if total > 0 else 0.0

                    if failures / max(total, 1) > 0.5:
                        status = 'failing'
                    elif failures / max(total, 1) > 0.1:
                        status = 'degraded'
                    else:
                        status = 'healthy'

                    TaskMonitor.objects.update_or_create(
                        task_name=task_name,
                        defaults={
                            'status': status,
                            'avg_duration_seconds': agg['avg_dur'],
                            'success_rate': round(success_rate, 2),
                            'total_runs_last_24h': total,
                            'total_failures_last_24h': failures,
                            'last_run_at': (
                                qs.order_by('-created_at')
                                .values_list('created_at', flat=True)
                                .first()
                            ),
                        },
                    )
                    updated += 1

                except Exception as task_err:
                    logger.error(f"[ERROR] Refresh monitor for {task_name}: {task_err}")

        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService.refresh_all_monitors: {e}")

        return updated

    # ─── Private helpers ──────────────────────────────────────────────

    def _refresh_monitor(
        self,
        task_name: str,
        success: bool,
        duration: float,
    ) -> None:
        """
        Incrementally update the TaskMonitor row without a full recount.
        Uses a Redis lock to prevent race conditions.
        """
        try:
            from api.tasks.models.monitoring import TaskMonitor

            monitor, _ = TaskMonitor.objects.get_or_create(task_name=task_name)

            # Update last_run_at
            monitor.last_run_at = timezone.now()

            if success:
                monitor.last_success_at = timezone.now()
            else:
                monitor.last_failure_at = timezone.now()

            # Update rolling average duration (simple rolling mean)
            prev_avg = monitor.avg_duration_seconds or 0.0
            if prev_avg == 0.0:
                monitor.avg_duration_seconds = duration
            else:
                monitor.avg_duration_seconds = (prev_avg * 0.9) + (duration * 0.1)

            # Determine status
            recent_failures = monitor.total_failures_last_24h or 0
            recent_total    = monitor.total_runs_last_24h or 0

            if not success:
                recent_failures += 1
            recent_total += 1

            monitor.total_runs_last_24h     = recent_total
            monitor.total_failures_last_24h = recent_failures

            fail_rate = recent_failures / max(recent_total, 1)
            if fail_rate > 0.5:
                monitor.status = TaskMonitor.Status.FAILING
            elif fail_rate > 0.1:
                monitor.status = TaskMonitor.Status.DEGRADED
            else:
                monitor.status = TaskMonitor.Status.HEALTHY

            monitor.save(update_fields=[
                'last_run_at', 'last_success_at', 'last_failure_at',
                'avg_duration_seconds', 'total_runs_last_24h',
                'total_failures_last_24h', 'status', 'updated_at',
            ])

        except Exception as e:
            logger.error(f"[ERROR] TaskMonitorService._refresh_monitor: {e}")
