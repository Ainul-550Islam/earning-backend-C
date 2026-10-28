"""
Metric Event model for Telemetry Observability.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .base import BaseModel


class MetricEventManager(models.Manager):
    """
    Custom manager for MetricEvent model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_name(self, name):
        """Filter metrics by exact name."""
        return self.filter(name=name)

    def by_type(self, metric_type):
        """Filter metrics by metric_type (counter, gauge, histogram, summary)."""
        return self.filter(metric_type=metric_type)

    def by_service(self, service):
        """Filter metrics by service name."""
        return self.filter(service=service)

    def by_environment(self, environment):
        """Filter metrics by environment."""
        return self.filter(environment=environment)

    def by_source(self, source):
        """Filter metrics by source."""
        return self.filter(source=source)

    def recent(self, hours=24):
        """Return metrics recorded within the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=since)

    def with_value_range(self, min_value, max_value):
        """Return metrics whose value falls within [min_value, max_value]."""
        return self.filter(value__gte=min_value, value__lte=max_value)

    def search(self, query):
        """Case-insensitive name search."""
        return self.filter(name__icontains=query)

    def counters(self):
        """Return only counter-type metrics."""
        return self.filter(metric_type='counter')

    def gauges(self):
        """Return only gauge-type metrics."""
        return self.filter(metric_type='gauge')


class MetricEvent(BaseModel):
    """
    Model representing a metric event for telemetry.
    """

    name = models.CharField(max_length=255)
    metric_type = models.CharField(
        max_length=50,
        choices=[
            ('counter', 'Counter'),
            ('gauge', 'Gauge'),
            ('histogram', 'Histogram'),
            ('summary', 'Summary'),
        ],
        default='counter'
    )
    value = models.FloatField()
    unit = models.CharField(max_length=50, blank=True)
    labels = models.JSONField(default=dict)
    source = models.CharField(max_length=255, blank=True)
    service = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=50, default='production')
    timestamp = models.DateTimeField(auto_now_add=True)

    # Attach custom manager — replaces default objects = models.Manager()
    objects = MetricEventManager()

    class Meta:
        verbose_name = 'Metric Event'
        verbose_name_plural = 'Metric Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['metric_type']),
            models.Index(fields=['source']),
            models.Index(fields=['service']),
            models.Index(fields=['environment']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.name}: {self.value} {self.unit}"
