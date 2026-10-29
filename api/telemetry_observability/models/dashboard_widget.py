"""
Dashboard Widget model for Telemetry Observability.
"""
from django.db import models
from django.core.validators import MinValueValidator

from .base import BaseModel
from ..choices import WidgetTypeChoices, DataSourceChoices
from ..validators import GridSizeValidator


class DashboardWidgetManager(models.Manager):
    """
    Custom manager for DashboardWidget model.
    Provides convenience queryset methods used throughout the codebase.
    """

    def by_type(self, widget_type):
        """Filter widgets by widget_type."""
        return self.filter(widget_type=widget_type)

    def by_data_source(self, data_source):
        """Filter widgets by data_source (metric, log, trace, alert, health, custom)."""
        return self.filter(data_source=data_source)

    def by_dashboard(self, dashboard_id):
        """Return all widgets belonging to a specific dashboard."""
        return self.filter(dashboard_id=dashboard_id)

    def active(self):
        """Return only active (is_active=True) widgets."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive (is_active=False) widgets."""
        return self.filter(is_active=False)

    def search(self, query):
        """Case-insensitive search by widget name."""
        return self.filter(name__icontains=query)

    def ordered_by_position(self):
        """Return widgets sorted by grid position (top-left to bottom-right)."""
        return self.order_by('position_y', 'position_x')


class DashboardWidget(BaseModel):
    """
    Model representing a dashboard widget for visualization.
    """

    name = models.CharField(max_length=255)
    widget_type = models.CharField(
        max_length=50,
        choices=WidgetTypeChoices.choices,
        default=WidgetTypeChoices.METRIC_CARD,
    )
    data_source = models.CharField(
        max_length=50,
        choices=DataSourceChoices.choices,
        default=DataSourceChoices.METRIC,
    )
    query = models.JSONField(default=dict)
    config = models.JSONField(default=dict)
    position_x = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    position_y = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    width = models.IntegerField(default=4, validators=[GridSizeValidator()])
    height = models.IntegerField(default=4, validators=[GridSizeValidator()])
    refresh_interval = models.IntegerField(default=60, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    dashboard = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='widgets',
        null=True,
        blank=True
    )

    # Attach custom manager — replaces default objects = models.Manager()
    objects = DashboardWidgetManager()

    class Meta:
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['position_y', 'position_x']
        indexes = [
            models.Index(fields=['widget_type'], name='widget_type_idx'),
            models.Index(fields=['data_source'], name='widget_source_idx'),
            models.Index(fields=['dashboard'], name='widget_dashboard_idx'),
            models.Index(fields=['is_active'], name='widget_active_idx'),
        ]

    def __str__(self):
        return self.name
