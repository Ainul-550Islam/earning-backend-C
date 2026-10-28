"""
tasks/models/queue.py
Queue management models: TaskQueue, TaskPriority, TaskDeadLetterQueue, TaskRetryConfig
"""
import logging
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TaskQueue  –  represents a Celery queue
# ─────────────────────────────────────────────

class TaskQueue(models.Model):
    """
    Registry of Celery queues with metadata about capacity and priority.
    Does NOT replace Celery broker queues; it is a shadow record for
    admin visibility, alerting, and depth monitoring.
    """

    name = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Celery queue name (must match broker configuration)",
    )
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)

    # Concurrency limit enforced by the worker pool consuming this queue
    max_concurrency = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(256)],
        help_text="Maximum concurrent tasks on this queue",
    )

    # 1 = lowest priority, 10 = highest
    priority_level = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Queue routing priority (1-10). Higher = processed first.",
    )

    # Optional broker-specific routing key
    routing_key = models.CharField(max_length=200, blank=True, default='')

    # Depth thresholds for alerting
    alert_depth_warning  = models.PositiveIntegerField(
        default=100,
        help_text="Trigger a warning alert when depth exceeds this value",
    )
    alert_depth_critical = models.PositiveIntegerField(
        default=500,
        help_text="Trigger a critical alert when depth exceeds this value",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Queue'
        verbose_name_plural = 'Task Queues'
        ordering            = ['-priority_level', 'name']
        indexes = [
            models.Index(fields=['is_active', '-priority_level']),
        ]

    def __str__(self):
        active = 'active' if self.is_active else 'inactive'
        return f"{self.name} [P{self.priority_level}] [{active}]"

    def clean(self):
        if self.alert_depth_critical <= self.alert_depth_warning:
            raise ValidationError(
                'alert_depth_critical must be greater than alert_depth_warning.'
            )


# ─────────────────────────────────────────────
# TaskPriority  –  per-task priority settings within a queue
# ─────────────────────────────────────────────

class TaskPriority(models.Model):
    """
    Per-task priority configuration within a TaskQueue.
    Allows fine-grained control over which tasks get executed first
    when the queue is under load.
    """

    task_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Dotted Python path to the Celery task function",
    )
    queue = models.ForeignKey(
        TaskQueue,
        on_delete=models.CASCADE,
        related_name='task_priorities',
        help_text="Queue where this task runs",
    )

    # Broker-level priority (0–9 for RabbitMQ, 0–255 for Redis with priority queues)
    priority = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Task-level priority within the queue (1=low, 10=high)",
    )

    # Per-task execution timeout override
    timeout_seconds = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(1), MaxValueValidator(86400)],
        help_text="Max seconds allowed for a single execution. Overrides queue default.",
    )

    # Soft limit (SIGTERM before SIGKILL)
    soft_time_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Soft time limit in seconds",
    )

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Priority'
        verbose_name_plural = 'Task Priorities'
        unique_together     = [('task_name', 'queue')]
        ordering            = ['-priority', 'task_name']

    def __str__(self):
        return f"{self.task_name} → {self.queue.name} [P{self.priority}]"


# ─────────────────────────────────────────────
# TaskDeadLetterQueue  –  failed task storage
# ─────────────────────────────────────────────

class TaskDeadLetterQueue(models.Model):
    """
    Dead-letter storage for tasks that exceeded max retries or
    encountered unrecoverable errors. Supports manual retry and audit.
    """

    class FailureReason(models.TextChoices):
        EXCEPTION        = 'exception',        'Unhandled Exception'
        TIMEOUT          = 'timeout',          'Task Timeout'
        MAX_RETRIES      = 'max_retries',      'Max Retries Exceeded'
        WORKER_LOST      = 'worker_lost',      'Worker Process Lost'
        REVOKED          = 'revoked',          'Task Revoked'
        DESERIALIZATION  = 'deserialization',  'Payload Deserialization Error'
        UNKNOWN          = 'unknown',          'Unknown'

    class ReprocessStatus(models.TextChoices):
        PENDING    = 'pending',    'Pending Review'
        REQUEUED   = 'requeued',   'Requeued for Retry'
        RESOLVED   = 'resolved',   'Manually Resolved'
        DISCARDED  = 'discarded',  'Discarded'

    # ── Identity ──────────────────────────────
    task_name = models.CharField(max_length=255, db_index=True)
    task_id   = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Original Celery task UUID",
    )
    queue_name = models.CharField(max_length=200, blank=True, default='')

    # ── Error Details ─────────────────────────
    error          = models.TextField(help_text="Exception message or error summary")
    traceback      = models.TextField(blank=True, default='')
    failure_reason = models.CharField(
        max_length=30,
        choices=FailureReason.choices,
        default=FailureReason.UNKNOWN,
        db_index=True,
    )

    # ── Payload ───────────────────────────────
    payload      = models.JSONField(default=dict, blank=True, help_text="Task args/kwargs at time of failure")
    task_headers = models.JSONField(default=dict, blank=True, help_text="Celery message headers")

    # ── Timing ────────────────────────────────
    failed_at   = models.DateTimeField(default=timezone.now, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)

    # ── Reprocessing ──────────────────────────
    reprocess_status = models.CharField(
        max_length=20,
        choices=ReprocessStatus.choices,
        default=ReprocessStatus.PENDING,
        db_index=True,
    )
    reprocess_notes   = models.TextField(blank=True, default='')
    reprocessed_at    = models.DateTimeField(null=True, blank=True)
    new_task_id       = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Celery task ID of the requeued task",
    )

    # ── Worker Context ────────────────────────
    worker_hostname = models.CharField(max_length=255, blank=True, default='')

    # ── Timestamps ────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Dead Letter Queue Entry'
        verbose_name_plural = 'Dead Letter Queue Entries'
        ordering            = ['-failed_at']
        indexes = [
            models.Index(fields=['task_name', '-failed_at']),
            models.Index(fields=['reprocess_status', '-failed_at']),
            models.Index(fields=['failure_reason']),
        ]

    def __str__(self):
        return f"DLQ: {self.task_name} [{self.failure_reason}] @ {self.failed_at:%Y-%m-%d %H:%M}"

    # ── Helpers ───────────────────────────────

    def mark_requeued(self, new_task_id: str = '', notes: str = '') -> None:
        self.reprocess_status = self.ReprocessStatus.REQUEUED
        self.reprocessed_at   = timezone.now()
        self.new_task_id      = new_task_id
        self.reprocess_notes  = notes
        self.save(update_fields=[
            'reprocess_status', 'reprocessed_at', 'new_task_id',
            'reprocess_notes', 'updated_at',
        ])

    def mark_discarded(self, notes: str = '') -> None:
        self.reprocess_status = self.ReprocessStatus.DISCARDED
        self.reprocess_notes  = notes
        self.save(update_fields=['reprocess_status', 'reprocess_notes', 'updated_at'])

    def mark_resolved(self, notes: str = '') -> None:
        self.reprocess_status = self.ReprocessStatus.RESOLVED
        self.reprocess_notes  = notes
        self.save(update_fields=['reprocess_status', 'reprocess_notes', 'updated_at'])

    @property
    def is_pending(self) -> bool:
        return self.reprocess_status == self.ReprocessStatus.PENDING


