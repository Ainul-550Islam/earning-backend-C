"""
Trace Span model for Telemetry Observability.
"""
from django.db import models
from django.core.validators import MinValueValidator

from .base import BaseModel
from ..choices import TraceStatusChoices
from ..validators import TraceIdValidator, OperationNameValidator, ServiceNameValidator


class TraceSpanManager(models.Manager):
    """
    Custom manager for TraceSpan model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_trace_id(self, trace_id):
        """Return all spans belonging to a specific trace."""
        return self.filter(trace_id=trace_id)

    def by_service(self, service):
        """Filter spans by service name."""
        return self.filter(service=service)

    def by_status(self, status):
        """Filter spans by status (success, error, timeout)."""
        return self.filter(status=status)

    def by_operation(self, operation_name):
        """Filter spans by operation name."""
        return self.filter(operation_name=operation_name)

    def errors(self):
        """Return only error-status spans."""
        return self.filter(status='error')

    def timeouts(self):
        """Return only timeout-status spans."""
        return self.filter(status='timeout')

    def slow(self, threshold_ms=5000):
        """Return spans that took longer than threshold_ms milliseconds."""
        return self.filter(duration_ms__gte=threshold_ms)

    def completed(self):
        """Return spans that have been finished (end_time is set)."""
        return self.filter(end_time__isnull=False)

    def in_progress(self):
        """Return spans that are still in progress (no end_time yet)."""
        return self.filter(end_time__isnull=True)

    def recent(self, hours=24):
        """Return spans started within the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(start_time__gte=since)


class TraceSpan(BaseModel):
    """
    Model representing a distributed trace span.
    """

    trace_id = models.CharField(max_length=255, db_index=True, validators=[TraceIdValidator()])
    span_id = models.CharField(max_length=255, unique=True, db_index=True, validators=[TraceIdValidator()])
    parent_span_id = models.CharField(max_length=255, blank=True, null=True)
    operation_name = models.CharField(max_length=255, validators=[OperationNameValidator()])
    service = models.CharField(max_length=255, blank=True, default='', validators=[ServiceNameValidator()])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    duration_ms = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    status = models.CharField(
        max_length=50,
        choices=TraceStatusChoices.choices,
        default=TraceStatusChoices.SUCCESS,
    )
    tags = models.JSONField(default=dict)
    logs = models.JSONField(default=list)
    context = models.JSONField(default=dict)

    # Attach custom manager — replaces default objects = models.Manager()
    objects = TraceSpanManager()

    class Meta:
        verbose_name = 'Trace Span'
        verbose_name_plural = 'Trace Spans'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['trace_id'], name='trace_id_idx'),
            models.Index(fields=['span_id'], name='span_id_idx'),
            models.Index(fields=['operation_name'], name='operation_name_idx'),
            models.Index(fields=['service'], name='trace_service_idx'),
            models.Index(fields=['start_time'], name='trace_start_time_idx'),
        ]

    def __str__(self):
        return f"{self.operation_name} ({self.span_id})"
