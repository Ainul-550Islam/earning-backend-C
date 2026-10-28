"""
api/tasks/managers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom Django model managers for the task system.
Encapsulates common query patterns and business rules
into reusable manager methods.
"""

from django.db import models
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from decimal import Decimal
from datetime import timedelta


# ══════════════════════════════════════════════════════════════════════════════
# MasterTask Manager
# ══════════════════════════════════════════════════════════════════════════════

class MasterTaskQuerySet(models.QuerySet):

    def active(self):
        """Return only active tasks."""
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def by_category(self, category: str):
        return self.filter(category=category)

    def by_system_type(self, system_type: str):
        return self.filter(system_type=system_type)

    def for_country(self, country_code: str):
        """Return tasks eligible for a given country."""
        return self.filter(
            Q(allowed_countries__isnull=True) |
            Q(allowed_countries__contains=[country_code])
        )

    def for_device(self, device: str):
        """Return tasks eligible for a given device type."""
        return self.filter(
            Q(allowed_devices__isnull=True) |
            Q(allowed_devices__contains=[device])
        )

    def featured(self):
        return self.filter(is_featured=True, is_active=True)

    def not_expired(self):
        return self.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    def high_value(self, min_reward: Decimal = Decimal('1.00')):
        """Return tasks with reward above threshold."""
        return self.filter(is_active=True)

    def ordered_by_priority(self):
        return self.order_by(
            F('sort_order').asc(nulls_last=True),
            '-is_featured',
            'task_id',
        )

    def search(self, query: str):
        return self.filter(
            Q(name__icontains=query) |
            Q(task_id__icontains=query) |
            Q(category__icontains=query)
        )


class MasterTaskManager(models.Manager):
    def get_queryset(self):
        return MasterTaskQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def active_for_user(self, user, country: str = None, device: str = None):
        """Return active tasks eligible for a specific user."""
        qs = self.get_queryset().active().not_expired()
        if country:
            qs = qs.for_country(country)
        if device:
            qs = qs.for_device(device)
        return qs.ordered_by_priority()

    def featured(self):
        return self.get_queryset().featured()

    def by_category(self, category: str):
        return self.get_queryset().active().by_category(category)


# ══════════════════════════════════════════════════════════════════════════════
# UserTaskCompletion Manager
# ══════════════════════════════════════════════════════════════════════════════

class UserTaskCompletionQuerySet(models.QuerySet):

    def completed(self):
        return self.filter(status='completed')

    def pending(self):
        return self.filter(status='pending')

    def failed(self):
        return self.filter(status='failed')

    def for_user(self, user_id: int):
        return self.filter(user_id=user_id)

    def for_task(self, task_id: str):
        return self.filter(task__task_id=task_id)

    def today(self):
        today = timezone.now().date()
        return self.filter(completed_at__date=today)

    def this_week(self):
        cutoff = timezone.now() - timedelta(days=7)
        return self.filter(completed_at__gte=cutoff)

    def this_month(self):
        cutoff = timezone.now() - timedelta(days=30)
        return self.filter(completed_at__gte=cutoff)

    def in_range(self, start, end):
        return self.filter(completed_at__gte=start, completed_at__lt=end)

    def total_earned(self) -> Decimal:
        result = self.completed().aggregate(total=Sum('reward_amount'))
        return result['total'] or Decimal('0')

    def completion_count(self) -> int:
        return self.completed().count()

    def with_fraud_flags(self):
        return self.filter(is_suspicious=True)

    def by_source(self, source_ip: str):
        return self.filter(ip_address=source_ip)

    def with_task_info(self):
        return self.select_related('task', 'user')

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(completed_at__gte=cutoff)

    def aggregate_by_user(self):
        return (
            self.completed()
            .values('user_id')
            .annotate(
                total_earned=Sum('reward_amount'),
                completion_count=Count('id'),
                avg_reward=Avg('reward_amount'),
                max_reward=Max('reward_amount'),
                last_completed_at=Max('completed_at'),
            )
        )

    def aggregate_by_task(self):
        return (
            self.completed()
            .values('task_id', 'task__task_id', 'task__name')
            .annotate(
                total_completions=Count('id'),
                total_rewards=Sum('reward_amount'),
                avg_reward=Avg('reward_amount'),
                unique_users=Count('user_id', distinct=True),
            )
        )


