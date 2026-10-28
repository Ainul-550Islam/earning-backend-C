"""
NEW FILE — Scheduled flag changes.

Implements Missing Component #9 (Scheduling): previously a flag could
only be activated/paused by a human action at the exact desired moment
(e.g. a midnight launch required someone to be awake to click a button).
"""
from django.conf import settings
from django.db import models

from .base import BaseModel
from .feature_flag import FeatureFlag


class ScheduledChange(BaseModel):
    """A flag change to be applied automatically at a future time
    (see tasks.execute_scheduled_changes, which runs every minute)."""

    class ChangeType(models.TextChoices):
        ACTIVATE = 'activate', 'Activate'
        PAUSE = 'pause', 'Pause'
        ARCHIVE = 'archive', 'Archive'

    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='scheduled_changes')
    change_type = models.CharField(max_length=20, choices=ChangeType.choices)
    scheduled_for = models.DateTimeField(db_index=True)

    # Optional: also change rollout percentage at the same time (e.g.
    # gradual ramp steps).
    target_rollout_percentage = models.IntegerField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Scheduled Change'
        verbose_name_plural = 'Scheduled Changes'
        ordering = ['scheduled_for']
        indexes = [
            models.Index(fields=['scheduled_for', 'executed'], name='schedchange_due_idx'),
        ]

    def __str__(self):
        return f"{self.change_type} {self.flag.name} @ {self.scheduled_for}"