# ─────────────────────────────────────────────
# TaskRetryConfig  –  retry policy per task
# ─────────────────────────────────────────────

class TaskRetryConfig(models.Model):
    """
    Configures the retry policy for a specific Celery task.
    RetryService reads this model to decide how to re-enqueue
    failed tasks (linear vs. exponential backoff).
    """

    class BackoffStrategy(models.TextChoices):
        LINEAR      = 'linear',      'Linear Backoff'
        EXPONENTIAL = 'exponential', 'Exponential Backoff'
        FIBONACCI   = 'fibonacci',   'Fibonacci Backoff'
        CONSTANT    = 'constant',    'Constant Delay'

    # ── Identity ──────────────────────────────
    task_name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Dotted Python path to the Celery task function",
    )
    description = models.TextField(blank=True, default='')

    # ── Retry Limits ──────────────────────────
    max_retries = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Maximum number of retry attempts before DLQ",
    )
    max_retry_delay_seconds = models.PositiveIntegerField(
        default=3600,
        help_text="Cap on computed backoff delay (seconds). Prevents unbounded waits.",
    )

    # ── Backoff ───────────────────────────────
    retry_backoff = models.CharField(
        max_length=20,
        choices=BackoffStrategy.choices,
        default=BackoffStrategy.EXPONENTIAL,
    )
    retry_delay_seconds = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Base delay in seconds for the first retry",
    )
    backoff_multiplier = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(1.0)],
        help_text="Multiplier applied each retry for EXPONENTIAL / LINEAR strategies",
    )
    jitter = models.BooleanField(
        default=True,
        help_text="Add random jitter (±25%) to avoid thundering herd",
    )

    # ── Retry Conditions ──────────────────────
    retry_on_exceptions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of exception class names to retry on. Empty = retry on all exceptions.",
    )
    ignore_exceptions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of exception class names that should NOT be retried (go straight to DLQ).",
    )

    # ── DLQ Behaviour ─────────────────────────
    send_to_dlq_on_exhaustion = models.BooleanField(
        default=True,
        help_text="Move task to DeadLetterQueue when max_retries is reached",
    )

    # ── Status ────────────────────────────────
    is_active  = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Retry Config'
        verbose_name_plural = 'Task Retry Configs'
        ordering            = ['task_name']

    def __str__(self):
        return (
            f"{self.task_name} – {self.get_retry_backoff_display()} "
            f"max={self.max_retries} base={self.retry_delay_seconds}s"
        )

    # ── Helpers ───────────────────────────────

    def compute_delay(self, attempt: int) -> float:
        """
        Return the backoff delay in seconds for a given attempt number (1-indexed).
        Applies jitter if enabled.
        """
        import random
        import math

        base = float(self.retry_delay_seconds)

        if self.retry_backoff == self.BackoffStrategy.CONSTANT:
            delay = base
        elif self.retry_backoff == self.BackoffStrategy.LINEAR:
            delay = base * attempt * self.backoff_multiplier
        elif self.retry_backoff == self.BackoffStrategy.FIBONACCI:
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            delay = base * a
        else:  # EXPONENTIAL (default)
            delay = base * (self.backoff_multiplier ** (attempt - 1))

        # Apply cap
        delay = min(delay, float(self.max_retry_delay_seconds))

        # Apply jitter ±25%
        if self.jitter:
            jitter_factor = 1.0 + random.uniform(-0.25, 0.25)
            delay = delay * jitter_factor

        return round(max(delay, 1.0), 2)
