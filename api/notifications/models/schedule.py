# earning_backend/api/notifications/models/schedule.py
"""
Scheduling & queue models:
  - NotificationSchedule — individual scheduled notification
  - NotificationBatch    — batch send job linked to a template + segment
  - NotificationQueue    — priority queue entry for pending sends
  - NotificationRetry    — retry record for failed delivery attempts
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ---------------------------------------------------------------------------
# NotificationSchedule
# ---------------------------------------------------------------------------

class NotificationSchedule(models.Model):
    """
    Schedules a single Notification to be sent at a specific future time,
    optionally in a given timezone.
    """

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    )

    notification = models.OneToOneField(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='schedule',
    )

    send_at = models.DateTimeField(
        help_text='UTC datetime when the notification should be dispatched',
    )

    # Store the original timezone string so the UI can display the
    # send-time in the user's local timezone.
    timezone = models.CharField(
        max_length=64,
        default='UTC',
        help_text='IANA timezone name, e.g. "Asia/Dhaka"',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )

    sent_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    # Who created this schedule (admin / system / user)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_schedules',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Notification Schedule'
        verbose_name_plural = 'Notification Schedules'
        ordering = ['send_at']
        indexes = [
            models.Index(fields=['status', 'send_at']),
            models.Index(fields=['send_at']),
        ]

    def __str__(self):
        return f"Schedule #{self.pk} — send at {self.send_at} [{self.status}]"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_due(self):
        """Return True if the schedule time has been reached."""
        return timezone.now() >= self.send_at and self.status == 'pending'

    def is_overdue(self, grace_minutes=5):
        """Return True if the schedule is past the grace window."""
        from datetime import timedelta
        return timezone.now() > self.send_at + timedelta(minutes=grace_minutes)

    def mark_sent(self, save=True):
        self.status = 'sent'
        self.sent_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'sent_at', 'updated_at'])

    def mark_failed(self, reason='', save=True):
        self.status = 'failed'
        self.failure_reason = reason
        if save:
            self.save(update_fields=['status', 'failure_reason', 'updated_at'])

    def cancel(self, save=True):
        if self.status in ('pending', 'processing'):
            self.status = 'cancelled'
            if save:
                self.save(update_fields=['status', 'updated_at'])
            return True
        return False


# ---------------------------------------------------------------------------
# NotificationBatch
# ---------------------------------------------------------------------------

class NotificationBatch(models.Model):
    """
    Represents a bulk-send job that sends a template to a segment of users.
    Tracks overall progress across potentially thousands of sends.
    """

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('partially_failed', 'Partially Failed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    template = models.ForeignKey(
        'notifications.NotificationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batches',
    )

    # Optional link to a campaign segment (populated when created from a
    # CampaignSegment; may be null for ad-hoc batches).
    segment = models.ForeignKey(
        'notifications.CampaignSegment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batches',
    )

    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
    )

    # Progress counters
    total_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    # Extra context / template variables for the entire batch
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Template context variables applied to every notification in the batch',
    )

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Celery task ID for monitoring
    celery_task_id = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_batches',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Notification Batch'
        verbose_name_plural = 'Notification Batches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Batch '{self.name or self.pk}' — {self.status} ({self.sent_count}/{self.total_count})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def progress_pct(self):
        if self.total_count == 0:
            return 0
        return round((self.sent_count + self.failed_count + self.skipped_count) / self.total_count * 100, 2)

    @property
    def success_rate(self):
        if self.total_count == 0:
            return 0
        return round(self.sent_count / self.total_count * 100, 2)

    def start(self, save=True):
        self.status = 'processing'
        self.started_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'started_at', 'updated_at'])

    def complete(self, save=True):
        self.status = 'completed' if self.failed_count == 0 else 'partially_failed'
        self.completed_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def increment_sent(self, save=True):
        self.sent_count += 1
        if save:
            self.save(update_fields=['sent_count', 'updated_at'])

    def increment_failed(self, save=True):
        self.failed_count += 1
        if save:
            self.save(update_fields=['failed_count', 'updated_at'])

    def increment_skipped(self, save=True):
        self.skipped_count += 1
        if save:
            self.save(update_fields=['skipped_count', 'updated_at'])


# ---------------------------------------------------------------------------
# NotificationQueue
# ---------------------------------------------------------------------------

class NotificationQueue(models.Model):
    """
    An in-database priority queue entry for a notification waiting to be sent.
    The Celery task polls this table for items to process.
    """

    PRIORITY_CHOICES = [(i, str(i)) for i in range(1, 11)]  # 1 (lowest) – 10 (highest)

    STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    notification = models.OneToOneField(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='queue_entry',
    )

    priority = models.PositiveSmallIntegerField(
        default=5,
        choices=PRIORITY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text='1 = lowest priority, 10 = highest',
    )

    scheduled_at = models.DateTimeField(
        default=timezone.now,
        help_text='Earliest time this item should be processed',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='waiting',
        db_index=True,
    )

    # Attempt tracking
    attempts = models.PositiveSmallIntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)

    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Notification Queue Entry'
        verbose_name_plural = 'Notification Queue Entries'
        ordering = ['-priority', 'scheduled_at']
        indexes = [
            models.Index(fields=['status', '-priority', 'scheduled_at']),
            models.Index(fields=['scheduled_at']),
        ]

    def __str__(self):
        return f"Queue #{self.pk} — priority {self.priority} [{self.status}]"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_ready(self):
        """Return True if the entry is waiting and its scheduled time has passed."""
        return self.status == 'waiting' and timezone.now() >= self.scheduled_at

    def increment_attempt(self, save=True):
        self.attempts += 1
        self.last_attempt = timezone.now()
        if save:
            self.save(update_fields=['attempts', 'last_attempt', 'updated_at'])

    def mark_processing(self, task_id='', save=True):
        self.status = 'processing'
        if task_id:
            self.celery_task_id = task_id
        if save:
            self.save(update_fields=['status', 'celery_task_id', 'updated_at'])

    def mark_done(self, save=True):
        self.status = 'done'
        if save:
            self.save(update_fields=['status', 'updated_at'])

    def mark_failed(self, save=True):
        self.status = 'failed'
        if save:
            self.save(update_fields=['status', 'updated_at'])


# ---------------------------------------------------------------------------
# NotificationRetry
# ---------------------------------------------------------------------------

class NotificationRetry(models.Model):
    """
    Tracks individual retry attempts for a failed notification delivery.
    Each record represents one scheduled retry with its own outcome.
    """

    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    )

    notification = models.ForeignKey(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='retry_attempts',
    )

    attempt_number = models.PositiveSmallIntegerField(
        default=1,
        help_text='1-based retry attempt number',
    )

    max_attempts = models.PositiveSmallIntegerField(
        default=3,
        help_text='Maximum number of retry attempts before abandoning',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        db_index=True,
    )

    # Error from the previous failed attempt that triggered this retry
    error_from_previous = models.TextField(blank=True)

    # Error from this attempt (populated on failure)
    error = models.TextField(blank=True)

    # When this retry is scheduled to run
    retry_at = models.DateTimeField(default=timezone.now)

    # When this retry actually ran
    attempted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Notification Retry'
        verbose_name_plural = 'Notification Retries'
        ordering = ['notification', 'attempt_number']
        unique_together = [['notification', 'attempt_number']]
        indexes = [
            models.Index(fields=['status', 'retry_at']),
            models.Index(fields=['retry_at']),
        ]

    def __str__(self):
        return (
            f"Retry #{self.attempt_number}/{self.max_attempts} "
            f"for Notification #{self.notification_id} [{self.status}]"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_due(self):
        return self.status == 'scheduled' and timezone.now() >= self.retry_at

    def has_exceeded_max(self):
        return self.attempt_number >= self.max_attempts

    def mark_succeeded(self, save=True):
        self.status = 'succeeded'
        self.attempted_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'attempted_at', 'updated_at'])

    def mark_failed(self, error='', save=True):
        self.status = 'failed'
        self.error = error
        self.attempted_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'error', 'attempted_at', 'updated_at'])

    def mark_abandoned(self, save=True):
        self.status = 'abandoned'
        if save:
            self.save(update_fields=['status', 'updated_at'])
