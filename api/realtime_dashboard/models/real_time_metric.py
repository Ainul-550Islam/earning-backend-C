"""
Real-time Metric model for Real-time Dashboard Backend.
"""
from django.core.exceptions import ValidationError
from django.db import models

from .base import BaseModel
from ..managers.real_time_metric_manager import RealTimeMetricManager


class RealTimeMetric(BaseModel):
    """
    Model for real-time metrics.
    """

    class MetricType(models.TextChoices):
        COUNTER = 'counter', 'Counter'
        GAUGE = 'gauge', 'Gauge'
        HISTOGRAM = 'histogram', 'Histogram'
        SUMMARY = 'summary', 'Summary'
        CUSTOM = 'custom', 'Custom'

    class MetricStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ERROR = 'error', 'Error'

    # Custom manager - exposes .active(), .by_type(), .by_status() so
    # viewsets and services never repeat raw .filter(status='active') etc.
    objects = RealTimeMetricManager()  # type: ignore[django-manager-missing]

    # Metric information
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=50, choices=MetricType.choices, db_index=True)
    status = models.CharField(max_length=50, choices=MetricStatus.choices, default=MetricStatus.ACTIVE, db_index=True)

    # Data
    value = models.FloatField(default=0.0)
    previous_value = models.FloatField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True)

    # Thresholds
    warning_threshold = models.FloatField(blank=True, null=True)
    critical_threshold = models.FloatField(blank=True, null=True)

    # Timing
    last_updated = models.DateTimeField(auto_now=True)

    # Metadata
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    class Meta:
        verbose_name = 'Real-time Metric'
        verbose_name_plural = 'Real-time Metrics'
        ordering = ['-last_updated']
        indexes = [
            models.Index(fields=['name'], name='rtm_name_idx'),
            models.Index(fields=['metric_type'], name='rtm_type_idx'),
            models.Index(fields=['status'], name='rtm_status_idx'),
            models.Index(fields=['last_updated'], name='rtm_last_updated_idx'),
        ]
        constraints = [
            # DB-level backstop for the same rule validators.validate_thresholds()
            # enforces in RealTimeMetricSerializer.validate(). A model.clean()
            # alone is NOT enough here: Django does not call full_clean()/clean()
            # automatically on save() (only ModelForm.is_valid() does that), and
            # DRF's ModelSerializer does its own validation independently without
            # touching the model's clean(). Direct ORM writes — management
            # commands, Celery tasks, data migrations, shell access — bypass the
            # serializer entirely, so without this CHECK constraint the
            # warning<critical invariant had zero enforcement outside the API.
            #
            # Note on the type: ignore marker just below: installed
            # django-stubs (6.0.6) types CheckConstraint against a newer
            # Django API surface than the pinned runtime Django (4.2.30)
            # actually has — check= is correct and required on 4.2
            # (condition= replaces it as of a later Django version the
            # stubs already assume).
            models.CheckConstraint(
                check=(
                    models.Q(warning_threshold__isnull=True)
                    | models.Q(critical_threshold__isnull=True)
                    | models.Q(warning_threshold__lt=models.F('critical_threshold'))
                ),
                name='rtm_warning_lt_critical',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.metric_type})"

    def clean(self):
        """
        Model-level mirror of validators.validate_thresholds().

        Not automatically invoked by save() (see the CheckConstraint note
        above) — this exists so anything that DOES call full_clean()
        (Django admin's ModelForm, or a future caller that explicitly
        wants a friendly ValidationError instead of an IntegrityError)
        gets a clear, field-attributed message rather than a raw DB
        constraint violation.
        """
        super().clean()
        if (
            self.warning_threshold is not None
            and self.critical_threshold is not None
            and self.warning_threshold >= self.critical_threshold
        ):
            raise ValidationError({
                'warning_threshold': 'warning_threshold must be less than critical_threshold.',
            })
