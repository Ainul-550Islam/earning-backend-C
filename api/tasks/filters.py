"""
api/tasks/filters.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DRF filter classes for task system endpoints.
Uses django-filter for clean, reusable filter sets.
"""

import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


# ══════════════════════════════════════════════════════════════════════════════
# MASTER TASK FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class MasterTaskFilter(django_filters.FilterSet):
    """Filter set for MasterTask list endpoint."""

    name           = django_filters.CharFilter(lookup_expr='icontains')
    task_id        = django_filters.CharFilter(lookup_expr='icontains')
    category       = django_filters.CharFilter(lookup_expr='exact')
    system_type    = django_filters.CharFilter(lookup_expr='exact')
    is_active      = django_filters.BooleanFilter()
    is_featured    = django_filters.BooleanFilter()
    search         = django_filters.CharFilter(method='filter_search')
    created_after  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(task_id__icontains=value) |
            Q(category__icontains=value)
        )

    class Meta:
        try:
            from api.tasks.models import MasterTask
            model = MasterTask
        except ImportError:
            model = None
        fields = ['name', 'task_id', 'category', 'system_type', 'is_active', 'is_featured']


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETION FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class UserTaskCompletionFilter(django_filters.FilterSet):
    """Filter set for UserTaskCompletion list endpoint."""

    user_id          = django_filters.NumberFilter(field_name='user_id')
    task_id          = django_filters.CharFilter(field_name='task__task_id', lookup_expr='exact')
    status           = django_filters.CharFilter(lookup_expr='exact')
    ip_address       = django_filters.CharFilter(lookup_expr='exact')
    completed_after  = django_filters.DateTimeFilter(field_name='completed_at', lookup_expr='gte')
    completed_before = django_filters.DateTimeFilter(field_name='completed_at', lookup_expr='lte')
    completed_today  = django_filters.BooleanFilter(method='filter_today')
    min_reward       = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='gte')
    max_reward       = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='lte')
    is_suspicious    = django_filters.BooleanFilter()

    def filter_today(self, queryset, name, value):
        if value:
            return queryset.filter(completed_at__date=timezone.now().date())
        return queryset

    class Meta:
        try:
            from api.tasks.models import UserTaskCompletion
            model = UserTaskCompletion
        except ImportError:
            model = None
        fields = ['status', 'ip_address']


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN LEDGER FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class AdminLedgerFilter(django_filters.FilterSet):
    """Filter set for AdminLedger list endpoint."""

    source         = django_filters.CharFilter(lookup_expr='exact')
    min_amount     = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount     = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    created_after  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    today          = django_filters.BooleanFilter(method='filter_today')

    def filter_today(self, queryset, name, value):
        if value:
            return queryset.filter(created_at__date=timezone.now().date())
        return queryset

    class Meta:
        try:
            from api.tasks.models import AdminLedger
            model = AdminLedger
        except ImportError:
            model = None
        fields = ['source']


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class TaskMonitorFilter(django_filters.FilterSet):
    """Filter set for TaskMonitor list endpoint."""

    task_name      = django_filters.CharFilter(lookup_expr='icontains')
    status         = django_filters.CharFilter(lookup_expr='exact')
    healthy        = django_filters.BooleanFilter(method='filter_healthy')
    failing        = django_filters.BooleanFilter(method='filter_failing')
    min_success_rate = django_filters.NumberFilter(field_name='success_rate', lookup_expr='gte')
    max_success_rate = django_filters.NumberFilter(field_name='success_rate', lookup_expr='lte')

    def filter_healthy(self, queryset, name, value):
        if value:
            return queryset.filter(status='healthy')
        return queryset.exclude(status='healthy')

    def filter_failing(self, queryset, name, value):
        if value:
            return queryset.filter(status__in=['failing', 'degraded'])
        return queryset

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskMonitor
            model = TaskMonitor
        except ImportError:
            model = None
        fields = ['status', 'task_name']


