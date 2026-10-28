"""
NEW FILE — Notification preferences.

Implements Missing Component #8 (Notifications): previously there was no
way for a user to be told a flag they care about changed state, or that
an experiment reached statistical significance.
"""
from django.conf import settings
from django.db import models

from .base import BaseModel


class NotificationPreference(BaseModel):
    """Per-user opt-in settings for which flag/experiment events to be notified about."""

    class Event(models.TextChoices):
        FLAG_ACTIVATED = 'flag_activated', 'Flag Activated'
        FLAG_PAUSED = 'flag_paused', 'Flag Paused'
        FLAG_ARCHIVED = 'flag_archived', 'Flag Archived'
        EXPERIMENT_STARTED = 'experiment_started', 'Experiment Started'
        EXPERIMENT_COMPLETED = 'experiment_completed', 'Experiment Completed'
        SIGNIFICANCE_REACHED = 'significance_reached', 'Statistical Significance Reached'
        CHANGE_REQUESTED = 'change_requested', 'Flag Change Requested'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preference')
    events = models.JSONField(default=list, help_text='List of Event values this user wants notified about.')

    notify_email = models.BooleanField(default=True)
    notify_slack = models.BooleanField(default=False)
    slack_webhook_url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f"NotificationPreference({self.user})"

    def wants(self, event: str) -> bool:
        return event in (self.events or [])