class UserTaskCompletionManager(models.Manager):
    def get_queryset(self):
        return UserTaskCompletionQuerySet(self.model, using=self._db)

    def completed(self):
        return self.get_queryset().completed()

    def for_user(self, user_id: int):
        return self.get_queryset().for_user(user_id)

    def user_total_earned(self, user_id: int) -> Decimal:
        return self.for_user(user_id).total_earned()

    def user_completion_count(self, user_id: int, days: int = None) -> int:
        qs = self.for_user(user_id).completed()
        if days:
            qs = qs.filter(completed_at__gte=timezone.now() - timedelta(days=days))
        return qs.count()

    def daily_stats(self, date=None):
        """Platform-wide daily stats."""
        target = date or timezone.now().date()
        return self.get_queryset().filter(
            completed_at__date=target
        ).aggregate(
            completions=Count('id'),
            total_rewards=Sum('reward_amount'),
            unique_users=Count('user_id', distinct=True),
            admin_revenue=Sum('admin_revenue_received'),
        )

    def recent_fraud_risk(self, hours: int = 1):
        """Recently completed tasks flagged as suspicious."""
        return self.get_queryset().recent(hours).with_fraud_flags()


# ══════════════════════════════════════════════════════════════════════════════
# AdminLedger Manager
# ══════════════════════════════════════════════════════════════════════════════

class AdminLedgerQuerySet(models.QuerySet):

    def in_range(self, start, end):
        return self.filter(created_at__gte=start, created_at__lt=end)

    def today(self):
        today = timezone.now().date()
        return self.filter(created_at__date=today)

    def by_source(self, source: str):
        return self.filter(source=source)

    def total_profit(self) -> Decimal:
        result = self.aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0')

    def daily_profit(self):
        return (
            self.today()
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )

    def by_task_category(self, category: str):
        return self.filter(completion__task__category=category)

    def profit_summary(self, days: int = 30):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff).aggregate(
            total_profit=Sum('amount'),
            avg_daily=Avg('amount'),
            transaction_count=Count('id'),
        )


class AdminLedgerManager(models.Manager):
    def get_queryset(self):
        return AdminLedgerQuerySet(self.model, using=self._db)

    def today_profit(self) -> Decimal:
        return self.get_queryset().daily_profit()

    def total_profit(self) -> Decimal:
        return self.get_queryset().total_profit()

    def profit_summary(self, days: int = 30) -> dict:
        return self.get_queryset().profit_summary(days)


# ══════════════════════════════════════════════════════════════════════════════
# Monitoring Managers
# ══════════════════════════════════════════════════════════════════════════════

class TaskPerformanceLogQuerySet(models.QuerySet):

    def for_task(self, task_name: str):
        return self.filter(task_name=task_name)

    def successful(self):
        return self.filter(result='success')

    def failed(self):
        return self.filter(result='failure')

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def slow(self, threshold_seconds: float = 30.0):
        return self.filter(duration_seconds__gt=threshold_seconds)

    def success_rate(self) -> float:
        total = self.count()
        if total == 0:
            return 100.0
        success = self.successful().count()
        return round(success / total * 100, 2)

    def avg_duration(self) -> float:
        result = self.aggregate(avg=Avg('duration_seconds'))
        return result['avg'] or 0.0

    def p95_duration(self) -> float:
        """Approximate P95 by using 95th percentile of ordered values."""
        durations = list(
            self.filter(duration_seconds__isnull=False)
            .values_list('duration_seconds', flat=True)
            .order_by('duration_seconds')
        )
        if not durations:
            return 0.0
        idx = int(len(durations) * 0.95)
        return durations[min(idx, len(durations) - 1)]

    def task_stats(self, task_name: str, hours: int = 24) -> dict:
        qs = self.for_task(task_name).recent(hours)
        return qs.aggregate(
            total=Count('id'),
            successes=Count('id', filter=Q(result='success')),
            failures=Count('id', filter=Q(result='failure')),
            avg_duration=Avg('duration_seconds'),
            max_duration=Max('duration_seconds'),
            min_duration=Min('duration_seconds'),
        )


