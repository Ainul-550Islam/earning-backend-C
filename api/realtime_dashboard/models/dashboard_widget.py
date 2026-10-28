"""
Dashboard Widget model for Real-time Dashboard Backend.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .base import BaseModel
from ..managers.widget_manager import WidgetManager


class DashboardWidget(BaseModel):  # type: ignore[django-manager-missing]  # reverse accessor gap
    """
    Model for dashboard widgets.
    """

    class WidgetType(models.TextChoices):
        CHART = 'chart', 'Chart'
        TABLE = 'table', 'Table'
        METRIC = 'metric', 'Metric'
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        CUSTOM = 'custom', 'Custom'

    class WidgetStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ARCHIVED = 'archived', 'Archived'

    # Custom manager - exposes .active(), .by_type(), .by_status() so
    # viewsets and services never repeat raw .filter(status='active') etc.
    objects = WidgetManager()  # type: ignore[django-manager-missing]

    # Widget information
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    widget_type = models.CharField(max_length=50, choices=WidgetType.choices, db_index=True)
    status = models.CharField(max_length=50, choices=WidgetStatus.choices, default=WidgetStatus.ACTIVE, db_index=True)

    # Configuration
    configuration = models.JSONField(default=dict)
    data_source = models.CharField(max_length=255, blank=True)
    refresh_interval = models.IntegerField(default=60, validators=[MinValueValidator(0)])

    # Layout
    width = models.IntegerField(default=6, validators=[MinValueValidator(1)])
    height = models.IntegerField(default=4, validators=[MinValueValidator(1)])

    # Metadata
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    # Ownership
    created_by = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='dw_name_idx'),
            models.Index(fields=['widget_type'], name='dw_type_idx'),
            models.Index(fields=['status'], name='dw_status_idx'),
            models.Index(fields=['created_by'], name='dw_created_by_idx'),
        ]
        constraints = [
            # DB-level backstop for the same bounds validators.
            # validate_widget_dimensions() enforces in
            # DashboardWidgetSerializer.validate(). See the comment on
            # RealTimeMetric's rtm_warning_lt_critical constraint for why
            # a model.clean() call alone would not actually be enforced
            # on every write path.
            # Note on the type: ignore markers just below: installed
            # django-stubs (6.0.6) types CheckConstraint against a newer
            # Django API surface than the pinned runtime Django (4.2.30)
            # actually has — check= is correct and required on 4.2
            # (condition= replaces it as of a later Django version the
            # stubs already assume).
            models.CheckConstraint(
                check=models.Q(width__gte=1) & models.Q(width__lte=12),
                name='dw_width_in_grid_range',
            ),
            models.CheckConstraint(
                check=models.Q(height__gte=1) & models.Q(height__lte=24),
                name='dw_height_in_grid_range',
            ),
            models.CheckConstraint(
                check=models.Q(refresh_interval__gte=0),
                name='dw_refresh_interval_non_negative',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.widget_type})"

    def clean(self):
        """
        Model-level mirror of validators.validate_widget_dimensions().
        See RealTimeMetric.clean()'s docstring for why this is a friendly
        companion to the CheckConstraints above, not a substitute for them.
        """
        super().clean()
        errors = {}
        if self.width is not None and not (1 <= self.width <= 12):
            errors['width'] = 'Widget width must be between 1 and 12 (grid columns).'
        if self.height is not None and not (1 <= self.height <= 24):
            errors['height'] = 'Widget height must be between 1 and 24 (grid rows).'
        if errors:
            raise ValidationError(errors)
