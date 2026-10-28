"""
Dashboard manager for Real-time Dashboard Backend.
"""
from django.db import models


class DashboardQuerySet(models.QuerySet):
    """
    Custom QuerySet for UserDashboard.

    See managers/widget_manager.py (WidgetQuerySet) for the full
    explanation of why the from_queryset() pattern is used here instead
    of a plain models.Manager subclass.
    """

    def by_user(self, user_id):
        """Return dashboards belonging to the given user_id."""
        return self.filter(user_id=user_id)

    def by_status(self, status):
        """Return dashboards matching the given status."""
        return self.filter(status=status)

    def active(self):
        """Return only active dashboards (status='active')."""
        return self.filter(status='active')


DashboardManager = models.Manager.from_queryset(DashboardQuerySet)