class TaskPerformanceLogManager(models.Manager):
    def get_queryset(self):
        return TaskPerformanceLogQuerySet(self.model, using=self._db)

    def recent(self, hours: int = 24):
        return self.get_queryset().recent(hours)

    def for_task(self, task_name: str):
        return self.get_queryset().for_task(task_name)

    def task_stats(self, task_name: str, hours: int = 24) -> dict:
        return self.get_queryset().task_stats(task_name, hours)


# ══════════════════════════════════════════════════════════════════════════════
# DLQ Manager
# ══════════════════════════════════════════════════════════════════════════════

class DLQQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(reprocess_status='pending')

    def requeued(self):
        return self.filter(reprocess_status='requeued')

    def discarded(self):
        return self.filter(reprocess_status='discarded')

    def by_task(self, task_name: str):
        return self.filter(task_name__icontains=task_name)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(failed_at__gte=cutoff)

    def retryable(self, max_retries: int = 5):
        return self.pending().filter(retry_count__lt=max_retries)

    def top_failing_tasks(self, limit: int = 10):
        return (
            self.pending()
            .values('task_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )

    def stats(self) -> dict:
        return {
            'total':    self.count(),
            'pending':  self.pending().count(),
            'requeued': self.requeued().count(),
            'discarded': self.discarded().count(),
        }


class DLQManager(models.Manager):
    def get_queryset(self):
        return DLQQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()

    def stats(self) -> dict:
        return self.get_queryset().stats()

    def top_failing_tasks(self, limit: int = 10):
        return self.get_queryset().top_failing_tasks(limit)


# ══════════════════════════════════════════════════════════════════════════════
# Workflow Instance Manager
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowInstanceQuerySet(models.QuerySet):

    def running(self):
        return self.filter(status='running')

    def pending(self):
        return self.filter(status='pending')

    def completed(self):
        return self.filter(status='success')

    def failed(self):
        return self.filter(status='failed')

    def for_workflow(self, workflow_id: int):
        return self.filter(workflow_id=workflow_id)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def stale(self, hours: int = 2):
        """Running instances that haven't updated in `hours` hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.running().filter(updated_at__lt=cutoff)

    def success_rate(self) -> float:
        total = self.count()
        if total == 0:
            return 100.0
        success = self.completed().count()
        return round(success / total * 100, 2)


class WorkflowInstanceManager(models.Manager):
    def get_queryset(self):
        return WorkflowInstanceQuerySet(self.model, using=self._db)

    def running(self):
        return self.get_queryset().running()

    def stale(self, hours: int = 2):
        return self.get_queryset().stale(hours)

    def for_workflow(self, workflow_id: int):
        return self.get_queryset().for_workflow(workflow_id)


__all__ = [
    'MasterTaskQuerySet', 'MasterTaskManager',
    'UserTaskCompletionQuerySet', 'UserTaskCompletionManager',
    'AdminLedgerQuerySet', 'AdminLedgerManager',
    'TaskPerformanceLogQuerySet', 'TaskPerformanceLogManager',
    'DLQQuerySet', 'DLQManager',
    'WorkflowInstanceQuerySet', 'WorkflowInstanceManager',
]


# ══════════════════════════════════════════════════════════════════════════════
# WITHDRAWAL PRIORITY MANAGER
# ══════════════════════════════════════════════════════════════════════════════

from django.db import models as _dj_models
from django.utils import timezone as _tz


class WithdrawalPriorityManager(_dj_models.Manager):
    """
    Custom manager for WithdrawalPriority model.
    Provides helper methods for priority queue management.
    """

    def active(self):
        """Return only active (non-expired) priority records."""
        return self.filter(is_active=True, expires_at__gt=_tz.now())

    def expire_stale(self) -> int:
        """
        Deactivate all priority records that have passed their expiry time.
        Returns the number of records deactivated.
        """
        expired_qs = self.filter(is_active=True, expires_at__lte=_tz.now())
        count = expired_qs.count()
        expired_qs.update(is_active=False)
        return count

    def get_top_priority(self, limit: int = 50):
        """Return highest-priority withdrawal requests ordered by priority score."""
        return (
            self.active()
            .select_related('withdrawal_request')
            .order_by('-priority_score', 'created_at')[:limit]
        )
