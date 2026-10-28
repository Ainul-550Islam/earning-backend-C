"""
tasks/models/core.py
Core task models: TaskResult and ScheduledTask
These support Celery result tracking and cron-style scheduling.
"""
import logging
import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

User = get_user_model()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TaskResult  –  stores Celery task execution results
# ─────────────────────────────────────────────

class TaskResult(models.Model):
    """
    Persists Celery task execution results so they can be
    inspected from the admin or API without keeping the
    Celery result backend entries indefinitely.
    """

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        STARTED   = 'started',   'Started'
        SUCCESS   = 'success',   'Success'
        FAILURE   = 'failure',   'Failure'
        RETRY     = 'retry',     'Retry'
        REVOKED   = 'revoked',   'Revoked'

    # ── Identity ──────────────────────────────
    task_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Celery task UUID",
    )
    task_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Dotted Python path of the Celery task function",
    )

    # ── Timing ────────────────────────────────
    date_created  = models.DateTimeField(auto_now_add=True, db_index=True)
    date_started  = models.DateTimeField(null=True, blank=True)
    date_done     = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Wall-clock seconds from started to done",
    )

    # ── Result ────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    result    = models.JSONField(null=True, blank=True, help_text="Return value of the task")
    traceback = models.TextField(blank=True, default='', help_text="Exception traceback on failure")
    meta      = models.JSONField(default=dict, blank=True, help_text="Extra metadata (retries, ETA, etc.)")

    # ── Routing ───────────────────────────────
    worker      = models.CharField(max_length=255, blank=True, default='')
    queue       = models.CharField(max_length=100, blank=True, default='')
    retry_count = models.PositiveIntegerField(default=0)

    # ── Tenant / User (optional) ──────────────
    triggered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='triggered_task_results',
    )

    class Meta:
        verbose_name        = 'Task Result'
        verbose_name_plural = 'Task Results'
        ordering            = ['-date_created']
        indexes = [
            models.Index(fields=['task_name', 'status']),
            models.Index(fields=['-date_created']),
            models.Index(fields=['status', '-date_created']),
        ]

    def __str__(self):
        return f"{self.task_name} [{self.status}] – {self.task_id}"

    # ── Helpers ───────────────────────────────

    def mark_started(self, worker: str = '', queue: str = '') -> None:
        """Called when the worker picks up the task."""
        self.status       = self.Status.STARTED
        self.date_started = timezone.now()
        self.worker       = worker
        self.queue        = queue
        self.save(update_fields=['status', 'date_started', 'worker', 'queue'])

    def mark_success(self, result=None) -> None:
        """Called on successful completion."""
        now = timezone.now()
        self.status   = self.Status.SUCCESS
        self.date_done = now
        self.result   = result
        if self.date_started:
            self.duration_seconds = (now - self.date_started).total_seconds()
        self.save(update_fields=['status', 'date_done', 'result', 'duration_seconds'])

    def mark_failure(self, traceback: str = '', result=None) -> None:
        """Called on task failure."""
        now = timezone.now()
        self.status    = self.Status.FAILURE
        self.date_done = now
        self.traceback = traceback or ''
        self.result    = result
        if self.date_started:
            self.duration_seconds = (now - self.date_started).total_seconds()
        self.save(update_fields=['status', 'date_done', 'traceback', 'result', 'duration_seconds'])

    def mark_retry(self, retry_count: int) -> None:
        """Called when the task is being retried."""
        self.status      = self.Status.RETRY
        self.retry_count = retry_count
        self.save(update_fields=['status', 'retry_count'])

    @property
    def is_terminal(self) -> bool:
        """True if the task has reached a final state."""
        return self.status in {self.Status.SUCCESS, self.Status.FAILURE, self.Status.REVOKED}

    @property
    def failed(self) -> bool:
        return self.status == self.Status.FAILURE

    @property
    def succeeded(self) -> bool:
        return self.status == self.Status.SUCCESS


# ─────────────────────────────────────────────
# ScheduledTask  –  cron / periodic task registry
# ─────────────────────────────────────────────

