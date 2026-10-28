"""
tasks/viewsets/AdminTaskViewSet.py
Superadmin task management viewset — combines all task system controls
in one place: dashboard, run any task, manage DLQ, trigger workflows,
export data, refresh analytics, system health.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class AdminTaskViewSet(viewsets.ViewSet):
    """
    Superadmin-only ViewSet providing a unified interface for:
    - Dashboard overview
    - Dispatching arbitrary Celery tasks
    - DLQ management
    - Worker management
    - Analytics refresh
    - Export triggers
    - System health
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    # ─── Dashboard ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Return full admin task dashboard data."""
        from api.tasks.services.TaskDashboardService import TaskDashboardService
        force = request.query_params.get('force', 'false').lower() == 'true'
        data  = TaskDashboardService().get_dashboard_data(force_refresh=force)
        return Response(data)

    # ─── Task Dispatch ────────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def dispatch(self, request):
        """
        Dispatch any registered Celery task by name.
        Body: { task_name, kwargs, queue, countdown }
        """
        task_name  = request.data.get('task_name')
        kwargs     = request.data.get('kwargs', {})
        queue      = request.data.get('queue', 'default')
        countdown  = int(request.data.get('countdown', 0))

        if not task_name:
            return Response(
                {'error': 'task_name is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from celery import current_app
            result = current_app.send_task(
                task_name,
                kwargs=kwargs,
                queue=queue,
                countdown=countdown,
            )
            logger.info(f"[ADMIN] Dispatched '{task_name}' by {request.user} → id={result.id}")
            return Response({'task_id': result.id, 'task_name': task_name, 'status': 'queued'})
        except Exception as e:
            logger.error(f"[ERROR] AdminTaskViewSet.dispatch: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def dispatch_batch(self, request):
        """
        Dispatch multiple tasks in one call.
        Body: { tasks: [{task_name, kwargs, queue}] }
        """
        tasks   = request.data.get('tasks', [])
        results = []
        errors  = []

        try:
            from celery import current_app
            for t in tasks:
                task_name = t.get('task_name')
                if not task_name:
                    errors.append({'error': 'task_name missing', 'task': t})
                    continue
                try:
                    r = current_app.send_task(
                        task_name,
                        kwargs=t.get('kwargs', {}),
                        queue=t.get('queue', 'default'),
                    )
                    results.append({'task_id': r.id, 'task_name': task_name})
                except Exception as e:
                    errors.append({'task_name': task_name, 'error': str(e)})

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'dispatched': results, 'errors': errors})

    # ─── DLQ ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def dlq_stats(self, request):
        """Return DLQ statistics."""
        from api.tasks.services.DeadLetterService import DeadLetterService
        return Response(DeadLetterService().get_stats())

    @action(detail=False, methods=['post'])
    def dlq_retry_all(self, request):
        """Retry all pending DLQ entries."""
        from api.tasks.services.DeadLetterService import DeadLetterService
        task_name = request.data.get('task_name')
        result    = DeadLetterService().retry_all_pending(task_name=task_name)
        return Response(result)

    @action(detail=False, methods=['post'])
    def dlq_flush(self, request):
        """Discard all pending DLQ entries (use with caution)."""
        from api.tasks.services.DeadLetterService import DeadLetterService
        task_name = request.data.get('task_name')
        result    = DeadLetterService().discard_all(task_name=task_name)
        logger.warning(
            f"[ADMIN] DLQ flush by {request.user}: "
            f"task_name={task_name} discarded={result.get('discarded')}"
        )
        return Response(result)

    # ─── Workers ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def workers(self, request):
        """Return all worker health records."""
        from api.tasks.services.WorkerHealthService import WorkerHealthService
        return Response(WorkerHealthService().get_all())

    @action(detail=False, methods=['post'])
    def refresh_workers(self, request):
        """Refresh worker health from Celery inspect."""
        from api.tasks.services.WorkerHealthService import WorkerHealthService
        summary = WorkerHealthService().refresh()
        return Response(summary)

    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """
        Broadcast a Celery control command to all workers.
        Body: { command: 'ping'|'shutdown'|'pool_restart', destination: [worker_ids] }
        """
        command     = request.data.get('command', 'ping')
        destination = request.data.get('destination')  # None = all workers

        try:
            from celery import current_app
            reply = current_app.control.broadcast(
                command,
                destination=destination,
                reply=True,
                timeout=3.0,
            )
            logger.warning(f"[ADMIN] Broadcast '{command}' by {request.user}")
            return Response({'command': command, 'replies': reply})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─── Queue Management ─────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def queue_depths(self, request):
        """Return current depth for all queues."""
        from api.tasks.services.QueueDepthService import QueueDepthService
        return Response(QueueDepthService().get_all_depths())

    @action(detail=False, methods=['post'])
    def snapshot_queues(self, request):
        """Snapshot all queue depths to DB."""
        from api.tasks.services.QueueDepthService import QueueDepthService
        snapshots = QueueDepthService().snapshot_all()
        return Response({'count': len(snapshots), 'snapshots': snapshots})

    # ─── Analytics ────────────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def refresh_analytics(self, request):
        """Trigger analytics refresh tasks."""
        from api.tasks.analytics_tasks import refresh_analytics_cache
        result = refresh_analytics_cache.apply_async()
        return Response({'task_id': result.id, 'status': 'queued'})

    @action(detail=False, methods=['post'])
    def recalculate_costs(self, request):
        """Trigger cost estimate recalculation for all tasks."""
        from api.tasks.services.TaskCostService import TaskCostService
        result = TaskCostService().refresh_all()
        return Response(result)

    # ─── Alerts ───────────────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def evaluate_alerts(self, request):
        """Evaluate all alert rules and fire notifications."""
        from api.tasks.services.TaskAlertService import TaskAlertService
        fired = TaskAlertService().evaluate_all()
        return Response({'fired': fired, 'count': len(fired)})

    # ─── Exports ──────────────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def export_history(self, request):
        """Trigger async export of task history."""
        from api.tasks.export_tasks import export_task_history
        result = export_task_history.apply_async(kwargs={
            'start_date': request.data.get('start_date'),
            'end_date': request.data.get('end_date'),
            'status': request.data.get('status'),
            'requester_user_id': request.user.pk,
        })
        return Response({'task_id': result.id, 'status': 'queued'})

    @action(detail=False, methods=['post'])
    def export_dlq(self, request):
        """Export DLQ entries to CSV."""
        from api.tasks.services.TaskExportService import TaskExportService
        fmt    = request.data.get('format', 'csv')
        result = TaskExportService().export_dlq(fmt=fmt)
        return Response(result)

    # ─── System Health ────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Return cached system health or trigger a fresh check."""
        from django.core.cache import cache
        health = cache.get('system_health')
        if not health or request.query_params.get('refresh') == 'true':
            from api.tasks.health_check_tasks import system_health_ping
            result = system_health_ping.apply()
            health = result.get('health', {})
        return Response(health)

    # ─── Scheduled Tasks ──────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def scheduled_tasks(self, request):
        """List all scheduled tasks with stats."""
        from api.tasks.models.core import ScheduledTask
        tasks = list(
            ScheduledTask.objects.values(
                'id', 'name', 'task_name', 'schedule_type',
                'cron_expression', 'is_active', 'is_paused',
                'last_run_at', 'last_run_status', 'total_runs',
                'total_failures', 'avg_duration_sec',
            )
        )
        return Response(tasks)

    @action(detail=False, methods=['post'])
    def run_scheduled(self, request):
        """Immediately run a ScheduledTask by id."""
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': 'task_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from api.tasks.models.core import ScheduledTask
            from celery import current_app

            st     = ScheduledTask.objects.get(pk=task_id)
            result = current_app.send_task(
                st.task_name,
                args=st.task_args or [],
                kwargs=st.task_kwargs or {},
                queue=st.queue or 'default',
            )
            logger.info(f"[ADMIN] Manual trigger of '{st.name}' by {request.user}")
            return Response({'task_id': result.id, 'scheduled_task': st.name})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─── Monitors ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def monitors(self, request):
        """Return all TaskMonitor snapshots."""
        from api.tasks.services.TaskMonitorService import TaskMonitorService
        return Response(TaskMonitorService().get_all_monitors())

    @action(detail=False, methods=['post'])
    def refresh_monitors(self, request):
        """Recompute all TaskMonitor health snapshots."""
        from api.tasks.services.TaskMonitorService import TaskMonitorService
        updated = TaskMonitorService().refresh_all_monitors()
        return Response({'updated': updated})

    # ─── Workflow Shortcuts ───────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def workflows(self, request):
        """List all active workflows."""
        from api.tasks.services.WorkflowService import WorkflowService
        return Response(WorkflowService().list_workflows())

    @action(detail=False, methods=['post'])
    def trigger_workflow(self, request):
        """Trigger a workflow by id."""
        from api.tasks.services.WorkflowService import WorkflowService
        workflow_id = request.data.get('workflow_id')
        input_data  = request.data.get('input_data', {})
        if not workflow_id:
            return Response({'error': 'workflow_id required'}, status=status.HTTP_400_BAD_REQUEST)
        result = WorkflowService().trigger_workflow(
            workflow_id=int(workflow_id),
            input_data=input_data,
            triggered_by=request.user,
        )
        code = status.HTTP_202_ACCEPTED if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)