class TaskPerformanceLogFilter(django_filters.FilterSet):
    """Filter set for TaskPerformanceLog list endpoint."""

    task_name      = django_filters.CharFilter(lookup_expr='icontains')
    result         = django_filters.CharFilter(lookup_expr='exact')
    queue          = django_filters.CharFilter(lookup_expr='exact')
    worker         = django_filters.CharFilter(lookup_expr='icontains')
    min_duration   = django_filters.NumberFilter(field_name='duration_seconds', lookup_expr='gte')
    max_duration   = django_filters.NumberFilter(field_name='duration_seconds', lookup_expr='lte')
    created_after  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_hour      = django_filters.BooleanFilter(method='filter_last_hour')
    has_error      = django_filters.BooleanFilter(method='filter_has_error')

    def filter_last_hour(self, queryset, name, value):
        if value:
            cutoff = timezone.now() - timedelta(hours=1)
            return queryset.filter(created_at__gte=cutoff)
        return queryset

    def filter_has_error(self, queryset, name, value):
        if value:
            return queryset.exclude(error='').exclude(error__isnull=True)
        return queryset.filter(Q(error='') | Q(error__isnull=True))

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            model = TaskPerformanceLog
        except ImportError:
            model = None
        fields = ['task_name', 'result', 'queue', 'worker']


class TaskAlertFilter(django_filters.FilterSet):
    """Filter set for TaskAlert list endpoint."""

    task_name    = django_filters.CharFilter(lookup_expr='icontains')
    alert_type   = django_filters.CharFilter(lookup_expr='exact')
    severity     = django_filters.CharFilter(lookup_expr='exact')
    is_active    = django_filters.BooleanFilter()
    recently_triggered = django_filters.BooleanFilter(method='filter_recent')

    def filter_recent(self, queryset, name, value):
        if value:
            cutoff = timezone.now() - timedelta(hours=24)
            return queryset.filter(last_triggered_at__gte=cutoff)
        return queryset

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskAlert
            model = TaskAlert
        except ImportError:
            model = None
        fields = ['alert_type', 'severity', 'is_active']


class WorkerHealthFilter(django_filters.FilterSet):
    """Filter set for WorkerHealth list endpoint."""

    hostname   = django_filters.CharFilter(lookup_expr='icontains')
    status     = django_filters.CharFilter(lookup_expr='exact')
    is_stale   = django_filters.BooleanFilter(method='filter_stale')
    queue_name = django_filters.CharFilter(method='filter_by_queue')

    def filter_stale(self, queryset, name, value):
        cutoff = timezone.now() - timedelta(minutes=5)
        if value:
            return queryset.filter(last_heartbeat__lt=cutoff)
        return queryset.filter(last_heartbeat__gte=cutoff)

    def filter_by_queue(self, queryset, name, value):
        return queryset.filter(queue_names__contains=[value])

    class Meta:
        try:
            from api.tasks.models.monitoring import WorkerHealth
            model = WorkerHealth
        except ImportError:
            model = None
        fields = ['hostname', 'status']


class QueueDepthFilter(django_filters.FilterSet):
    """Filter set for QueueDepth list endpoint."""

    queue_name  = django_filters.CharFilter(lookup_expr='exact')
    min_depth   = django_filters.NumberFilter(field_name='depth', lookup_expr='gte')
    max_depth   = django_filters.NumberFilter(field_name='depth', lookup_expr='lte')
    after       = django_filters.DateTimeFilter(field_name='checked_at', lookup_expr='gte')
    before      = django_filters.DateTimeFilter(field_name='checked_at', lookup_expr='lte')

    class Meta:
        try:
            from api.tasks.models.monitoring import QueueDepth
            model = QueueDepth
        except ImportError:
            model = None
        fields = ['queue_name']


# ══════════════════════════════════════════════════════════════════════════════
# QUEUE / DLQ FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class DeadLetterQueueFilter(django_filters.FilterSet):
    """Filter set for TaskDeadLetterQueue list endpoint."""

    task_name         = django_filters.CharFilter(lookup_expr='icontains')
    failure_reason    = django_filters.CharFilter(lookup_expr='exact')
    reprocess_status  = django_filters.CharFilter(lookup_expr='exact')
    queue_name        = django_filters.CharFilter(lookup_expr='exact')
    failed_after      = django_filters.DateTimeFilter(field_name='failed_at', lookup_expr='gte')
    failed_before     = django_filters.DateTimeFilter(field_name='failed_at', lookup_expr='lte')
    min_retry_count   = django_filters.NumberFilter(field_name='retry_count', lookup_expr='gte')
    has_notes         = django_filters.BooleanFilter(method='filter_has_notes')

    def filter_has_notes(self, queryset, name, value):
        if value:
            return queryset.exclude(reprocess_notes='')
        return queryset.filter(reprocess_notes='')

    class Meta:
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue
            model = TaskDeadLetterQueue
        except ImportError:
            model = None
        fields = ['task_name', 'failure_reason', 'reprocess_status', 'queue_name']


