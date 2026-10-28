"""
Dashboard Layout manager for Real-time Dashboard Backend.
"""
from django.db import models


class DashboardLayoutQuerySet(models.QuerySet):
    """
    Custom QuerySet for DashboardLayout.

    Provides .by_type() and .by_creator() manager methods so viewsets
    and services never repeat raw .filter(layout_type=...) calls (DRY).

    Uses Manager.from_queryset() pattern for QuerySet-level availability.
    """

    def by_type(self, layout_type):
        """Return layouts matching the given layout_type."""
        return self.filter(layout_type=layout_type)

    def by_creator(self, created_by):
        """Return layouts created by the given user identifier."""
        return self.filter(created_by=created_by)


DashboardLayoutManager = models.Manager.from_queryset(DashboardLayoutQuerySet)
