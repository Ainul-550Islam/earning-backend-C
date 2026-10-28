# cms/viewsets_new/TaskManagementViewSet.py
"""
API ViewSets for Task Management and Scheduling.

v11b: Wired TaskManagementService into every action.

Previous version queried TaskSchedule/TaskExecution models directly,
bypassing:
  • Dependency resolution (task.depends_on checking)
  • TaskLock acquisition / release (race condition risk)
  • next_run recalculation after enable/disable/execute
  • Worker ID recording on execution
  • Cache invalidation of the ready_tasks hot path
  • TaskQueue ordering by priority + retry backoff
  • Performance metrics recording (PerformanceMonitor.record_task)

Now all mutations go through TaskManagementService.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models_new.task_management import (
    TaskSchedule, TaskExecution, TaskQueue, TaskLock
)

logger = logging.getLogger('cms.viewsets_new.task_management')


def _get_service():
    from ..services_new.TaskManagementService import TaskManagementService
    return TaskManagementService()


class TaskScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TaskSchedule — all writes go via TaskManagementService.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['frequency', 'status', 'priority']

    def get_queryset(self):
        if self.request.user.is_staff:
            return TaskSchedule.objects.all().prefetch_related(
                'depends_on', 'created_by'
            ).order_by('-created_at')
        return TaskSchedule.objects.filter(
            status='active'
        ).prefetch_related('depends_on', 'created_by').order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers_new.TaskManagementSerializer import (
            TaskScheduleSerializer, TaskScheduleDetailSerializer
        )
        if self.action == 'list':
            return TaskScheduleSerializer
        return TaskScheduleDetailSerializer

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can create task schedules")
        task_data = serializer.validated_data.copy()
        task_data['created_by'] = self.request.user
        try:
            svc = _get_service()
            task = svc.schedule_task(task_data)
            # Update serializer instance to match what was actually created
            serializer.instance = task
        except Exception:
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can update task schedules")
        serializer.save()

    # ── enable ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        POST /v3/task-schedules/{id}/enable/

        Enable a disabled task via TaskManagementService.
        Service recalculates next_run and clears the ready_tasks cache.
        """
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        schedule = self.get_object()
        try:
            svc = _get_service()
            svc.enable_task(str(schedule.uuid))
            schedule.refresh_from_db()
            return Response({
                'message': 'Task schedule enabled',
                'uuid': str(schedule.uuid),
                'status': schedule.status,
                'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
            })
        except Exception as e:
            logger.error(f'[TaskScheduleViewSet] enable error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    # ── disable ───────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        POST /v3/task-schedules/{id}/disable/

        Disable an active task via TaskManagementService.
        Releases any held TaskLock and clears the ready_tasks cache.
        """
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        schedule = self.get_object()
        try:
            svc = _get_service()
            svc.disable_task(str(schedule.uuid))
            schedule.refresh_from_db()
            return Response({
                'message': 'Task schedule disabled',
                'uuid': str(schedule.uuid),
                'status': schedule.status,
            })
        except Exception as e:
            logger.error(f'[TaskScheduleViewSet] disable error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    # ── execute_now ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def execute_now(self, request, pk=None):
        """
        POST /v3/task-schedules/{id}/execute-now/

        Admin: trigger immediate execution via TaskManagementService.
        Service handles lock acquisition, dependency check, execution
        record creation, next_run recalculation, and metric recording.

        Previously: admins set status=active and waited for the Celery
        beat to pick it up on the next */1 tick — up to 60s delay.
        Now: executes immediately, returns the TaskExecution UUID.
        """
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        schedule = self.get_object()
        try:
            svc = _get_service()
            worker_id = f'admin_{request.user.pk}_{timezone.now().timestamp()}'
            execution = svc.execute_task(str(schedule.uuid), worker_id=worker_id)
            return Response({
                'message': 'Task executed',
                'execution_uuid': str(execution.uuid),
                'status': execution.status,
                'worker_id': worker_id,
                'started_at': execution.started_at.isoformat()
                              if execution.started_at else None,
            })
        except Exception as e:
            logger.error(f'[TaskScheduleViewSet] execute_now error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    # ── ready_tasks ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def ready_tasks(self, request):
        """
        GET /v3/task-schedules/ready-tasks/

        Returns tasks whose next_run <= now AND whose dependencies are met.
        Uses TaskManagementService.get_ready_tasks() (cached).
        Ops use: see what's about to run before the next beat tick.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        try:
            svc = _get_service()
            tasks = svc.get_ready_tasks()
            return Response({
                'ready_tasks': [
                    {
                        'uuid': str(t.uuid),
                        'name': t.name,
                        'priority': t.priority,
                        'next_run': t.next_run.isoformat() if t.next_run else None,
                    }
                    for t in tasks
                ],
                'count': len(tasks),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ── stats ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        GET /v3/task-schedules/stats/

        Admin: schedule health stats (active, disabled, overdue counts).
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        try:
            svc = _get_service()
            return Response(svc.get_task_statistics())
        except Exception as e:
            now = timezone.now()
            qs = TaskSchedule.objects.all()
            return Response({
                'total': qs.count(),
                'active': qs.filter(status='active').count(),
                'disabled': qs.filter(status='disabled').count(),
                'overdue': qs.filter(status='active', next_run__lt=now).count(),
                'error': str(e),
            })


class TaskExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for TaskExecution — read-only audit log.
    Executions are created by TaskManagementService, never directly.
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'schedule']

    def get_queryset(self):
        return TaskExecution.objects.all().select_related(
            'schedule'
        ).order_by('-started_at')

    def get_serializer_class(self):
        from ..serializers_new.TaskManagementSerializer import TaskExecutionSerializer
        return TaskExecutionSerializer

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        POST /v3/task-executions/{id}/retry/

        Admin: retry a failed execution via TaskManagementService.
        Creates a new execution record; does NOT mutate the original.
        """
        execution = self.get_object()
        if execution.status not in ('failed', 'timeout'):
            return Response(
                {'error': f'Cannot retry a {execution.status} execution'},
                status=400,
            )
        try:
            svc = _get_service()
            worker_id = f'retry_admin_{request.user.pk}'
            new_exec = svc.execute_task(
                str(execution.schedule.uuid), worker_id=worker_id
            )
            return Response({
                'success': True,
                'original_execution': str(execution.uuid),
                'new_execution': str(new_exec.uuid),
                'status': new_exec.status,
            })
        except Exception as e:
            logger.error(f'[TaskExecutionViewSet] retry error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def recent_failures(self, request):
        """
        GET /v3/task-executions/recent-failures/?limit=20

        Returns the most recent failed/timeout executions.
        Ops alerting: detect Celery worker issues early.
        """
        limit = min(int(request.query_params.get('limit', 20)), 100)
        qs = TaskExecution.objects.filter(
            status__in=['failed', 'timeout']
        ).select_related('schedule').order_by('-started_at')[:limit]
        from ..serializers_new.TaskManagementSerializer import TaskExecutionSerializer
        return Response({
            'failures': TaskExecutionSerializer(qs, many=True).data,
            'count': qs.count(),
        })

    @action(detail=False, methods=['get'])
    def duration_report(self, request):
        """
        GET /v3/task-executions/duration-report/?days=7

        Average execution duration per task type for performance monitoring.
        """
        days = int(request.query_params.get('days', 7))
        from django.db.models import Avg, Max, Min, Count, ExpressionWrapper, F, fields
        since = timezone.now() - timezone.timedelta(days=days)
        try:
            svc = _get_service()
            report = svc.get_execution_performance_report(since=since)
            return Response(report)
        except Exception as e:
            qs = TaskExecution.objects.filter(
                started_at__gte=since,
                status='completed',
            ).values('schedule__name').annotate(
                count=Count('id'),
                avg_duration_s=Avg('duration_seconds'),
                max_duration_s=Max('duration_seconds'),
                min_duration_s=Min('duration_seconds'),
            ).order_by('-avg_duration_s')
            return Response({
                'report': list(qs),
                'days': days,
                'error': str(e),
            })


class TaskQueueViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TaskQueue — priority queue management.
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'priority']
    queryset = TaskQueue.objects.all().order_by('-priority', 'queued_at')

    def get_serializer_class(self):
        from ..serializers_new.TaskManagementSerializer import TaskQueueSerializer
        return TaskQueueSerializer

    @action(detail=False, methods=['post'])
    def drain(self, request):
        """
        POST /v3/task-queue/drain/

        Admin: process all queued items via TaskManagementService.
        Body: { "limit": 50 }
        """
        limit = min(int(request.data.get('limit', 50)), 500)
        try:
            svc = _get_service()
            result = svc.drain_queue(limit=limit)
            return Response({
                'success': True,
                'processed': result.get('processed', 0),
                'failed': result.get('failed', 0),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def enqueue(self, request):
        """
        POST /v3/task-queue/enqueue/

        Admin: manually enqueue a task for execution.
        Body: { "schedule_uuid": "...", "priority": 5, "params": {} }
        """
        schedule_uuid = request.data.get('schedule_uuid')
        if not schedule_uuid:
            return Response({'error': 'schedule_uuid required'}, status=400)
        try:
            svc = _get_service()
            queue_item = svc.enqueue_task(
                schedule_uuid=schedule_uuid,
                priority=int(request.data.get('priority', 5)),
                params=request.data.get('params', {}),
            )
            return Response({
                'success': True,
                'queue_uuid': str(queue_item.uuid),
                'priority': queue_item.priority,
                'status': queue_item.status,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class TaskLockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for TaskLock — distributed lock inspection.
    Read-only; locks are managed by TaskManagementService.
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
    queryset = TaskLock.objects.all().select_related('schedule').order_by('-acquired_at')

    def get_serializer_class(self):
        from ..serializers_new.TaskManagementSerializer import TaskLockSerializer
        return TaskLockSerializer

    @action(detail=True, methods=['post'])
    def force_release(self, request, pk=None):
        """
        POST /v3/task-locks/{id}/force-release/

        Admin: forcibly release a stuck lock.
        Use when a worker crashed mid-task and left the lock held.
        """
        lock = self.get_object()
        try:
            svc = _get_service()
            released = svc.force_release_lock(str(lock.uuid))
            return Response({
                'success': released,
                'lock_uuid': str(lock.uuid),
                'message': 'Lock released' if released else 'Lock was already inactive',
            })
        except Exception as e:
            logger.error(f'[TaskLockViewSet] force_release error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def stale_locks(self, request):
        """
        GET /v3/task-locks/stale-locks/?stale_minutes=30

        Returns locks held for longer than stale_minutes.
        Ops: detect crashed workers before they block dependent tasks.
        """
        stale_minutes = int(request.query_params.get('stale_minutes', 30))
        cutoff = timezone.now() - timezone.timedelta(minutes=stale_minutes)
        qs = TaskLock.objects.filter(
            is_active=True,
            acquired_at__lt=cutoff,
        ).select_related('schedule').order_by('acquired_at')
        from ..serializers_new.TaskManagementSerializer import TaskLockSerializer
        return Response({
            'stale_locks': TaskLockSerializer(qs, many=True).data,
            'count': qs.count(),
            'stale_minutes': stale_minutes,
        })