class ScheduledTask(models.Model):
    """
    Human-friendly registry of Celery Beat periodic tasks.
    Admins can pause/resume tasks, change schedules, or
    trigger them on-demand without touching celery_beat tables.
    """

    class ScheduleType(models.TextChoices):
        CRON     = 'cron',     'Cron Expression'
        INTERVAL = 'interval', 'Fixed Interval'
        SOLAR    = 'solar',    'Solar Event'
        CLOCKED  = 'clocked',  'One-Time (Clocked)'

    class Priority(models.TextChoices):
        LOW      = 'low',      'Low'
        NORMAL   = 'normal',   'Normal'
        HIGH     = 'high',     'High'
        CRITICAL = 'critical', 'Critical'

    # ── Identity ──────────────────────────────
    name = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Human-readable name (e.g. 'Daily Revenue Rollup')",
    )
    task_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Dotted Python path to the Celery task (e.g. 'tasks.analytics_tasks.daily_revenue_rollup')",
    )
    description = models.TextField(blank=True, default='')

    # ── Schedule ──────────────────────────────
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.CRON,
    )
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Standard 5-field cron (minute hour day month weekday). Required for CRON type.",
    )
    interval_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Interval in seconds. Required for INTERVAL type.",
    )
    one_time_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Exact datetime for one-time CLOCKED tasks.",
    )

    # ── Task Arguments ────────────────────────
    task_args   = models.JSONField(default=list, blank=True, help_text="Positional args passed to the task")
    task_kwargs = models.JSONField(default=dict, blank=True, help_text="Keyword args passed to the task")

    # ── Routing ───────────────────────────────
    queue    = models.CharField(max_length=100, blank=True, default='default')
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    routing_key = models.CharField(max_length=200, blank=True, default='')

    # ── Control ───────────────────────────────
    is_active  = models.BooleanField(default=True, db_index=True)
    is_paused  = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Stop running after this datetime")

    # ── Execution limits ──────────────────────
    max_retries     = models.PositiveIntegerField(default=3)
    timeout_seconds = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(1), MaxValueValidator(86400)],
    )
    soft_time_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Soft time limit in seconds (sends SIGTERM before SIGKILL)",
    )

    # ── Stats ─────────────────────────────────
    last_run_at      = models.DateTimeField(null=True, blank=True)
    last_run_status  = models.CharField(max_length=20, blank=True, default='')
    total_runs       = models.PositiveIntegerField(default=0)
    total_failures   = models.PositiveIntegerField(default=0)
    avg_duration_sec = models.FloatField(null=True, blank=True)
    next_run_at      = models.DateTimeField(null=True, blank=True)

    # ── Audit ─────────────────────────────────
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_scheduled_tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Scheduled Task'
        verbose_name_plural = 'Scheduled Tasks'
        ordering            = ['name']
        indexes = [
            models.Index(fields=['is_active', 'is_paused']),
            models.Index(fields=['task_name']),
            models.Index(fields=['next_run_at']),
        ]

    def __str__(self):
        status = 'paused' if self.is_paused else ('active' if self.is_active else 'inactive')
        return f"{self.name} [{status}]"

    # ── Validation ────────────────────────────

    def clean(self):
        if self.schedule_type == self.ScheduleType.CRON and not self.cron_expression:
            raise ValidationError({'cron_expression': 'Required for CRON schedule type.'})
        if self.schedule_type == self.ScheduleType.INTERVAL and not self.interval_seconds:
            raise ValidationError({'interval_seconds': 'Required for INTERVAL schedule type.'})
        if self.schedule_type == self.ScheduleType.CLOCKED and not self.one_time_at:
            raise ValidationError({'one_time_at': 'Required for CLOCKED schedule type.'})

    # ── Helpers ───────────────────────────────

    def pause(self) -> None:
        """Pause execution without deactivating."""
        self.is_paused = True
        self.save(update_fields=['is_paused', 'updated_at'])
        logger.info(f"ScheduledTask '{self.name}' paused.")

    def resume(self) -> None:
        """Resume a paused task."""
        self.is_paused = False
        self.save(update_fields=['is_paused', 'updated_at'])
        logger.info(f"ScheduledTask '{self.name}' resumed.")

    def deactivate(self) -> None:
        """Fully deactivate the task."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    def record_run(self, status: str, duration_sec: float = 0.0) -> None:
        """Update stats after each execution."""
        self.last_run_at     = timezone.now()
        self.last_run_status = status
        self.total_runs     += 1
        if status == 'failure':
            self.total_failures += 1

        # Rolling average duration
        if self.avg_duration_sec is None:
            self.avg_duration_sec = duration_sec
        else:
            self.avg_duration_sec = (
                (self.avg_duration_sec * (self.total_runs - 1) + duration_sec)
                / self.total_runs
            )

        self.save(update_fields=[
            'last_run_at', 'last_run_status', 'total_runs',
            'total_failures', 'avg_duration_sec',
        ])

    @property
    def is_running(self) -> bool:
        return self.is_active and not self.is_paused

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return round((self.total_runs - self.total_failures) / self.total_runs * 100, 2)

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
