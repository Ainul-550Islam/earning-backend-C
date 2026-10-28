"""
Log Entry model for Telemetry Observability.
"""
from django.db import models

from .base import BaseModel


class LogEntryManager(models.Manager):
    """
    Custom manager for LogEntry model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_level(self, level):
        """Filter log entries by log level (debug, info, warning, error, critical)."""
        return self.filter(level=level)

    def by_service(self, service):
        """Filter log entries by service name."""
        return self.filter(service=service)

    def by_environment(self, environment):
        """Filter log entries by environment."""
        return self.filter(environment=environment)

    def by_source(self, source):
        """Filter log entries by source."""
        return self.filter(source=source)

    def by_logger(self, logger_name):
        """Filter log entries by logger name."""
        return self.filter(logger_name=logger_name)

    def errors(self):
        """Return only error-level log entries."""
        return self.filter(level='error')

    def critical(self):
        """Return only critical-level log entries."""
        return self.filter(level='critical')

    def errors_and_critical(self):
        """Return error and critical level log entries combined."""
        return self.filter(level__in=['error', 'critical'])

    def recent(self, hours=24):
        """Return log entries from the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=since)

    def search(self, query):
        """Case-insensitive search in message field."""
        return self.filter(message__icontains=query)


class LogEntry(BaseModel):
    """
    Model representing a log entry for observability.
    """

    level = models.CharField(
        max_length=20,
        choices=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical'),
        ],
        default='info'
    )
    message = models.TextField()
    logger_name = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=255, blank=True)
    service = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=50, default='production')
    timestamp = models.DateTimeField(auto_now_add=True)
    stack_trace = models.TextField(blank=True)
    context = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    # Attach custom manager — replaces default objects = models.Manager()
    objects = LogEntryManager()

    class Meta:
        verbose_name = 'Log Entry'
        verbose_name_plural = 'Log Entries'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level']),
            models.Index(fields=['source']),
            models.Index(fields=['service']),
            models.Index(fields=['environment']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"[{self.level.upper()}] {self.message[:50]}"
