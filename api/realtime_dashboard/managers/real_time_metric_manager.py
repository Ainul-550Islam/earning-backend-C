"""
Real-time Metric manager for Real-time Dashboard Backend.
"""
from django.db import models


class RealTimeMetricQuerySet(models.QuerySet):
    """
    Custom QuerySet for RealTimeMetric.

    See managers/widget_manager.py (WidgetQuerySet) for the full
    explanation of why the from_queryset() pattern is used here instead
    of a plain models.Manager subclass.
    """

    def by_type(self, metric_type):
        """Return metrics matching the given metric_type."""
        return self.filter(metric_type=metric_type)

    def by_status(self, status):
        """Return metrics matching the given status."""
        return self.filter(status=status)

    def active(self):
        """Return only active metrics (status='active')."""
        return self.filter(status='active')


RealTimeMetricManager = models.Manager.from_queryset(RealTimeMetricQuerySet)
