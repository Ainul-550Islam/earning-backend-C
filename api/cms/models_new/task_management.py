# api/cms/models_new/task_management.py
"""
Task Management Models for Background Job Tracking and Scheduling
"""
import uuid
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class TaskSchedule(models.Model):
    """
    Scheduled task configuration and tracking
    """
    FREQUENCY_CHOICES = [
        ('once', _('Once')),
        ('minutely', _('Every Minute')),
        ('hourly', _('Hourly')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
        ('custom', _('Custom Cron')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('paused', _('Paused')),
        ('disabled', _('Disabled')),
        ('completed', _('Completed')),
    ]
    
    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Task Name"), max_length=200)
    description = models.TextField(_("Description"), blank=True)
    schedule_type     = models.CharField(max_length=20, default='interval')
    is_active         = models.BooleanField(default=True)
    task_path = models.CharField(_("Task Path"), max_length=500, help_text=_("Full path to the task function"))
    
    # Scheduling configuration
    frequency = models.CharField(_("Frequency"), max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    cron_expression = models.CharField(
        _("Cron Expression"), max_length=100, blank=True,
        help_text=_("Cron expression for custom frequency")
    )
    timezone = models.CharField(_("Timezone"), max_length=50, default='UTC')
    
    # Timing
    start_time = models.DateTimeField(_("Start Time"), null=True, blank=True)
    end_time = models.DateTimeField(_("End Time"), null=True, blank=True)
    next_run = models.DateTimeField(_("Next Run"), null=True, blank=True)
    last_run = models.DateTimeField(_("Last Run"), null=True, blank=True)
    
    # Status and priority
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(_("Priority"), max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Configuration
    task_args = models.JSONField(_("Task Arguments"), default=dict, blank=True)
    task_kwargs = models.JSONField(_("Task Keyword Arguments"), default=dict, blank=True)
    max_retries = models.PositiveIntegerField(_("Max Retries"), default=3)
    retry_delay = models.PositiveIntegerField(
        _("Retry Delay (seconds)"), default=300,
        help_text=_("Delay between retries in seconds")
    )
    
    # Resource limits
    timeout_seconds = models.PositiveIntegerField(
        _("Timeout (seconds)"), null=True, blank=True,
        help_text=_("Maximum execution time in seconds")
    )
    memory_limit_mb = models.PositiveIntegerField(
        _("Memory Limit (MB)"), null=True, blank=True
    )
    
    # Dependencies
    depends_on = models.ManyToManyField(
        'self', symmetrical=False, blank=True,
        related_name='dependent_tasks',
        help_text=_("Tasks that must complete before this task can run")
    )
    
    # Notifications
    notify_on_success = models.BooleanField(_("Notify on Success"), default=False)
    notify_on_failure = models.BooleanField(_("Notify on Failure"), default=True)
    notification_emails = models.JSONField(
        _("Notification Emails"), default=list, blank=True
    )
    
    # Statistics
    total_runs = models.PositiveIntegerField(_("Total Runs"), default=0)
    successful_runs = models.PositiveIntegerField(_("Successful Runs"), default=0)
    failed_runs = models.PositiveIntegerField(_("Failed Runs"), default=0)
    average_runtime = models.DecimalField(
        _("Average Runtime (seconds)"), max_digits=10, decimal_places=2, default=0
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_tasks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Task Schedule")
        verbose_name_plural = _("Task Schedules")
        indexes = [
            models.Index(fields=['status', 'next_run']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['frequency']),
            models.Index(fields=['next_run']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate task configuration."""
        if self.frequency == 'custom' and not self.cron_expression:
            raise ValidationError(_("Cron expression is required for custom frequency"))
        
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_("End time must be after start time"))
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency."""
        if not self.start_time:
            return None
        
        now = timezone.now()
        base_time = self.last_run or self.start_time
        
        if self.frequency == 'once':
            return base_time if base_time > now else None
        
        elif self.frequency == 'minutely':
            return base_time + timedelta(minutes=1)
        
        elif self.frequency == 'hourly':
            return base_time + timedelta(hours=1)
        
        elif self.frequency == 'daily':
            return base_time + timedelta(days=1)
        
        elif self.frequency == 'weekly':
            return base_time + timedelta(weeks=1)
        
        elif self.frequency == 'monthly':
            return base_time + timedelta(days=30)
        
        elif self.frequency == 'quarterly':
            return base_time + timedelta(days=90)
        
        elif self.frequency == 'yearly':
            return base_time + timedelta(days=365)
        
        elif self.frequency == 'custom':
            # Would need cron parser implementation
            # For now, return next day as placeholder
            return base_time + timedelta(days=1)
        
        return None
    
    def is_ready_to_run(self):
        """Check if task is ready to run."""
        if self.status != 'active':
            return False
        
        now = timezone.now()
        
        # Check start/end time constraints
        if self.start_time and now < self.start_time:
            return False
        
        if self.end_time and now > self.end_time:
            return False
        
        # Check next run time
        if self.next_run and now < self.next_run:
            return False
        
        # Check dependencies
        if self.depends_on.exists():
            for dependency in self.depends_on.all():
                if not dependency.is_completed_successfully():
                    return False
        
        return True
    
    def is_completed_successfully(self):
        """Check if task completed successfully on last run."""
        if not self.last_run:
            return False
        
        latest_execution = self.executions.order_by('-started_at').first()
        return latest_execution and latest_execution.status == 'success'
    
    def update_statistics(self, runtime_seconds=None, success=None):
        """Update task statistics."""
        self.total_runs += 1
        
        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1
        
        if runtime_seconds is not None:
            # Update average runtime
            if self.average_runtime == 0:
                self.average_runtime = Decimal(str(runtime_seconds))
            else:
                total_runtime = self.average_runtime * (self.total_runs - 1) + Decimal(str(runtime_seconds))
                self.average_runtime = total_runtime / self.total_runs
        
        self.last_run = timezone.now()
        self.next_run = self.calculate_next_run()
        self.save(update_fields=[
            'total_runs', 'successful_runs', 'failed_runs',
            'average_runtime', 'last_run', 'next_run'
        ])


class TaskExecution(models.Model):
    """
    Individual task execution records
    """
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('running', _('Running')),
        ('success', _('Success')),
        ('failure', _('Failure')),
        ('timeout', _('Timeout')),
        ('cancelled', _('Cancelled')),
        ('retry', _('Retry')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    schedule = models.ForeignKey(
        TaskSchedule, on_delete=models.CASCADE, related_name='executions'
    )
    
    # Timing
    started_at = models.DateTimeField(_("Started At"), auto_now_add=True)
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)
    runtime_seconds = models.DecimalField(
        _("Runtime (seconds)"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    
    # Status and result
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(_("Result"), default=dict, blank=True)
    error_message = models.TextField(_("Error Message"), blank=True)
    error_traceback = models.TextField(_("Error Traceback"), blank=True)
    
    # Execution details
    worker_id = models.CharField(_("Worker ID"), max_length=100, blank=True)
    process_id = models.PositiveIntegerField(_("Process ID"), null=True, blank=True)
    
    # Resources used
    memory_used_mb = models.DecimalField(
        _("Memory Used (MB)"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    cpu_percent = models.DecimalField(
        _("CPU Percent"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Retry information
    retry_count = models.PositiveIntegerField(_("Retry Count"), default=0)
    parent_execution = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='retry_executions'
    )
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Task Execution")
        verbose_name_plural = _("Task Executions")
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['schedule', 'status']),
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.schedule.name} - {self.get_status_display()} - {self.started_at}"
    
    def mark_completed(self, status='success', result=None, error_message=None, error_traceback=None):
        """Mark execution as completed."""
        self.status = status
        self.completed_at = timezone.now()
        
        if self.started_at:
            runtime = self.completed_at - self.started_at
            self.runtime_seconds = Decimal(str(runtime.total_seconds()))
        
        if result:
            self.result = result
        
        if error_message:
            self.error_message = error_message
        
        if error_traceback:
            self.error_traceback = error_traceback
        
        self.save()
        
        # Update schedule statistics
        success = status == 'success'
        self.schedule.update_statistics(
            runtime_seconds=float(self.runtime_seconds) if self.runtime_seconds else None,
            success=success
        )


class TaskQueue(models.Model):
    """
    Task queue management for background job processing
    """
    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    STATUS_CHOICES = [
        ('queued', _('Queued')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    task_name = models.CharField(_("Task Name"), max_length=200)
    schedule_type     = models.CharField(max_length=20, default='interval')
    is_active         = models.BooleanField(default=True)
    task_path = models.CharField(_("Task Path"), max_length=500)
    priority = models.CharField(_("Priority"), max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Task data
    task_args = models.JSONField(_("Task Arguments"), default=list, blank=True)
    task_kwargs = models.JSONField(_("Task Keyword Arguments"), default=dict, blank=True)
    
    # Queue management
    queue_name = models.CharField(_("Queue Name"), max_length=100, default='default')
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='queued')
    
    # Timing
    queued_at = models.DateTimeField(_("Queued At"), auto_now_add=True)
    started_at = models.DateTimeField(_("Started At"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)
    
    # Execution details
    worker_id = models.CharField(_("Worker ID"), max_length=100, blank=True)
    execution_id = models.CharField(_("Execution ID"), max_length=100, blank=True)
    
    # Result
    result = models.JSONField(_("Result"), default=dict, blank=True)
    error_message = models.TextField(_("Error Message"), blank=True)
    
    # Retry configuration
    max_retries = models.PositiveIntegerField(_("Max Retries"), default=3)
    retry_count = models.PositiveIntegerField(_("Retry Count"), default=0)
    next_retry_at = models.DateTimeField(_("Next Retry At"), null=True, blank=True)
    
    # Dependencies
    depends_on = models.ManyToManyField(
        'self', symmetrical=False, blank=True,
        related_name='dependent_tasks'
    )
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Task Queue")
        verbose_name_plural = _("Task Queue")
        ordering = ['priority', 'queued_at']
        indexes = [
            models.Index(fields=['status', 'priority', 'queued_at']),
            models.Index(fields=['queue_name', 'status']),
            models.Index(fields=['task_name']),
            models.Index(fields=['next_retry_at']),
        ]
    
    def __str__(self):
        return f"{self.task_name} ({self.get_status_display()})"
    
    def can_retry(self):
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status in ['failed', 'cancelled']
    
    def schedule_retry(self, delay_seconds=300):
        """Schedule a retry for this task."""
        if not self.can_retry():
            return False
        
        self.retry_count += 1
        self.status = 'queued'
        self.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
        self.save(update_fields=['retry_count', 'status', 'next_retry_at'])
        return True


class TaskLock(models.Model):
    """
    Task locking mechanism to prevent concurrent execution
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    lock_key = models.CharField(_("Lock Key"), max_length=200, unique=True)
    task_name = models.CharField(_("Task Name"), max_length=200)
    
    # Lock details
    owner = models.CharField(_("Owner"), max_length=100, blank=True)
    acquired_at = models.DateTimeField(_("Acquired At"), auto_now_add=True)
    expires_at = models.DateTimeField(_("Expires At"))
    
    # Metadata
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Task Lock")
        verbose_name_plural = _("Task Locks")
        indexes = [
            models.Index(fields=['lock_key']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['task_name']),
        ]
    
    def __str__(self):
        return f"{self.lock_key} ({self.owner})"
    
    @classmethod
    def acquire(cls, lock_key, owner=None, timeout_seconds=3600, metadata=None):
        """Acquire a task lock."""
        expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
        
        lock, created = cls.objects.get_or_create(
            lock_key=lock_key,
            defaults={
                'task_name': lock_key,
                'owner': owner or 'unknown',
                'expires_at': expires_at,
                'metadata': metadata or {}
            }
        )
        
        # Return None for lock on conflict (test expects None when created=False)
        return created, (lock if created else None)
    
    @classmethod
    def release(cls, lock_key, owner=None):
        """Release a task lock."""
        queryset = cls.objects.filter(lock_key=lock_key)
        if owner:
            queryset = queryset.filter(owner=owner)
        
        deleted_count = queryset.delete()[0]
        return deleted_count > 0
    
    @classmethod
    def cleanup_expired(cls):
        """Clean up expired locks."""
        expired_count = cls.objects.filter(expires_at__lt=timezone.now()).delete()[0]
        return expired_count
    
    def is_expired(self):
        """Check if lock has expired."""
        return timezone.now() > self.expires_at
    
    def extend(self, additional_seconds=3600):
        """Extend lock expiration."""
        self.expires_at = timezone.now() + timedelta(seconds=additional_seconds)
        self.save(update_fields=['expires_at'])
