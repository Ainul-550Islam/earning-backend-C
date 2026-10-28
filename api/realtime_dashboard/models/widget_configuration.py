"""
Widget Configuration model for Real-time Dashboard Backend.
"""
from django.db import models

from .base import BaseModel
from .dashboard_widget import DashboardWidget
from ..managers.widget_configuration_manager import WidgetConfigurationManager


class WidgetConfiguration(BaseModel):
    """
    Model for widget configurations.
    """

    class ConfigType(models.TextChoices):
        CHART = 'chart', 'Chart'
        DATA = 'data', 'Data'
        STYLE = 'style', 'Style'
        BEHAVIOR = 'behavior', 'Behavior'

    # Custom manager - exposes .by_widget() and .by_type() so viewsets
    # never repeat raw .filter(widget_id=...) calls (DRY).
    objects = WidgetConfigurationManager()  # type: ignore[django-manager-missing]

    widget = models.ForeignKey(DashboardWidget, on_delete=models.CASCADE, related_name='configurations')

    # Configuration information
    config_type = models.CharField(max_length=50, choices=ConfigType.choices, default=ConfigType.CHART)
    key = models.CharField(max_length=255)
    value = models.JSONField(default=dict)

    # Metadata
    metadata = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'Widget Configuration'
        verbose_name_plural = 'Widget Configurations'
        ordering = ['widget', 'config_type', 'key']
        unique_together = [['widget', 'key']]
        indexes = [
            models.Index(fields=['widget'], name='wc_widget_idx'),
            models.Index(fields=['config_type'], name='wc_type_idx'),
            models.Index(fields=['key'], name='wc_key_idx'),
        ]

    def __str__(self):
        return f"{self.widget.name} - {self.key}"
