"""
api/tasks/admin_inline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django admin inline classes for the task system.
Used in admin.py to show related data inline.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone


class UserTaskCompletionInline(admin.TabularInline):
    """Show task completions inline on the MasterTask admin page."""

    try:
        from api.tasks.models import UserTaskCompletion
        model = UserTaskCompletion
    except ImportError:
        model = None

    extra      = 0
    max_num    = 20
    can_delete = False
    show_change_link = True

    fields  = ('user', 'status', 'reward_amount', 'ip_address', 'completed_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-completed_at')


class AdminLedgerInline(admin.TabularInline):
    """Show admin revenue inline on completion admin page."""

    try:
        from api.tasks.models import AdminLedger
        model = AdminLedger
    except ImportError:
        model = None

    extra      = 0
    can_delete = False

    fields  = ('amount', 'source', 'created_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class WorkflowStepInline(admin.TabularInline):
    """Show workflow steps inline on TaskWorkflow admin."""

    try:
        from api.tasks.models.workflow import WorkflowStep
        model = WorkflowStep
    except ImportError:
        model = None

    extra   = 1
    fields  = ('step_order', 'name', 'task_name', 'queue', 'is_active')
    ordering = ('step_order',)


class WorkflowInstanceInline(admin.TabularInline):
    """Show recent workflow runs inline."""

    try:
        from api.tasks.models.workflow import WorkflowInstance
        model = WorkflowInstance
    except ImportError:
        model = None

    extra      = 0
    max_num    = 10
    can_delete = False
    show_change_link = True

    fields  = ('status', 'started_at', 'finished_at', 'error')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')


class TaskAlertInline(admin.TabularInline):
    """Show alerts inline on TaskMonitor admin."""

    try:
        from api.tasks.models.monitoring import TaskAlert
        model = TaskAlert
    except ImportError:
        model = None

    extra   = 0
    fields  = ('alert_type', 'severity', 'threshold', 'is_active', 'last_triggered_at')
    readonly_fields = ('last_triggered_at',)


class TaskPerformanceLogInline(admin.TabularInline):
    """Show recent performance logs inline on TaskMonitor."""

    try:
        from api.tasks.models.monitoring import TaskPerformanceLog
        model = TaskPerformanceLog
    except ImportError:
        model = None

    extra      = 0
    max_num    = 10
    can_delete = False

    fields  = ('result', 'duration_seconds', 'queue', 'worker', 'created_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')


class TaskQueueInline(admin.TabularInline):
    """Show task queues inline on TaskResult admin."""

    try:
        from api.tasks.models.queue import TaskQueue
        model = TaskQueue
    except ImportError:
        model = None

    extra   = 0
    fields  = ('queue_name', 'is_active', 'max_retries', 'default_timeout')


class TaskRetryConfigInline(admin.TabularInline):
    """Show retry config inline on task admin."""

    try:
        from api.tasks.models.queue import TaskRetryConfig
        model = TaskRetryConfig
    except ImportError:
        model = None

    extra  = 0
    fields = ('task_name', 'max_retries', 'retry_backoff', 'base_delay', 'is_active')


__all__ = [
    'UserTaskCompletionInline', 'AdminLedgerInline',
    'WorkflowStepInline', 'WorkflowInstanceInline',
    'TaskAlertInline', 'TaskPerformanceLogInline',
    'TaskQueueInline', 'TaskRetryConfigInline',
]
