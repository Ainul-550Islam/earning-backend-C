"""
Health Status model for Telemetry Observability.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .base import BaseModel


class HealthStatusManager(models.Manager):
    """
    Custom manager for HealthStatus model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_service(self, service_name):
        """Return health records for a specific service."""
        return self.filter(service_name=service_name)

    def by_component(self, component_name):
        """Return health records for a specific component."""
        return self.filter(component_name=component_name)

    def by_status(self, health_status):
        """Filter by health status (healthy, degraded, unhealthy, unknown)."""
        return self.filter(status=health_status)

    def by_environment(self, environment):
        """Filter health records by environment."""
        return self.filter(environment=environment)

    def healthy(self):
        """Return only healthy services."""
        return self.filter(status='healthy')

    def degraded(self):
        """Return only degraded services."""
        return self.filter(status='degraded')

    def unhealthy(self):
        """Return services in degraded or unhealthy state."""
        return self.filter(status__in=['degraded', 'unhealthy'])

    def critical(self):
        """Return services with unhealthy status AND health_score below 50."""
        return self.filter(status='unhealthy', health_score__lt=50)

    def recent(self, hours=24):
        """Return health records checked within the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(last_check__gte=since)

    def above_score(self, min_score):
        """Return services with health_score at or above min_score."""
        return self.filter(health_score__gte=min_score)

    def below_score(self, max_score):
        """Return services with health_score at or below max_score."""
        return self.filter(health_score__lte=max_score)


class HealthStatus(BaseModel):
    """
    Model representing the health status of a service or component.
    """

    service_name = models.CharField(max_length=255)
    component_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('unhealthy', 'Unhealthy'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    health_score = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    last_check = models.DateTimeField(auto_now=True)
    uptime = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    response_time_ms = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    error_rate = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    metadata = models.JSONField(default=dict)
    environment = models.CharField(max_length=50, default='production')

    # Attach custom manager — replaces default objects = models.Manager()
    objects = HealthStatusManager()

    class Meta:
        verbose_name = 'Health Status'
        verbose_name_plural = 'Health Statuses'
        ordering = ['-last_check']
        indexes = [
            models.Index(fields=['service_name']),
            models.Index(fields=['component_name']),
            models.Index(fields=['status']),
            models.Index(fields=['environment']),
            models.Index(fields=['last_check']),
        ]
        unique_together = [['service_name', 'component_name', 'environment']]

    def __str__(self):
        if self.component_name:
            return f"{self.service_name} - {self.component_name}: {self.status}"
        return f"{self.service_name}: {self.status}"

    def is_healthy(self):
        """
        Check if the service/component is healthy.

        Returns:
            bool: True if status is 'healthy' AND health_score >= 70
        """
        return self.status == 'healthy' and self.health_score >= 70

    def is_degraded(self):
        """
        Check if the service/component is degraded.

        Returns:
            bool: True if status is 'degraded' OR health_score is in [50, 70)
        """
        return self.status == 'degraded' or (50 <= self.health_score < 70)

    def is_unhealthy(self):
        """
        Check if the service/component is unhealthy.

        Returns:
            bool: True if status is 'unhealthy' OR health_score < 50
        """
        return self.status == 'unhealthy' or self.health_score < 50
