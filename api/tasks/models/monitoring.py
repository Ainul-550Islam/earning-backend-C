"""
tasks/models/monitoring.py
Monitoring models: TaskMonitor, TaskAlert, TaskPerformanceLog, WorkerHealth, QueueDepth
"""
import logging
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TaskMonitor
# ─────────────────────────────────────────────

class TaskMonitor(models.Model):
    """
    Aggregated health snapshot for a specific task name.
    Updated periodically by TaskMonitorService.
    """

    class Status(models.TextChoices):
        HEALTHY   = 'healthy',   'Healthy'
        DEGRADED  = 'degraded',  'Degraded'
        FAILING   = 'failing',   'Failing'
        MISSING   = 'missing',   'Missing (no recent runs)'
        UNKNOWN   = 'unknown',   'Unknown'

    task_name   = models.CharField(max_length=255, unique=True, db_index=True)
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNKNOWN,
        db_index=True,
    )

    last_run_at    = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)

    # Rolling metrics (updated by TaskMonitorService)
    avg_duration_seconds  = models.FloatField(null=True, blank=True)
    p95_duration_seconds  = models.FloatField(null=True, blank=True)
    success_rate          = models.FloatField(
        null=True,
        blank=True,
        help_text="Success rate as a percentage (0–100)",
    )
    total_runs_last_24h   = models.PositiveIntegerField(default=0)
    total_failures_last_24h = models.PositiveIntegerField(default=0)

    # Alert suppression
    alert_silenced_until  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Monitor'
        verbose_name_plural = 'Task Monitors'
        ordering            = ['task_name']

    def __str__(self):
        return f"Monitor: {self.task_name} [{self.status}]"

    @property
    def alerts_suppressed(self) -> bool:
        if self.alert_silenced_until:
            return timezone.now() < self.alert_silenced_until
        return False

    def silence_alerts(self, minutes: int = 60) -> None:
        from datetime import timedelta
        self.alert_silenced_until = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=['alert_silenced_until', 'updated_at'])


# ─────────────────────────────────────────────
# TaskAlert
# ─────────────────────────────────────────────

class TaskAlert(models.Model):
    """
    Alert rules that fire when task health degrades.
    Evaluated by TaskAlertService.
    """

    class AlertType(models.TextChoices):
        FAILURE  = 'failure',  'Task Failure Rate'
        SLOW     = 'slow',     'Task Running Slow'
        MISSING  = 'missing',  'Task Not Running'
        DLQ      = 'dlq',      'Dead Letter Queue Growth'
        DEPTH    = 'depth',    'Queue Depth Exceeded'

    class Severity(models.TextChoices):
        INFO     = 'info',     'Info'
        WARNING  = 'warning',  'Warning'
        CRITICAL = 'critical', 'Critical'

    task_name  = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Task name this alert applies to. Use '*' for all tasks.",
    )
    alert_type = models.CharField(
        max_length=20,
        choices=AlertType.choices,
        db_index=True,
    )
    severity   = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING,
    )

    # Threshold – interpreted differently per alert_type:
    # failure  → failure_rate % (e.g. 10 = fire when >10% fail)
    # slow     → seconds (e.g. 60 = fire when avg_duration > 60s)
    # missing  → minutes since last run (e.g. 60 = fire if no run in 1 h)
    # dlq      → absolute DLQ size
    # depth    → absolute queue depth
    threshold = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Numeric threshold that triggers the alert",
    )

    is_active         = models.BooleanField(default=True, db_index=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count     = models.PositiveIntegerField(default=0)

    # Notification channels stored as JSON list of channel identifiers
    # e.g. ["email:admin@example.com", "slack:#ops-alerts", "webhook:https://..."]
    notification_channels = models.JSONField(default=list, blank=True)

    # Cooldown – don't fire again within this many minutes
    cooldown_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minimum minutes between consecutive firings",
    )

    description = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Alert'
        verbose_name_plural = 'Task Alerts'
        ordering            = ['task_name', 'alert_type']
        indexes = [
            models.Index(fields=['is_active', 'alert_type']),
        ]

    def __str__(self):
        return f"Alert: {self.task_name} [{self.alert_type}] threshold={self.threshold}"

    @property
    def is_in_cooldown(self) -> bool:
        if not self.last_triggered_at:
            return False
        from datetime import timedelta
        cooldown_end = self.last_triggered_at + timedelta(minutes=self.cooldown_minutes)
        return timezone.now() < cooldown_end

    def record_trigger(self) -> None:
        self.last_triggered_at  = timezone.now()
        self.trigger_count     += 1
        self.save(update_fields=['last_triggered_at', 'trigger_count', 'updated_at'])


# ─────────────────────────────────────────────
# TaskPerformanceLog
# ─────────────────────────────────────────────

