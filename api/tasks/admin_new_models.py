"""
tasks/admin_new_models.py
Django Admin registrations for all NEW task system models.
This file is imported at the bottom of admin.py.

New models covered:
  Core:       TaskResult, ScheduledTask
  Queue:      TaskQueue, TaskPriority, TaskDeadLetterQueue, TaskRetryConfig
  Monitoring: TaskMonitor, TaskAlert, TaskPerformanceLog, WorkerHealth, QueueDepth
  Workflow:   TaskWorkflow, WorkflowStep, WorkflowInstance, WorkflowLog, WorkflowTrigger
  Analytics:  TaskInsight, TaskThroughput, TaskFailureRate, TaskCostEstimate
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg, Sum
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CORE MODELS
# ══════════════════════════════════════════════════════════════════════════════

# helper: _safe_register defined below

def _safe_register(model, admin_class):
    """Register model only if not already registered."""
    try:
        if not admin.site.is_registered(model):
            admin.site.register(model, admin_class)
    except Exception as e:
        logger.warning(f"[WARN] Admin register {model}: {e}")


# ── TaskResult ─────────────────────────────────────────────────────────────

class TaskResultAdmin(admin.ModelAdmin):
    list_display  = ['task_id_short', 'task_name', 'status_badge', 'duration_seconds',
                     'worker', 'queue', 'date_created']
    list_filter   = ['status', 'queue', 'worker']
    search_fields = ['task_name', 'worker', 'queue']
    readonly_fields = ['task_id', 'date_created', 'date_started', 'date_done',
                       'duration_seconds', 'result', 'traceback']
    ordering      = ['-date_created']
    list_per_page = 50

    def task_id_short(self, obj):
        return str(obj.task_id)[:12] + '…'
    task_id_short.short_description = 'Task ID'

    def status_badge(self, obj):
        colors = {
            'success': '#27ae60', 'failure': '#e74c3c',
            'pending': '#f39c12', 'started': '#3498db',
            'retry': '#e67e22', 'revoked': '#95a5a6',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'


# ── ScheduledTask ──────────────────────────────────────────────────────────

class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display  = ['name', 'task_name', 'schedule_type', 'is_active', 'is_paused',
                     'last_run_at', 'total_runs', 'success_rate_display']
    list_filter   = ['schedule_type', 'is_active', 'is_paused', 'priority']
    search_fields = ['name', 'task_name']
    readonly_fields = ['last_run_at', 'last_run_status', 'total_runs',
                       'total_failures', 'avg_duration_sec']
    ordering      = ['name']
    actions       = ['pause_tasks', 'resume_tasks']

    def success_rate_display(self, obj):
        rate = obj.success_rate
        color = '#27ae60' if rate >= 90 else ('#e67e22' if rate >= 70 else '#e74c3c')
        return format_html(
            '<span style="color:{};font-weight:bold">{:.1f}%</span>', color, rate
        )
    success_rate_display.short_description = 'Success Rate'

    def pause_tasks(self, request, queryset):
        for task in queryset:
            task.pause()
        self.message_user(request, f'{queryset.count()} tasks paused.')
    pause_tasks.short_description = 'Pause selected tasks'

    def resume_tasks(self, request, queryset):
        for task in queryset:
            task.resume()
        self.message_user(request, f'{queryset.count()} tasks resumed.')
    resume_tasks.short_description = 'Resume selected tasks'


# ══════════════════════════════════════════════════════════════════════════════
# QUEUE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TaskQueueAdmin(admin.ModelAdmin):
    list_display  = ['name', 'priority_level', 'max_concurrency', 'is_active',
                     'alert_depth_warning', 'alert_depth_critical']
    list_filter   = ['is_active', 'priority_level']
    search_fields = ['name', 'description']
    ordering      = ['-priority_level', 'name']


class TaskPriorityAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'queue', 'priority', 'timeout_seconds', 'is_active']
    list_filter   = ['queue', 'priority', 'is_active']
    search_fields = ['task_name']
    ordering      = ['-priority', 'task_name']


class TaskDeadLetterQueueAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'task_id_short', 'failure_reason_badge', 'retry_count',
                     'reprocess_status_badge', 'failed_at']
    list_filter   = ['failure_reason', 'reprocess_status', 'queue_name']
    search_fields = ['task_name', 'task_id', 'error']
    readonly_fields = ['task_id', 'failed_at', 'error', 'traceback', 'payload',
                       'retry_count', 'worker_hostname']
    ordering      = ['-failed_at']
    actions       = ['retry_selected', 'discard_selected']
    list_per_page = 50

    def task_id_short(self, obj):
        return obj.task_id[:20] + '…' if len(obj.task_id) > 20 else obj.task_id
    task_id_short.short_description = 'Task ID'

    def failure_reason_badge(self, obj):
        colors = {
            'exception': '#e74c3c', 'timeout': '#e67e22',
            'max_retries': '#c0392b', 'worker_lost': '#8e44ad',
            'revoked': '#7f8c8d',
        }
        color = colors.get(obj.failure_reason, '#999')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.get_failure_reason_display()
        )
    failure_reason_badge.short_description = 'Reason'

    def reprocess_status_badge(self, obj):
        colors = {'pending': '#e67e22', 'requeued': '#27ae60',
                  'resolved': '#3498db', 'discarded': '#95a5a6'}
        color = colors.get(obj.reprocess_status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.reprocess_status.upper()
        )
    reprocess_status_badge.short_description = 'Status'

    def retry_selected(self, request, queryset):
        from api.tasks.services.DeadLetterService import DeadLetterService
        svc = DeadLetterService()
        retried = 0
        for entry in queryset.filter(reprocess_status='pending'):
            result = svc.retry_entry(entry.pk)
            if result.get('success'):
                retried += 1
        self.message_user(request, f'{retried} entries re-queued.')
    retry_selected.short_description = 'Retry selected DLQ entries'

    def discard_selected(self, request, queryset):
        count = queryset.update(reprocess_status='discarded', reprocessed_at=timezone.now())
        self.message_user(request, f'{count} entries discarded.')
    discard_selected.short_description = 'Discard selected DLQ entries'


class TaskRetryConfigAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'max_retries', 'retry_backoff', 'retry_delay_seconds',
                     'backoff_multiplier', 'jitter', 'is_active']
    list_filter   = ['retry_backoff', 'is_active']
    search_fields = ['task_name']
    ordering      = ['task_name']


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TaskMonitorAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'status_badge', 'success_rate_display',
                     'avg_duration_seconds', 'total_runs_last_24h', 'last_run_at']
    list_filter   = ['status']
    search_fields = ['task_name']
    readonly_fields = ['last_run_at', 'last_success_at', 'last_failure_at',
                       'avg_duration_seconds', 'success_rate', 'total_runs_last_24h',
                       'total_failures_last_24h', 'p95_duration_seconds']
    ordering      = ['task_name']

    def status_badge(self, obj):
        colors = {'healthy': '#27ae60', 'degraded': '#e67e22',
                  'failing': '#e74c3c', 'missing': '#8e44ad', 'unknown': '#95a5a6'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def success_rate_display(self, obj):
        if obj.success_rate is None:
            return '—'
        color = '#27ae60' if obj.success_rate >= 90 else '#e74c3c'
        return format_html('<span style="color:{};font-weight:bold">{:.1f}%</span>',
                           color, obj.success_rate)
    success_rate_display.short_description = 'Success Rate'


class TaskAlertAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'alert_type', 'severity_badge', 'threshold',
                     'is_active', 'trigger_count', 'last_triggered_at']
    list_filter   = ['alert_type', 'severity', 'is_active']
    search_fields = ['task_name', 'description']
    ordering      = ['task_name', 'alert_type']
    actions       = ['activate_alerts', 'deactivate_alerts', 'test_fire']

    def severity_badge(self, obj):
        colors = {'info': '#3498db', 'warning': '#e67e22', 'critical': '#e74c3c'}
        color = colors.get(obj.severity, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'

    def activate_alerts(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} alerts activated.')
    activate_alerts.short_description = 'Activate selected alerts'

    def deactivate_alerts(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} alerts deactivated.')
    deactivate_alerts.short_description = 'Deactivate selected alerts'

    def test_fire(self, request, queryset):
        from api.tasks.services.TaskAlertService import TaskAlertService
        svc = TaskAlertService()
        for alert in queryset:
            svc.trigger_manual(alert.pk)
        self.message_user(request, f'{queryset.count()} alerts manually fired.')
    test_fire.short_description = 'Manually fire selected alerts'


class TaskPerformanceLogAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'result_badge', 'duration_seconds', 'queue',
                     'worker', 'retry_count', 'created_at']
    list_filter   = ['result', 'queue']
    search_fields = ['task_name', 'task_id', 'worker', 'error']
    readonly_fields = ['task_id', 'task_name', 'result', 'duration_seconds',
                       'error', 'output', 'created_at', 'started_at', 'completed_at']
    ordering      = ['-created_at']
    list_per_page = 100

    def result_badge(self, obj):
        colors = {'success': '#27ae60', 'failure': '#e74c3c',
                  'timeout': '#e67e22', 'retry': '#f39c12'}
        color = colors.get(obj.result, '#999')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>', color, obj.result.upper()
        )
    result_badge.short_description = 'Result'


class WorkerHealthAdmin(admin.ModelAdmin):
    list_display  = ['worker_id', 'hostname', 'status_badge', 'active_tasks',
                     'concurrency', 'load_pct_display', 'last_heartbeat']
    list_filter   = ['status']
    search_fields = ['worker_id', 'hostname']
    readonly_fields = ['worker_id', 'processed_total', 'failed_total',
                       'last_heartbeat', 'cpu_percent', 'memory_mb']
    ordering      = ['-last_heartbeat']

    def status_badge(self, obj):
        colors = {'online': '#27ae60', 'offline': '#e74c3c', 'idle': '#3498db',
                  'busy': '#e67e22', 'degraded': '#8e44ad'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def load_pct_display(self, obj):
        pct = obj.load_pct
        color = '#27ae60' if pct < 70 else ('#e67e22' if pct < 90 else '#e74c3c')
        return format_html('<span style="color:{}">{:.0f}%</span>', color, pct)
    load_pct_display.short_description = 'Load'


class QueueDepthAdmin(admin.ModelAdmin):
    list_display  = ['queue_name', 'depth_display', 'processing_count',
                     'failed_count', 'consumer_count', 'checked_at']
    list_filter   = ['queue_name']
    readonly_fields = list_display + ['avg_wait_seconds', 'oldest_message_at']
    ordering      = ['-checked_at']
    list_per_page = 100

    def depth_display(self, obj):
        color = '#27ae60' if obj.depth < 50 else ('#e67e22' if obj.depth < 200 else '#e74c3c')
        return format_html('<span style="color:{};font-weight:bold">{}</span>', color, obj.depth)
    depth_display.short_description = 'Depth'


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW MODELS
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowStepInline(admin.TabularInline):
    try:
        from api.tasks.models.workflow import WorkflowStep
        model = WorkflowStep
    except Exception:
        model = None
    extra         = 0
    fields        = ['step_number', 'task_name', 'label', 'on_failure',
                     'timeout_seconds', 'max_retries', 'is_active']
    ordering      = ['step_number']


class TaskWorkflowAdmin(admin.ModelAdmin):
    list_display  = ['name', 'trigger_type', 'on_failure', 'is_active',
                     'step_count_display', 'created_at']
    list_filter   = ['trigger_type', 'on_failure', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering      = ['name']
    inlines       = [WorkflowStepInline]

    def step_count_display(self, obj):
        return obj.step_count
    step_count_display.short_description = 'Steps'


class WorkflowStepAdmin(admin.ModelAdmin):
    list_display  = ['workflow', 'step_number', 'label', 'task_name',
                     'on_failure', 'timeout_seconds', 'is_active']
    list_filter   = ['workflow', 'on_failure', 'is_active']
    search_fields = ['task_name', 'label', 'workflow__name']
    ordering      = ['workflow', 'step_number']


class WorkflowLogInline(admin.TabularInline):
    try:
        from api.tasks.models.workflow import WorkflowLog
        model = WorkflowLog
    except Exception:
        model = None
    extra     = 0
    readonly_fields = ['step_number', 'task_name', 'status', 'output',
                       'error', 'duration_seconds', 'started_at', 'completed_at']
    can_delete = False
    ordering   = ['step_number']


class WorkflowInstanceAdmin(admin.ModelAdmin):
    list_display  = ['id', 'workflow', 'status_badge', 'current_step',
                     'started_at', 'completed_at', 'duration_seconds']
    list_filter   = ['status', 'trigger_type']
    search_fields = ['workflow__name', 'trigger_ref']
    readonly_fields = ['workflow', 'status', 'current_step', 'input_data',
                       'context_data', 'started_at', 'completed_at',
                       'duration_seconds', 'error', 'triggered_by']
    ordering      = ['-created_at']
    inlines       = [WorkflowLogInline]

    def status_badge(self, obj):
        colors = {'pending': '#f39c12', 'running': '#3498db', 'success': '#27ae60',
                  'failed': '#e74c3c', 'cancelled': '#95a5a6', 'partial': '#e67e22'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'


class WorkflowLogAdmin(admin.ModelAdmin):
    list_display  = ['instance', 'step_number', 'task_name', 'status',
                     'duration_seconds', 'retry_count', 'started_at']
    list_filter   = ['status']
    search_fields = ['task_name', 'error', 'instance__id']
    readonly_fields = list_display + ['output', 'error', 'celery_task_id', 'completed_at']
    ordering      = ['instance', 'step_number']


class WorkflowTriggerAdmin(admin.ModelAdmin):
    list_display  = ['workflow', 'trigger_type', 'is_active',
                     'trigger_count', 'last_triggered_at']
    list_filter   = ['trigger_type', 'is_active']
    search_fields = ['workflow__name', 'description']
    readonly_fields = ['trigger_count', 'last_triggered_at']
    ordering      = ['workflow', 'trigger_type']


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TaskInsightAdmin(admin.ModelAdmin):
    list_display  = ['date', 'task_name', 'run_count', 'success_count',
                     'failure_count', 'success_rate_display', 'avg_duration']
    list_filter   = ['queue']
    search_fields = ['task_name']
    date_hierarchy = 'date'
    ordering      = ['-date', 'task_name']
    readonly_fields = list_display + ['retry_count', 'p50_duration', 'p95_duration',
                                       'p99_duration', 'total_cpu_seconds', 'avg_memory_mb']

    def success_rate_display(self, obj):
        rate = obj.success_rate
        color = '#27ae60' if rate >= 90 else ('#e67e22' if rate >= 70 else '#e74c3c')
        return format_html('<span style="color:{};font-weight:bold">{:.1f}%</span>', color, rate)
    success_rate_display.short_description = 'Success Rate'


class TaskThroughputAdmin(admin.ModelAdmin):
    list_display  = ['queue_name', 'tasks_per_minute', 'tasks_per_hour',
                     'period', 'completed_count', 'failed_count', 'snapshot_at']
    list_filter   = ['queue_name', 'period']
    readonly_fields = list_display + ['avg_wait_seconds']
    ordering      = ['-snapshot_at']
    list_per_page = 100


class TaskFailureRateAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'period', 'period_start', 'total_runs',
                     'failure_count', 'failure_pct_display', 'most_common_error_short']
    list_filter   = ['period']
    search_fields = ['task_name', 'most_common_error']
    readonly_fields = ['task_name', 'period', 'period_start', 'period_end',
                       'total_runs', 'failure_count', 'failure_pct',
                       'most_common_error', 'most_common_error_count', 'error_breakdown']
    ordering      = ['-period_start', '-failure_pct']

    def failure_pct_display(self, obj):
        color = '#e74c3c' if obj.failure_pct > 20 else ('#e67e22' if obj.failure_pct > 5 else '#27ae60')
        return format_html('<span style="color:{};font-weight:bold">{:.1f}%</span>',
                           color, obj.failure_pct)
    failure_pct_display.short_description = 'Failure %'

    def most_common_error_short(self, obj):
        err = obj.most_common_error or '—'
        return err[:60] + '…' if len(err) > 60 else err
    most_common_error_short.short_description = 'Most Common Error'


class TaskCostEstimateAdmin(admin.ModelAdmin):
    list_display  = ['task_name', 'cost_per_run', 'monthly_cost_est',
                     'avg_wall_seconds', 'avg_cpu_seconds', 'avg_memory_mb',
                     'sample_size', 'calculated_at']
    search_fields = ['task_name']
    readonly_fields = list_display + ['cpu_cost_per_second', 'memory_cost_per_mb_sec',
                                       'runs_per_day_avg', 'estimation_period']
    ordering      = ['-cost_per_run']
    actions       = ['refresh_estimates']

    def refresh_estimates(self, request, queryset):
        from api.tasks.services.TaskCostService import TaskCostService
        svc = TaskCostService()
        updated = 0
        for est in queryset:
            result = svc.update_cost_estimate(est.task_name)
            if result.get('success'):
                updated += 1
        self.message_user(request, f'{updated} cost estimates refreshed.')
    refresh_estimates.short_description = 'Refresh cost estimates'


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitConfigAdmin(admin.ModelAdmin):
    list_display = ['limit_type', 'display_name', 'limit', 'window_seconds',
                    'scope_badge', 'is_active_badge', 'requests_per_hour', 'updated_at']
    list_filter = ['scope', 'is_active', 'is_default']
    search_fields = ['limit_type', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['limit_type']
    actions = ['activate_limits', 'deactivate_limits', 'reset_to_defaults']

    fieldsets = (
        ('Basic Configuration', {
            'fields': ('limit_type', 'display_name', 'description')
        }),
        ('Rate Limits', {
            'fields': ('limit', 'window_seconds'),
            'description': 'Maximum requests allowed within the time window.'
        }),
        ('Scope & Status', {
            'fields': ('scope', 'is_active', 'is_default'),
            'description': 'Scope determines whether limits apply per user, globally, or per IP.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def scope_badge(self, obj):
        colors = {
            'user': '#3498db',
            'global': '#e74c3c',
            'ip': '#9b59b6'
        }
        color = colors.get(obj.scope, '#95a5a6')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.get_scope_display()
        )
    scope_badge.short_description = 'Scope'

    def is_active_badge(self, obj):
        color = '#27ae60' if obj.is_active else '#e74c3c'
        status = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, status
        )
    is_active_badge.short_description = 'Status'

    def requests_per_hour(self, obj):
        rate = obj.get_requests_per_hour()
        return f"{rate:.1f}"
    requests_per_hour.short_description = 'Req/Hour'
    requests_per_hour.admin_order_field = 'limit'

    def activate_limits(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} rate limits activated.')
    activate_limits.short_description = 'Activate selected rate limits'

    def deactivate_limits(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} rate limits deactivated.')
    deactivate_limits.short_description = 'Deactivate selected rate limits'

    def reset_to_defaults(self, request, queryset):
        from api.tasks.middleware_rate_limit import DEFAULT_RATE_LIMITS
        updated = 0
        for config in queryset.filter(is_default=True):
            if config.limit_type in DEFAULT_RATE_LIMITS:
                default = DEFAULT_RATE_LIMITS[config.limit_type]
                config.limit = default['limit']
                config.window_seconds = default['window']
                config.scope = default.get('scope', 'user')
                config.save()
                updated += 1
        self.message_user(request, f'{updated} rate limits reset to defaults.')
    reset_to_defaults.short_description = 'Reset default limits to system defaults'

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of default system limits
        if obj and obj.is_default:
            return False
        return super().has_delete_permission(request, obj)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTER ALL NEW MODELS
# ══════════════════════════════════════════════════════════════════════════════

def register_all_new_models():
    """
    Register all new task system models to admin.
    Called at module load and from apps.py ready().
    """
    registrations = []

    # Rate Limit Configuration
    try:
        from api.tasks.models import RateLimitConfig
        registrations += [
            (RateLimitConfig, RateLimitConfigAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] RateLimitConfig model not importable: {e}")

    try:
        from api.tasks.models.core import TaskResult, ScheduledTask
        registrations += [
            (TaskResult,      TaskResultAdmin),
            (ScheduledTask,   ScheduledTaskAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] core models not importable: {e}")

    try:
        from api.tasks.models.queue import (
            TaskQueue, TaskPriority, TaskDeadLetterQueue, TaskRetryConfig
        )
        registrations += [
            (TaskQueue,            TaskQueueAdmin),
            (TaskPriority,         TaskPriorityAdmin),
            (TaskDeadLetterQueue,  TaskDeadLetterQueueAdmin),
            (TaskRetryConfig,      TaskRetryConfigAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] queue models not importable: {e}")

    try:
        from api.tasks.models.monitoring import (
            TaskMonitor, TaskAlert, TaskPerformanceLog, WorkerHealth, QueueDepth
        )
        registrations += [
            (TaskMonitor,       TaskMonitorAdmin),
            (TaskAlert,         TaskAlertAdmin),
            (TaskPerformanceLog, TaskPerformanceLogAdmin),
            (WorkerHealth,      WorkerHealthAdmin),
            (QueueDepth,        QueueDepthAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] monitoring models not importable: {e}")

    try:
        from api.tasks.models.workflow import (
            TaskWorkflow, WorkflowStep, WorkflowInstance, WorkflowLog, WorkflowTrigger
        )
        registrations += [
            (TaskWorkflow,      TaskWorkflowAdmin),
            (WorkflowStep,      WorkflowStepAdmin),
            (WorkflowInstance,  WorkflowInstanceAdmin),
            (WorkflowLog,       WorkflowLogAdmin),
            (WorkflowTrigger,   WorkflowTriggerAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] workflow models not importable: {e}")

    try:
        from api.tasks.models.analytics import (
            TaskInsight, TaskThroughput, TaskFailureRate, TaskCostEstimate
        )
        registrations += [
            (TaskInsight,       TaskInsightAdmin),
            (TaskThroughput,    TaskThroughputAdmin),
            (TaskFailureRate,   TaskFailureRateAdmin),
            (TaskCostEstimate,  TaskCostEstimateAdmin),
        ]
    except ImportError as e:
        logger.warning(f"[WARN] analytics models not importable: {e}")

    registered = 0
    for model, admin_class in registrations:
        try:
            if not admin.site.is_registered(model):
                admin.site.register(model, admin_class)
                registered += 1
        except Exception as exc:
            logger.warning(f"[WARN] Could not register {model}: {exc}")

    logger.info(f"[OK] Registered {registered}/{len(registrations)} new task models to admin.")
    return registered


# Auto-register on module import
try:
    register_all_new_models()
except Exception as e:
    logger.warning(f"[WARN] admin_new_models auto-register: {e}")
