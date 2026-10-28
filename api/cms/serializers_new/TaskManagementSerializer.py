# api/cms/serializers_new/TaskManagementSerializer.py
"""
Serializers for Task Management Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.task_management import (
    TaskSchedule, TaskExecution, TaskQueue, TaskLock
)

User = get_user_model()


class TaskScheduleSerializer(serializers.ModelSerializer):
    """Basic task schedule serializer"""
    class Meta:
        model = TaskSchedule
        fields = [
            'uuid', 'name', 'description', 'task_path', 'frequency',
            'cron_expression', 'timezone', 'start_time', 'end_time',
            'next_run', 'last_run', 'status', 'priority',
            'task_args', 'task_kwargs', 'max_retries', 'retry_delay',
            'timeout_seconds', 'memory_limit_mb', 'notify_on_success',
            'notify_on_failure', 'notification_emails', 'total_runs',
            'successful_runs', 'failed_runs', 'average_runtime',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class TaskScheduleDetailSerializer(serializers.ModelSerializer):
    """Detailed task schedule serializer with relationships"""
    depends_on = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskSchedule
        fields = [
            'uuid', 'name', 'description', 'task_path', 'frequency',
            'cron_expression', 'timezone', 'start_time', 'end_time',
            'next_run', 'last_run', 'status', 'priority',
            'task_args', 'task_kwargs', 'max_retries', 'retry_delay',
            'timeout_seconds', 'memory_limit_mb', 'notify_on_success',
            'notify_on_failure', 'notification_emails', 'total_runs',
            'successful_runs', 'failed_runs', 'average_runtime',
            'depends_on', 'created_by', 'created_by_username',
            'success_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_depends_on(self, obj):
        """Get dependency tasks"""
        depends_on = obj.depends_on.all()
        return TaskScheduleSerializer(depends_on, many=True).data
    
    def get_created_by_username(self, obj):
        """Get created by username"""
        return obj.created_by.username if obj.created_by else None
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_runs > 0:
            return round((obj.successful_runs / obj.total_runs) * 100, 2)
        return 0


class TaskScheduleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating task schedules"""
    class Meta:
        model = TaskSchedule
        fields = [
            'name', 'description', 'task_path', 'frequency',
            'cron_expression', 'timezone', 'start_time', 'end_time',
            'priority', 'task_args', 'task_kwargs', 'max_retries',
            'retry_delay', 'timeout_seconds', 'memory_limit_mb',
            'notify_on_success', 'notify_on_failure', 'notification_emails'
        ]
    
    def validate_frequency(self, value):
        """Validate frequency field"""
        valid_frequencies = ['once', 'minutely', 'hourly', 'daily', 'weekly', 'monthly', 'custom']
        if value not in valid_frequencies:
            raise serializers.ValidationError(f"Invalid frequency: {value}")
        return value
    
    def validate_priority(self, value):
        """Validate priority field"""
        valid_priorities = ['low', 'normal', 'high', 'critical']
        if value not in valid_priorities:
            raise serializers.ValidationError(f"Invalid priority: {value}")
        return value


class TaskExecutionSerializer(serializers.ModelSerializer):
    """Basic task execution serializer"""
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    schedule_uuid = serializers.UUIDField(source='schedule.uuid', read_only=True)
    runtime_minutes = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskExecution
        fields = [
            'uuid', 'schedule', 'schedule_name', 'schedule_uuid',
            'started_at', 'completed_at', 'runtime_seconds',
            'runtime_minutes', 'status', 'status_display',
            'result', 'error_message', 'error_traceback',
            'worker_id', 'process_id', 'memory_used_mb',
            'cpu_percent', 'retry_count', 'parent_execution',
            'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']
    
    def get_runtime_minutes(self, obj):
        """Convert runtime seconds to minutes"""
        if obj.runtime_seconds:
            return round(obj.runtime_seconds / 60, 1)
        return 0
    
    def get_status_display(self, obj):
        """Get status display"""
        status_map = {
            'pending': 'Pending',
            'running': 'Running',
            'success': 'Success',
            'failure': 'Failure',
            'timeout': 'Timeout',
            'cancelled': 'Cancelled',
            'retry': 'Retry'
        }
        return status_map.get(obj.status, obj.status.title())


