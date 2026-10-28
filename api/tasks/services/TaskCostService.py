"""
tasks/services/TaskCostService.py
Estimate compute cost per Celery task execution.
"""
import logging
from decimal import Decimal
from typing import Dict, Any, List
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default pricing (AWS Lambda-equivalent approximate rates)
DEFAULT_CPU_COST_PER_SECOND     = Decimal('0.00001667')   # $/vCPU-second
DEFAULT_MEMORY_COST_PER_MB_SEC  = Decimal('0.000000174')  # $/MB-second


class TaskCostService:
    """Estimate and track compute costs for Celery tasks."""

    def estimate_cost(
        self,
        avg_cpu_seconds: float,
        avg_memory_mb: float,
        avg_wall_seconds: float,
        cpu_cost: Decimal = DEFAULT_CPU_COST_PER_SECOND,
        memory_cost: Decimal = DEFAULT_MEMORY_COST_PER_MB_SEC,
    ) -> Decimal:
        """
        Estimate cost per single task execution.
        cost = (cpu_seconds * cpu_rate) + (memory_mb * wall_seconds * memory_rate)
        """
        cpu_cost_total    = Decimal(str(avg_cpu_seconds)) * cpu_cost
        memory_cost_total = (
            Decimal(str(avg_memory_mb)) *
            Decimal(str(avg_wall_seconds)) *
            memory_cost
        )
        return round(cpu_cost_total + memory_cost_total, 8)

    def update_cost_estimate(
        self,
        task_name: str,
        estimation_period: str = 'last_7_days',
    ) -> Dict[str, Any]:
        """
        Recompute and persist the TaskCostEstimate for a task_name.
        """
        try:
            from api.tasks.models.analytics  import TaskCostEstimate
            from api.tasks.models.monitoring import TaskPerformanceLog
            from django.db.models import Avg, Count

            days_map = {
                'last_7_days': 7,
                'last_30_days': 30,
                'last_1_day': 1,
            }
            days   = days_map.get(estimation_period, 7)
            cutoff = timezone.now() - timedelta(days=days)

            qs = TaskPerformanceLog.objects.filter(
                task_name=task_name,
                created_at__gte=cutoff,
                result='success',
            )

            agg = qs.aggregate(
                avg_cpu=Avg('cpu_seconds'),
                avg_mem=Avg('memory_mb'),
                avg_wall=Avg('duration_seconds'),
                sample_size=Count('id'),
            )

            avg_cpu  = float(agg['avg_cpu'] or 0)
            avg_mem  = float(agg['avg_mem'] or 0)
            avg_wall = float(agg['avg_wall'] or 0)
            samples  = agg['sample_size'] or 0

            cost_per_run = self.estimate_cost(avg_cpu, avg_mem, avg_wall)

            # Estimate monthly cost
            runs_per_day = samples / max(days, 1)
            monthly_est  = cost_per_run * Decimal(str(runs_per_day * 30))

            obj, created = TaskCostEstimate.objects.update_or_create(
                task_name=task_name,
                defaults={
                    'avg_cpu_seconds': avg_cpu,
                    'avg_memory_mb': avg_mem,
                    'avg_wall_seconds': avg_wall,
                    'cost_per_run': cost_per_run,
                    'cpu_cost_per_second': DEFAULT_CPU_COST_PER_SECOND,
                    'memory_cost_per_mb_sec': DEFAULT_MEMORY_COST_PER_MB_SEC,
                    'sample_size': samples,
                    'estimation_period': estimation_period,
                    'runs_per_day_avg': round(runs_per_day, 4),
                    'monthly_cost_est': round(monthly_est, 4),
                    'calculated_at': timezone.now(),
                },
            )

            return {
                'success': True,
                'task_name': task_name,
                'cost_per_run': str(cost_per_run),
                'monthly_cost_est': str(monthly_est),
                'sample_size': samples,
                'created': created,
            }

        except Exception as e:
            logger.error(f"[ERROR] TaskCostService.update_cost_estimate for {task_name}: {e}")
            return {'success': False, 'error': str(e)}

    def refresh_all(self) -> Dict[str, Any]:
        """Refresh cost estimates for all tasks with recent performance logs."""
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog

            task_names = (
                TaskPerformanceLog.objects
                .filter(created_at__gte=timezone.now() - timedelta(days=7))
                .values_list('task_name', flat=True)
                .distinct()
            )

            updated = 0
            errors  = 0
            for name in task_names:
                result = self.update_cost_estimate(name)
                if result.get('success'):
                    updated += 1
                else:
                    errors += 1

            return {'updated': updated, 'errors': errors}

        except Exception as e:
            logger.error(f"[ERROR] TaskCostService.refresh_all: {e}")
            return {'error': str(e)}

    def get_top_costly_tasks(self, limit: int = 10) -> List[Dict]:
        """Return the most expensive tasks by cost_per_run."""
        try:
            from api.tasks.models.analytics import TaskCostEstimate

            return list(
                TaskCostEstimate.objects.order_by('-cost_per_run')[:limit].values(
                    'task_name', 'cost_per_run', 'monthly_cost_est',
                    'avg_wall_seconds', 'avg_cpu_seconds', 'avg_memory_mb',
                    'sample_size', 'calculated_at',
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] TaskCostService.get_top_costly_tasks: {e}")
            return []
