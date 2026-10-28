"""
Widget Configuration manager for Real-time Dashboard Backend.
"""
from django.db import models


class WidgetConfigurationQuerySet(models.QuerySet):
    """
    Custom QuerySet for WidgetConfiguration.

    Provides .by_widget() and .by_type() manager methods so viewsets
    and services never repeat raw .filter(widget_id=...) calls (DRY).

    Uses Manager.from_queryset() so methods are available on both the
    manager and every QuerySet clone (see managers/widget_manager.py
    for the full explanation of this pattern).
    """

    def by_widget(self, widget_id):
        """Return configurations for the given widget_id."""
        return self.filter(widget_id=widget_id)

    def by_type(self, config_type):
        """Return configurations matching the given config_type."""
        return self.filter(config_type=config_type)


WidgetConfigurationManager = models.Manager.from_queryset(WidgetConfigurationQuerySet)
