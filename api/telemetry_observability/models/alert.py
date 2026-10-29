"""
Alert model for Telemetry Observability.
"""
from django.db import models

from .base import BaseModel
from ..choices import AlertTypeChoices, AlertSeverityChoices, AlertStatusChoices
from ..validators import AlertNameValidator, ServiceNameValidator


class AlertManager(models.Manager):
    """
    Custom manager for Alert model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_type(self, alert_type):
        """Filter alerts by alert_type (metric, log, trace, health, custom)."""
        return self.filter(alert_type=alert_type)

    def by_severity(self, severity):
        """Filter alerts by severity (info, warning, error, critical)."""
        return self.filter(severity=severity)

    def by_status(self, alert_status):
        """Filter alerts by status (open, acknowledged, resolved, suppressed)."""
        return self.filter(status=alert_status)

    def by_service(self, service):
        """Filter alerts by service name."""
        return self.filter(service=service)

    def by_environment(self, environment):
        """Filter alerts by environment."""
        return self.filter(environment=environment)

    def open(self):
        """Return only open alerts."""
        return self.filter(status='open')

    def acknowledged(self):
        """Return only acknowledged alerts."""
        return self.filter(status='acknowledged')

    def resolved(self):
        """Return only resolved alerts."""
        return self.filter(status='resolved')

    def critical(self):
        """Return only critical-severity alerts."""
        return self.filter(severity='critical')

    def recent(self, hours=24):
        """Return alerts triggered within the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(triggered_at__gte=since)

    def search(self, query):
        """Case-insensitive search across name and message fields."""
        return self.filter(
            models.Q(name__icontains=query) | models.Q(message__icontains=query)
        )


class Alert(BaseModel):
    """
    Model representing an alert for observability.
    """

    name = models.CharField(max_length=255, validators=[AlertNameValidator()])
    alert_type = models.CharField(
        max_length=50,
        choices=AlertTypeChoices.choices,
        default=AlertTypeChoices.METRIC,
    )
    severity = models.CharField(
        max_length=50,
        choices=AlertSeverityChoices.choices,
        default=AlertSeverityChoices.WARNING,
    )
    status = models.CharField(
        max_length=50,
        choices=AlertStatusChoices.choices,
        default=AlertStatusChoices.OPEN,
    )
    condition = models.JSONField(default=dict)
    message = models.TextField()
    source = models.CharField(max_length=255, blank=True, default='')
    service = models.CharField(max_length=255, blank=True, default='', validators=[ServiceNameValidator()])
    environment = models.CharField(max_length=50, default='production')
    triggered_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.CharField(max_length=255, blank=True, default='')
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    # Attach custom manager — replaces default objects = models.Manager()
    objects = AlertManager()

    class Meta:
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['name'], name='alert_name_idx'),
            models.Index(fields=['alert_type'], name='alert_type_idx'),
            models.Index(fields=['severity'], name='alert_severity_idx'),
            models.Index(fields=['status'], name='alert_status_idx'),
            models.Index(fields=['source'], name='alert_source_idx'),
            models.Index(fields=['service'], name='alert_service_idx'),
            models.Index(fields=['triggered_at'], name='alert_triggered_at_idx'),
        ]

    def __str__(self):
        return f"{self.name} - {self.severity}"

    def acknowledge(self, user):
        """
        Acknowledge the alert.

        Args:
            user: User who acknowledged (string identifier or User object)
        """
        from django.utils import timezone
        self.status = AlertStatusChoices.ACKNOWLEDGED
        self.acknowledged_by = str(user)
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])

    def resolve(self):
        """
        Resolve the alert. Sets status='resolved' and records resolved_at timestamp.
        """
        from django.utils import timezone
        self.status = AlertStatusChoices.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
