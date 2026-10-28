"""
Widget manager for Real-time Dashboard Backend.
"""
from django.db import models


class WidgetQuerySet(models.QuerySet):
    """
    Custom QuerySet for DashboardWidget.

    FIXED (architecture): the original WidgetManager extended models.Manager
    directly, which means custom methods like .active() were only available
    on the Manager instance itself, NOT on QuerySet clones produced by
    .all() / .filter() etc. DRF viewsets store `queryset = Model.objects.all()`
    at class-definition time, which yields a plain QuerySet clone - so
    `self.queryset.active()` raised AttributeError at runtime.

    The fix is Manager.from_queryset(WidgetQuerySet) below, which overrides
    get_queryset() so every clone the manager produces is a WidgetQuerySet.
    Methods like .active() are therefore available on self.queryset in every
    viewset, on chained calls (.filter(...).active()), and on the manager
    itself - all from one definition, with no duplication.
    """

    def by_type(self, widget_type):
        """Return widgets matching the given widget_type."""
        return self.filter(widget_type=widget_type)

    def by_status(self, status):
        """Return widgets matching the given status."""
        return self.filter(status=status)

    def active(self):
        """Return only active widgets (status='active')."""
        return self.filter(status='active')


WidgetManager = models.Manager.from_queryset(WidgetQuerySet)