class TaskPerformanceLog(models.Model):
    """
    Detailed log of each task execution: timing, result, errors.
    Used for analytics, SLA tracking, and debugging.
    """

    class Result(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILURE = 'failure', 'Failure'
        TIMEOUT = 'timeout', 'Timeout'
        RETRY   = 'retry',   'Retry'

    task_id   = models.CharField(max_length=255, db_index=True, help_text="Celery task UUID")
    task_name = models.CharField(max_length=255, db_index=True)
    queue     = models.CharField(max_length=100, blank=True, default='')
    worker    = models.CharField(max_length=255, blank=True, default='')

    # Timing
    started_at       = models.DateTimeField(null=True, blank=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    # Result
    result      = models.CharField(
        max_length=20,
        choices=Result.choices,
        db_index=True,
    )
    error       = models.TextField(blank=True, default='')
    retry_count = models.PositiveIntegerField(default=0)
    output      = models.JSONField(null=True, blank=True, help_text="Task return value")

    # Resource usage (populated from Celery signals if available)
    cpu_seconds  = models.FloatField(null=True, blank=True)
    memory_mb    = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = 'Task Performance Log'
        verbose_name_plural = 'Task Performance Logs'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['task_name', '-created_at']),
            models.Index(fields=['result', '-created_at']),
            models.Index(fields=['-duration_seconds']),
        ]

    def __str__(self):
        return f"PerfLog: {self.task_name} [{self.result}] {self.duration_seconds:.2f}s"


# ─────────────────────────────────────────────
# WorkerHealth
# ─────────────────────────────────────────────

class WorkerHealth(models.Model):
    """
    Heartbeat records from Celery workers.
    WorkerHealthService writes a record per heartbeat cycle.
    """

    class Status(models.TextChoices):
        ONLINE   = 'online',   'Online'
        OFFLINE  = 'offline',  'Offline'
        IDLE     = 'idle',     'Idle'
        BUSY     = 'busy',     'Busy'
        DEGRADED = 'degraded', 'Degraded'

    worker_id  = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Celery worker node name (e.g. celery@hostname)",
    )
    hostname   = models.CharField(max_length=255, db_index=True)
    status     = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONLINE,
        db_index=True,
    )

    # Which queues this worker consumes
    queue_names = models.JSONField(
        default=list,
        blank=True,
        help_text="List of queue names this worker listens on",
    )

    # Concurrency & load
    concurrency     = models.PositiveIntegerField(default=1)
    active_tasks    = models.PositiveIntegerField(default=0)
    processed_total = models.PositiveIntegerField(default=0)
    failed_total    = models.PositiveIntegerField(default=0)

    # Resource usage snapshots
    cpu_percent  = models.FloatField(null=True, blank=True)
    memory_mb    = models.FloatField(null=True, blank=True)

    # Heartbeat
    last_heartbeat = models.DateTimeField(default=timezone.now, db_index=True)

    # Celery version info
    celery_version = models.CharField(max_length=50, blank=True, default='')
    python_version = models.CharField(max_length=50, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Worker Health'
        verbose_name_plural = 'Worker Health Records'
        ordering            = ['-last_heartbeat']
        indexes = [
            models.Index(fields=['status', '-last_heartbeat']),
        ]

    def __str__(self):
        return f"Worker: {self.worker_id} [{self.status}]"

    @property
    def is_stale(self) -> bool:
        """True if the last heartbeat is older than 2 minutes."""
        from datetime import timedelta
        return (timezone.now() - self.last_heartbeat) > timedelta(minutes=2)

    @property
    def load_pct(self) -> float:
        if self.concurrency == 0:
            return 0.0
        return round(self.active_tasks / self.concurrency * 100, 1)

    def record_heartbeat(
        self,
        active_tasks: int = 0,
        cpu_percent: float = None,
        memory_mb: float = None,
    ) -> None:
        self.last_heartbeat = timezone.now()
        self.active_tasks   = active_tasks
        if cpu_percent is not None:
            self.cpu_percent = cpu_percent
        if memory_mb is not None:
            self.memory_mb = memory_mb
        self.status = self.Status.BUSY if active_tasks > 0 else self.Status.IDLE
        self.save(update_fields=[
            'last_heartbeat', 'active_tasks', 'cpu_percent',
            'memory_mb', 'status', 'updated_at',
        ])


# ─────────────────────────────────────────────
# QueueDepth
# ─────────────────────────────────────────────

class QueueDepth(models.Model):
    """
    Point-in-time snapshot of queue depth measurements.
    Collected by QueueDepthService on a schedule.
    """

    queue_name       = models.CharField(max_length=200, db_index=True)
    depth            = models.PositiveIntegerField(
        default=0,
        help_text="Number of messages waiting to be consumed",
    )
    processing_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of messages currently being processed",
    )
    failed_count     = models.PositiveIntegerField(
        default=0,
        help_text="Number of messages in failed/DLQ state",
    )
    consumer_count   = models.PositiveIntegerField(
        default=0,
        help_text="Number of active consumers on this queue",
    )
    checked_at       = models.DateTimeField(default=timezone.now, db_index=True)

    # Derived metrics stored for quick querying
    avg_wait_seconds  = models.FloatField(null=True, blank=True)
    oldest_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Queue Depth Snapshot'
        verbose_name_plural = 'Queue Depth Snapshots'
        ordering            = ['-checked_at']
        indexes = [
            models.Index(fields=['queue_name', '-checked_at']),
            models.Index(fields=['-depth']),
        ]

    def __str__(self):
        return (
            f"QueueDepth: {self.queue_name} "
            f"depth={self.depth} proc={self.processing_count} "
            f"@ {self.checked_at:%Y-%m-%d %H:%M}"
        )
