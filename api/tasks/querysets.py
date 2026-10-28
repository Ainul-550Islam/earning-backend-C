"""
api/tasks/querysets.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extended QuerySet classes with rich filtering, annotation,
and aggregation methods used across DRF views and services.
Separate from managers.py to keep them small and focused.
"""

from django.db import models
from django.db.models import (
    Sum, Count, Avg, Q, F, Max, Min, ExpressionWrapper,
    DurationField, FloatField, DecimalField, Case, When, Value
)
from django.db.models.functions import TruncDate, TruncHour, TruncWeek
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta


# ══════════════════════════════════════════════════════════════════════════════
# TASK INSIGHT QuerySet (analytics rollups)
# ══════════════════════════════════════════════════════════════════════════════

class TaskInsightQuerySet(models.QuerySet):

    def for_date(self, date):
        return self.filter(date=date)

    def for_task(self, task_name: str):
        return self.filter(task_name=task_name)

    def in_date_range(self, start, end):
        return self.filter(date__gte=start, date__lte=end)

    def with_success_rate(self):
        return self.annotate(
            success_rate_pct=ExpressionWrapper(
                Case(
                    When(run_count=0, then=Value(0.0)),
                    default=F('success_count') * 100.0 / F('run_count'),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            )
        )

    def top_failing(self, limit: int = 10):
        return (
            self.annotate(
                fail_rate=ExpressionWrapper(
                    Case(
                        When(run_count=0, then=Value(0.0)),
                        default=F('failure_count') * 100.0 / F('run_count'),
                        output_field=FloatField(),
                    ),
                    output_field=FloatField(),
                )
            )
            .filter(fail_rate__gt=0)
            .order_by('-fail_rate')[:limit]
        )

    def platform_summary(self, days: int = 7):
        cutoff = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=cutoff).aggregate(
            total_runs=Sum('run_count'),
            total_successes=Sum('success_count'),
            total_failures=Sum('failure_count'),
            avg_duration=Avg('avg_duration'),
        )

    def daily_breakdown(self):
        return (
            self.values('date')
            .annotate(
                runs=Sum('run_count'),
                successes=Sum('success_count'),
                failures=Sum('failure_count'),
                avg_dur=Avg('avg_duration'),
            )
            .order_by('date')
        )

    def task_breakdown(self):
        return (
            self.values('task_name')
            .annotate(
                runs=Sum('run_count'),
                successes=Sum('success_count'),
                failures=Sum('failure_count'),
                avg_dur=Avg('avg_duration'),
                p95_dur=Max('p95_duration'),
            )
            .order_by('-runs')
        )


# ══════════════════════════════════════════════════════════════════════════════
# TASK RESULT QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class TaskResultQuerySet(models.QuerySet):

    def success(self):
        return self.filter(status='success')

    def failure(self):
        return self.filter(status='failure')

    def pending(self):
        return self.filter(status='pending')

    def started(self):
        return self.filter(status='started')

    def for_worker(self, worker: str):
        return self.filter(worker=worker)

    def for_queue(self, queue: str):
        return self.filter(queue=queue)

    def slow(self, threshold: float = 30.0):
        return self.filter(duration_seconds__gt=threshold)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(date_created__gte=cutoff)

    def terminal(self):
        return self.filter(status__in=['success', 'failure', 'revoked'])

    def by_task_name(self, task_name: str):
        return self.filter(task_name__icontains=task_name)

    def stats_by_task(self):
        return (
            self.values('task_name')
            .annotate(
                total=Count('id'),
                successes=Count('id', filter=Q(status='success')),
                failures=Count('id', filter=Q(status='failure')),
                avg_duration=Avg('duration_seconds'),
            )
        )


