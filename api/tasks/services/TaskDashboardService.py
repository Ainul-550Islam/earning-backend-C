"""
tasks/services/TaskDashboardService.py
Aggregate all task system data for the admin dashboard.
"""
import logging
from typing import Dict, Any
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_KEY = 'task_admin_dashboard'
DASHBOARD_CACHE_TTL = 60  # seconds


class TaskDashboardService:
    """
    Provides a single get_dashboard_data() call that assembles
    all widgets needed by the admin task monitoring dashboard.
    """

    def get_dashboard_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Return complete dashboard data dict.
        Caches for 60 seconds unless force_refresh=True.
        """
        if not force_refresh:
            cached = cache.get(DASHBOARD_CACHE_KEY)
            if cached:
                return cached

        data = {
            'generated_at': timezone.now().isoformat(),
            'system_health': self._get_system_health(),
            'worker_summary': self._get_worker_summary(),
            'queue_summary': self._get_queue_summary(),
            'dlq_summary': self._get_dlq_summary(),
            'monitor_overview': self._get_monitor_overview(),
            'recent_failures': self._get_recent_failures(),
            'platform_kpis': cache.get('platform_kpis') or {},
            'active_workflows': self._get_active_workflows(),
            'top_costly_tasks': self._get_top_costly_tasks(),
            'alert_summary': self._get_alert_summary(),
        }

        cache.set(DASHBOARD_CACHE_KEY, data, timeout=DASHBOARD_CACHE_TTL)
        return data

    # ─── Sections ─────────────────────────────────────────────────────

    def _get_system_health(self) -> Dict:
        return cache.get('system_health') or {'overall': 'unknown'}

    def _get_worker_summary(self) -> Dict:
        try:
            from api.tasks.models.monitoring import WorkerHealth
            from django.db.models import Count

            counts = WorkerHealth.objects.values('status').annotate(cnt=Count('id'))
            summary = {row['status']: row['cnt'] for row in counts}
            summary['total'] = sum(summary.values())
            return summary
        except Exception:
            return {}

    def _get_queue_summary(self) -> list:
        try:
            from api.tasks.services.QueueDepthService import QueueDepthService

            svc = QueueDepthService()
            return svc.get_all_depths()
        except Exception:
            return []

    def _get_dlq_summary(self) -> Dict:
        try:
            from api.tasks.services.DeadLetterService import DeadLetterService

            return DeadLetterService().get_stats()
        except Exception:
            return {}

    def _get_monitor_overview(self) -> Dict:
        try:
            from api.tasks.models.monitoring import TaskMonitor
            from django.db.models import Count

            counts = TaskMonitor.objects.values('status').annotate(cnt=Count('id'))
            summary = {row['status']: row['cnt'] for row in counts}
            summary['total'] = sum(summary.values())
            return summary
        except Exception:
            return {}

    def _get_recent_failures(self, limit: int = 10) -> list:
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from datetime import timedelta

            cutoff = timezone.now() - timedelta(hours=1)
            return list(
                TaskPerformanceLog.objects.filter(
                    result='failure',
                    created_at__gte=cutoff,
                ).order_by('-created_at')[:limit].values(
                    'task_name', 'error', 'created_at', 'worker', 'queue'
                )
            )
        except Exception:
            return []

    def _get_active_workflows(self) -> list:
        try:
            from api.tasks.models.workflow import WorkflowInstance

            return list(
                WorkflowInstance.objects.filter(status='running')
                .select_related('workflow')
                .order_by('-created_at')[:10]
                .values('id', 'workflow__name', 'current_step', 'started_at')
            )
        except Exception:
            return []

    def _get_top_costly_tasks(self, limit: int = 5) -> list:
        try:
            from api.tasks.services.TaskCostService import TaskCostService

            return TaskCostService().get_top_costly_tasks(limit=limit)
        except Exception:
            return []

    def _get_alert_summary(self) -> Dict:
        try:
            from api.tasks.models.monitoring import TaskAlert
            from django.db.models import Count

            total  = TaskAlert.objects.filter(is_active=True).count()
            recent = TaskAlert.objects.filter(
                is_active=True,
                last_triggered_at__isnull=False,
            ).order_by('-last_triggered_at')[:5].values(
                'task_name', 'alert_type', 'severity', 'last_triggered_at'
            )

            return {
                'active_rules': total,
                'recently_fired': list(recent),
            }
        except Exception:
            return {}