class RetryConfigFilter(django_filters.FilterSet):
    """Filter set for TaskRetryConfig list endpoint."""

    task_name    = django_filters.CharFilter(lookup_expr='icontains')
    retry_backoff = django_filters.CharFilter(lookup_expr='exact')
    is_active    = django_filters.BooleanFilter()
    min_retries  = django_filters.NumberFilter(field_name='max_retries', lookup_expr='gte')

    class Meta:
        try:
            from api.tasks.models.queue import TaskRetryConfig
            model = TaskRetryConfig
        except ImportError:
            model = None
        fields = ['task_name', 'retry_backoff', 'is_active']


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowFilter(django_filters.FilterSet):
    """Filter set for TaskWorkflow list endpoint."""

    name          = django_filters.CharFilter(lookup_expr='icontains')
    trigger_type  = django_filters.CharFilter(lookup_expr='exact')
    is_active     = django_filters.BooleanFilter()
    created_by    = django_filters.NumberFilter(field_name='created_by_id')

    class Meta:
        try:
            from api.tasks.models.workflow import TaskWorkflow
            model = TaskWorkflow
        except ImportError:
            model = None
        fields = ['name', 'trigger_type', 'is_active']


class WorkflowInstanceFilter(django_filters.FilterSet):
    """Filter set for WorkflowInstance list endpoint."""

    workflow_id   = django_filters.NumberFilter(field_name='workflow_id')
    status        = django_filters.CharFilter(lookup_expr='exact')
    trigger_type  = django_filters.CharFilter(lookup_expr='exact')
    started_after = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    started_before = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')
    has_error     = django_filters.BooleanFilter(method='filter_has_error')

    def filter_has_error(self, queryset, name, value):
        if value:
            return queryset.exclude(error='')
        return queryset.filter(error='')

    class Meta:
        try:
            from api.tasks.models.workflow import WorkflowInstance
            model = WorkflowInstance
        except ImportError:
            model = None
        fields = ['status', 'trigger_type']


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS FILTERS
# ══════════════════════════════════════════════════════════════════════════════

class TaskInsightFilter(django_filters.FilterSet):
    """Filter set for TaskInsight analytics endpoint."""

    task_name  = django_filters.CharFilter(lookup_expr='icontains')
    queue      = django_filters.CharFilter(lookup_expr='exact')
    date       = django_filters.DateFilter(lookup_expr='exact')
    date_after  = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_before = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    min_runs    = django_filters.NumberFilter(field_name='run_count', lookup_expr='gte')
    has_failures = django_filters.BooleanFilter(method='filter_has_failures')

    def filter_has_failures(self, queryset, name, value):
        if value:
            return queryset.filter(failure_count__gt=0)
        return queryset.filter(failure_count=0)

    class Meta:
        try:
            from api.tasks.models.analytics import TaskInsight
            model = TaskInsight
        except ImportError:
            model = None
        fields = ['task_name', 'queue']


class TaskCostFilter(django_filters.FilterSet):
    """Filter set for TaskCostEstimate endpoint."""

    task_name    = django_filters.CharFilter(lookup_expr='icontains')
    min_cost     = django_filters.NumberFilter(field_name='cost_per_run', lookup_expr='gte')
    max_cost     = django_filters.NumberFilter(field_name='cost_per_run', lookup_expr='lte')
    currency     = django_filters.CharFilter(lookup_expr='exact')

    class Meta:
        try:
            from api.tasks.models.analytics import TaskCostEstimate
            model = TaskCostEstimate
        except ImportError:
            model = None
        fields = ['task_name', 'currency']


__all__ = [
    'MasterTaskFilter', 'UserTaskCompletionFilter', 'AdminLedgerFilter',
    'TaskMonitorFilter', 'TaskPerformanceLogFilter', 'TaskAlertFilter',
    'WorkerHealthFilter', 'QueueDepthFilter',
    'DeadLetterQueueFilter', 'RetryConfigFilter',
    'WorkflowFilter', 'WorkflowInstanceFilter',
    'TaskInsightFilter', 'TaskCostFilter',
]
