"""
User Dashboard model for Real-time Dashboard Backend.
"""
from django.db import models

from .base import BaseModel
from .dashboard_layout import DashboardLayout
from ..managers.dashboard_manager import DashboardManager


class UserDashboard(BaseModel):
    """
    Model for user dashboards.
    """

    class DashboardStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ARCHIVED = 'archived', 'Archived'

    # Custom manager - exposes .active(), .by_user(), .by_status() so
    # viewsets and services never repeat raw .filter(user_id=x) etc.
    objects = DashboardManager()  # type: ignore[django-manager-missing]

    # Dashboard information
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=50, choices=DashboardStatus.choices, default=DashboardStatus.ACTIVE, db_index=True,
    )

    # Layout
    layout = models.ForeignKey(
        DashboardLayout, on_delete=models.SET_NULL, related_name='user_dashboards', blank=True, null=True,
    )

    # Widgets
    widgets = models.JSONField(default=list)

    # User
    user_id = models.CharField(max_length=255, db_index=True)

    # Metadata
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    class Meta:
        verbose_name = 'User Dashboard'
        verbose_name_plural = 'User Dashboards'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='ud_name_idx'),
            models.Index(fields=['status'], name='ud_status_idx'),
            models.Index(fields=['user_id'], name='ud_user_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.user_id})"
