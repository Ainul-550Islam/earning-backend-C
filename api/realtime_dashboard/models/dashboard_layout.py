"""
Dashboard Layout model for Real-time Dashboard Backend.
"""
from django.db import models

from .base import BaseModel
from ..managers.dashboard_layout_manager import DashboardLayoutManager


class DashboardLayout(BaseModel):  # type: ignore[django-manager-missing]  # reverse accessor gap
    """
    Model for dashboard layouts.
    """

    class LayoutType(models.TextChoices):
        GRID = 'grid', 'Grid'
        TABS = 'tabs', 'Tabs'
        ACCORDION = 'accordion', 'Accordion'
        CUSTOM = 'custom', 'Custom'

    # Custom manager - exposes .by_type() and .by_creator() so viewsets
    # never repeat raw .filter(layout_type=...) calls (DRY).
    objects = DashboardLayoutManager()  # type: ignore[django-manager-missing]

    # Layout information
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    layout_type = models.CharField(max_length=50, choices=LayoutType.choices, default=LayoutType.GRID, db_index=True)

    # Layout configuration
    columns = models.IntegerField(default=12)
    rows = models.IntegerField(default=12)
    configuration = models.JSONField(default=dict)

    # Metadata
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    # Ownership
    created_by = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Dashboard Layout'
        verbose_name_plural = 'Dashboard Layouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='dl_name_idx'),
            models.Index(fields=['layout_type'], name='dl_type_idx'),
            models.Index(fields=['created_by'], name='dl_created_by_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.layout_type})"