class TaskExecutionDetailSerializer(serializers.ModelSerializer):
    """Detailed task execution serializer"""
    schedule_details = TaskScheduleDetailSerializer(source='schedule', read_only=True)
    parent_execution_details = TaskExecutionSerializer(source='parent_execution', read_only=True)
    
    class Meta:
        model = TaskExecution
        fields = [
            'uuid', 'schedule', 'schedule_details', 'parent_execution',
            'started_at', 'completed_at', 'runtime_seconds',
            'runtime_minutes', 'status', 'result', 'error_message',
            'error_traceback', 'worker_id', 'process_id',
            'memory_used_mb', 'cpu_percent', 'retry_count',
            'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']


class TaskQueueSerializer(serializers.ModelSerializer):
    """Basic task queue serializer"""
    priority_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskQueue
        fields = [
            'uuid', 'task_name', 'task_path', 'priority',
            'task_args', 'task_kwargs', 'queue_name', 'status',
            'queued_at', 'started_at', 'completed_at',
            'worker_id', 'execution_id', 'result', 'error_message',
            'max_retries', 'retry_count', 'next_retry_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_priority_display(self, obj):
        """Get priority display"""
        priority_map = {
            'low': 'Low',
            'normal': 'Normal',
            'high': 'High',
            'critical': 'Critical'
        }
        return priority_map.get(obj.priority, obj.priority.title())
    
    def get_status_display(self, obj):
        """Get status display"""
        status_map = {
            'queued': 'Queued',
            'processing': 'Processing',
            'completed': 'Completed',
            'failed': 'Failed',
            'cancelled': 'Cancelled'
        }
        return status_map.get(obj.status, obj.status.title())


class TaskQueueCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating queued tasks"""
    class Meta:
        model = TaskQueue
        fields = [
            'task_name', 'task_path', 'priority', 'task_args',
            'task_kwargs', 'queue_name', 'max_retries'
        ]


class TaskLockSerializer(serializers.ModelSerializer):
    """Basic task lock serializer"""
    is_expired = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskLock
        fields = [
            'uuid', 'lock_key', 'task_name', 'owner', 'acquired_at',
            'expires_at', 'is_expired', 'time_remaining', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_is_expired(self, obj):
        """Check if lock is expired"""
        return obj.is_expired()
    
    def get_time_remaining(self, obj):
        """Get time remaining until expiration"""
        from django.utils import timezone
        if obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                return remaining.total_seconds()
        return 0


class TaskLockDetailSerializer(serializers.ModelSerializer):
    """Detailed task lock serializer"""
    class Meta:
        model = TaskLock
        fields = [
            'uuid', 'lock_key', 'task_name', 'owner', 'acquired_at',
            'expires_at', 'is_expired', 'time_remaining', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class TaskManagementStatsSerializer(serializers.Serializer):
    """Task management statistics serializer"""
    overview = serializers.SerializerMethodField()
    schedules = serializers.SerializerMethodField()
    executions = serializers.SerializerMethodField()
    queues = serializers.SerializerMethodField()
    locks = serializers.SerializerMethodField()
    
    class Meta:
        fields = [
            'overview', 'schedules', 'executions', 'queues', 'locks'
        ]
    
    def get_overview(self, obj):
        """Get overview statistics"""
        return obj.get('overview', {})
    
    def get_schedules(self, obj):
        """Get schedule statistics"""
        return obj.get('schedules', {})
    
    def get_executions(self, obj):
        """Get execution statistics"""
        return obj.get('executions', {})
    
    def get_queues(self, obj):
        """Get queue statistics"""
        return obj.get('queues', {})
    
    def get_locks(self, obj):
        """Get lock statistics"""
        return obj.get('locks', {})