# ══════════════════════════════════════════════════════════════════════════════
# TASK ALERT QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class TaskAlertQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def by_severity(self, severity: str):
        return self.filter(severity=severity)

    def critical(self):
        return self.active().filter(severity__in=['critical', 'emergency'])

    def by_type(self, alert_type: str):
        return self.filter(alert_type=alert_type)

    def for_task(self, task_name: str):
        return self.filter(task_name__icontains=task_name)

    def not_in_cooldown(self):
        now = timezone.now()
        from django.db.models.functions import Now
        return self.active().filter(
            Q(last_triggered_at__isnull=True) |
            Q(cooldown_minutes=0) |
            Q(last_triggered_at__lt=now - timedelta(minutes=1) * F('cooldown_minutes'))
        )

    def recently_fired(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(last_triggered_at__gte=cutoff)

    def ordered_by_priority(self):
        severity_order = Case(
            When(severity='emergency', then=0),
            When(severity='critical',  then=1),
            When(severity='warning',   then=2),
            When(severity='info',      then=3),
            default=4,
            output_field=models.IntegerField(),
        )
        return self.annotate(priority=severity_order).order_by('priority', 'task_name')


# ══════════════════════════════════════════════════════════════════════════════
# QUEUE DEPTH QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class QueueDepthQuerySet(models.QuerySet):

    def for_queue(self, queue_name: str):
        return self.filter(queue_name=queue_name)

    def recent(self, hours: int = 1):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(checked_at__gte=cutoff)

    def latest_per_queue(self):
        from django.db.models import Subquery, OuterRef
        latest_id = (
            self.filter(queue_name=OuterRef('queue_name'))
            .order_by('-checked_at')
            .values('id')[:1]
        )
        return self.filter(id__in=Subquery(latest_id))

    def average_depth(self, queue_name: str, hours: int = 1) -> float:
        result = self.for_queue(queue_name).recent(hours).aggregate(avg=Avg('depth'))
        return result['avg'] or 0.0

    def critical_queues(self, threshold: int = 500):
        return self.filter(depth__gte=threshold).distinct('queue_name')

    def summary(self):
        return self.latest_per_queue().aggregate(
            total_messages=Sum('depth'),
            max_depth=Max('depth'),
            avg_depth=Avg('depth'),
            queue_count=Count('queue_name', distinct=True),
        )


# ══════════════════════════════════════════════════════════════════════════════
# WORKER HEALTH QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class WorkerHealthQuerySet(models.QuerySet):

    def online(self):
        return self.filter(status__in=['online', 'idle', 'busy'])

    def offline(self):
        return self.filter(status='offline')

    def stale(self, minutes: int = 5):
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return self.filter(last_heartbeat__lt=cutoff)

    def healthy(self, minutes: int = 5):
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return self.filter(last_heartbeat__gte=cutoff, status__in=['online', 'idle', 'busy'])

    def overloaded(self, load_threshold: float = 90.0):
        """Workers with >90% load."""
        return self.online().filter(
            concurrency__gt=0,
            active_tasks__gte=F('concurrency') * load_threshold / 100,
        )

    def summary(self) -> dict:
        return self.aggregate(
            total=Count('id'),
            online=Count('id', filter=Q(status__in=['online', 'idle', 'busy'])),
            offline=Count('id', filter=Q(status='offline')),
            total_capacity=Sum('concurrency'),
            total_active=Sum('active_tasks'),
        )


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def by_trigger_type(self, trigger_type: str):
        return self.filter(trigger_type=trigger_type)

    def with_step_count(self):
        return self.annotate(step_count=Count('workflow_steps'))

    def ordered(self):
        return self.order_by('name')

    def recently_created(self, days: int = 7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def by_creator(self, user_id: int):
        return self.filter(created_by_id=user_id)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULED TASK QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class ScheduledTaskQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True, is_paused=False)

    def paused(self):
        return self.filter(is_paused=True)

    def due(self):
        """Tasks due for execution (next_run_at <= now)."""
        return self.active().filter(
            Q(next_run_at__isnull=True) | Q(next_run_at__lte=timezone.now())
        )

    def by_queue(self, queue: str):
        return self.filter(queue=queue)

    def high_failure_rate(self, threshold: float = 20.0):
        return self.active().annotate(
            fail_rate=ExpressionWrapper(
                Case(
                    When(total_runs=0, then=Value(0.0)),
                    default=F('total_failures') * 100.0 / F('total_runs'),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            )
        ).filter(fail_rate__gt=threshold)

    def not_run_recently(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.active().filter(
            Q(last_run_at__isnull=True) | Q(last_run_at__lt=cutoff)
        )


# ══════════════════════════════════════════════════════════════════════════════
# TASK COST ESTIMATE QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class TaskCostQuerySet(models.QuerySet):

    def by_task(self, task_name: str):
        return self.filter(task_name=task_name)

    def expensive(self, threshold_usd: Decimal = Decimal('0.01')):
        return self.filter(cost_per_run__gt=threshold_usd)

    def high_monthly_cost(self, threshold_usd: Decimal = Decimal('10.00')):
        return self.filter(monthly_cost_est__gt=threshold_usd)

    def ordered_by_cost(self):
        return self.order_by('-cost_per_run')

    def total_monthly_estimate(self) -> Decimal:
        result = self.aggregate(total=Sum('monthly_cost_est'))
        return result['total'] or Decimal('0')


# ══════════════════════════════════════════════════════════════════════════════
# FAILURE RATE QuerySet
# ══════════════════════════════════════════════════════════════════════════════

class TaskFailureRateQuerySet(models.QuerySet):

    def for_period(self, period: str):
        return self.filter(period=period)

    def for_task(self, task_name: str):
        return self.filter(task_name=task_name)

    def high_failure(self, threshold: float = 10.0):
        return self.filter(failure_pct__gt=threshold)

    def recent_periods(self, count: int = 7):
        return self.order_by('-period_start')[:count]

    def trend(self, task_name: str, period: str = 'daily', count: int = 30):
        return (
            self.filter(task_name=task_name, period=period)
            .order_by('-period_start')[:count]
            .values('period_start', 'failure_pct', 'total_runs', 'failure_count')
        )


__all__ = [
    'TaskInsightQuerySet', 'TaskResultQuerySet', 'TaskAlertQuerySet',
    'QueueDepthQuerySet', 'WorkerHealthQuerySet', 'WorkflowQuerySet',
    'ScheduledTaskQuerySet', 'TaskCostQuerySet', 'TaskFailureRateQuerySet',
]
