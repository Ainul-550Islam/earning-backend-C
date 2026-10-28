"""
tasks/new_serializers.py
DRF serializers for all new task system models.
Imported by viewsets; existing serializers.py kept untouched.
"""
from rest_framework import serializers


# ══════════════════════════════════════════════════════
# CORE
# ══════════════════════════════════════════════════════

class TaskResultSerializer(serializers.ModelSerializer):
    is_terminal = serializers.ReadOnlyField()
    failed      = serializers.ReadOnlyField()
    succeeded   = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.core import TaskResult
            model = TaskResult
        except Exception:
            model = None
        fields = [
            'id', 'task_id', 'task_name', 'status', 'date_created',
            'date_started', 'date_done', 'duration_seconds', 'result',
            'traceback', 'meta', 'worker', 'queue', 'retry_count',
            'triggered_by', 'is_terminal', 'failed', 'succeeded',
        ]
        read_only_fields = [
            'task_id', 'date_created', 'date_started', 'date_done',
            'duration_seconds', 'is_terminal', 'failed', 'succeeded',
        ]


class ScheduledTaskSerializer(serializers.ModelSerializer):
    success_rate = serializers.ReadOnlyField()
    is_running   = serializers.ReadOnlyField()
    is_expired   = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.core import ScheduledTask
            model = ScheduledTask
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = [
            'last_run_at', 'last_run_status', 'total_runs',
            'total_failures', 'avg_duration_sec',
        ]


# ══════════════════════════════════════════════════════
# QUEUE
# ══════════════════════════════════════════════════════

class TaskQueueSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.queue import TaskQueue
            model = TaskQueue
        except Exception:
            model = None
        fields = '__all__'


class TaskPrioritySerializer(serializers.ModelSerializer):
    queue_name = serializers.CharField(source='queue.name', read_only=True)

    class Meta:
        try:
            from api.tasks.models.queue import TaskPriority
            model = TaskPriority
        except Exception:
            model = None
        fields = '__all__'


class TaskDeadLetterQueueSerializer(serializers.ModelSerializer):
    is_pending = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue
            model = TaskDeadLetterQueue
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['failed_at', 'reprocessed_at', 'new_task_id']


class TaskRetryConfigSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.queue import TaskRetryConfig
            model = TaskRetryConfig
        except Exception:
            model = None
        fields = '__all__'


# ══════════════════════════════════════════════════════
# MONITORING
# ══════════════════════════════════════════════════════

class TaskMonitorSerializer(serializers.ModelSerializer):
    alerts_suppressed = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskMonitor
            model = TaskMonitor
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = [
            'last_run_at', 'last_success_at', 'last_failure_at',
            'avg_duration_seconds', 'p95_duration_seconds', 'success_rate',
            'total_runs_last_24h', 'total_failures_last_24h',
        ]


class TaskAlertSerializer(serializers.ModelSerializer):
    is_in_cooldown = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskAlert
            model = TaskAlert
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['last_triggered_at', 'trigger_count']


class TaskPerformanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            model = TaskPerformanceLog
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['created_at']


class WorkerHealthSerializer(serializers.ModelSerializer):
    is_stale = serializers.ReadOnlyField()
    load_pct = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.monitoring import WorkerHealth
            model = WorkerHealth
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['last_heartbeat', 'processed_total', 'failed_total']


class QueueDepthSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.monitoring import QueueDepth
            model = QueueDepth
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['checked_at']


# ══════════════════════════════════════════════════════
# WORKFLOW
# ══════════════════════════════════════════════════════

class WorkflowStepSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.workflow import WorkflowStep
            model = WorkflowStep
        except Exception:
            model = None
        fields = '__all__'


class TaskWorkflowSerializer(serializers.ModelSerializer):
    step_count = serializers.ReadOnlyField()
    steps_detail = WorkflowStepSerializer(source='workflow_steps', many=True, read_only=True)

    class Meta:
        try:
            from api.tasks.models.workflow import TaskWorkflow
            model = TaskWorkflow
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'step_count']


class WorkflowLogSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.workflow import WorkflowLog
            model = WorkflowLog
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['created_at']


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    workflow_name    = serializers.CharField(source='workflow.name', read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    logs             = WorkflowLogSerializer(many=True, read_only=True)

    class Meta:
        try:
            from api.tasks.models.workflow import WorkflowInstance
            model = WorkflowInstance
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = [
            'started_at', 'completed_at', 'duration_seconds',
            'current_step', 'error', 'created_at', 'updated_at',
        ]


class WorkflowTriggerSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        try:
            from api.tasks.models.workflow import WorkflowTrigger
            model = WorkflowTrigger
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['trigger_count', 'last_triggered_at']


# ══════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════

class TaskInsightSerializer(serializers.ModelSerializer):
    success_rate = serializers.ReadOnlyField()
    failure_rate = serializers.ReadOnlyField()

    class Meta:
        try:
            from api.tasks.models.analytics import TaskInsight
            model = TaskInsight
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TaskThroughputSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.analytics import TaskThroughput
            model = TaskThroughput
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['snapshot_at']


class TaskFailureRateSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.analytics import TaskFailureRate
            model = TaskFailureRate
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['created_at']


class TaskCostEstimateSerializer(serializers.ModelSerializer):
    class Meta:
        try:
            from api.tasks.models.analytics import TaskCostEstimate
            model = TaskCostEstimate
        except Exception:
            model = None
        fields = '__all__'
        read_only_fields = ['calculated_at', 'created_at', 'updated_at']
