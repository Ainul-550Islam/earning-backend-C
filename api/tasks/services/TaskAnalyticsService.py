"""
tasks/services/TaskAnalyticsService.py
Performance metrics aggregation for tasks.
"""
import logging
from typing import Dict, Any, List
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TaskAnalyticsService:
    """Aggregate and retrieve task performance analytics."""

    def get_task_stats(self, task_name: str, days: int = 7) -> Dict[str, Any]:
        """Return aggregated stats for a specific task over the last N days."""
        try:
            from api.tasks.models.analytics import TaskInsight
            from django.db.models import Sum, Avg

            cutoff = timezone.now().date() - timedelta(days=days)
            qs     = TaskInsight.objects.filter(
                task_name=task_name,
                date__gte=cutoff,
            )

            agg = qs.aggregate(
                total_runs=Sum('run_count'),
                total_success=Sum('success_count'),
                total_failures=Sum('failure_count'),
                avg_duration=Avg('avg_duration'),
            )

            total = agg['total_runs'] or 0
            succ  = agg['total_success'] or 0

            return {
                'task_name': task_name,
                'days': days,
                'total_runs': total,
                'success_count': succ,
                'failure_count': agg['total_failures'] or 0,
                'success_rate': round(succ / total * 100, 2) if total > 0 else 0.0,
                'avg_duration': round(agg['avg_duration'] or 0, 3),
            }
        except Exception as e:
            logger.error(f"[ERROR] TaskAnalyticsService.get_task_stats: {e}")
            return {}

    def get_platform_stats(self, days: int = 30) -> Dict[str, Any]:
        """Return platform-wide task stats."""
        cache_key = f'platform_stats_{days}d'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.tasks.models.analytics import TaskInsight
            from django.db.models import Sum

            cutoff = timezone.now().date() - timedelta(days=days)
            agg    = TaskInsight.objects.filter(date__gte=cutoff).aggregate(
                total_runs=Sum('run_count'),
                total_success=Sum('success_count'),
                total_failures=Sum('failure_count'),
            )

            result = {
                'days': days,
                'total_runs': agg['total_runs'] or 0,
                'success_count': agg['total_success'] or 0,
                'failure_count': agg['total_failures'] or 0,
            }
            cache.set(cache_key, result, timeout=1800)
            return result

        except Exception as e:
            logger.error(f"[ERROR] TaskAnalyticsService.get_platform_stats: {e}")
            return {}

    def get_daily_trend(self, task_name: str = None, days: int = 14) -> List[Dict]:
        """Return daily run/success/failure counts for charting."""
        try:
            from api.tasks.models.analytics import TaskInsight

            cutoff = timezone.now().date() - timedelta(days=days)
            qs     = TaskInsight.objects.filter(date__gte=cutoff).order_by('date')
            if task_name:
                qs = qs.filter(task_name=task_name)

            return list(qs.values(
                'date', 'task_name', 'run_count',
                'success_count', 'failure_count', 'avg_duration',
            ))
        except Exception as e:
            logger.error(f"[ERROR] TaskAnalyticsService.get_daily_trend: {e}")
            return []

    def get_top_tasks(self, by: str = 'completions', limit: int = 10, days: int = 7) -> List[Dict]:
        """Return top tasks ranked by completions or failure_rate."""
        try:
            from api.tasks.models.analytics import TaskInsight
            from django.db.models import Sum

            cutoff = timezone.now().date() - timedelta(days=days)
            qs     = (
                TaskInsight.objects.filter(date__gte=cutoff)
                .values('task_name')
                .annotate(
                    total_runs=Sum('run_count'),
                    total_failures=Sum('failure_count'),
                )
            )

            if by == 'completions':
                qs = qs.order_by('-total_runs')
            else:
                qs = qs.order_by('-total_failures')

            return list(qs[:limit])
        except Exception as e:
            logger.error(f"[ERROR] TaskAnalyticsService.get_top_tasks: {e}")
            return []
