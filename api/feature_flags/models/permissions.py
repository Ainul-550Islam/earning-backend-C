"""
NEW FILE — Role-Based Access Control models.

Implements Missing Component #1 (Authentication & Permissions) from the
audit. Three small models give us a minimal but functional RBAC system:
Role (admin/editor/viewer), Permission (fine-grained capability), and
UserRole (which role a given user holds).
"""
from django.conf import settings
from django.db import models

from .base import BaseModel


class Role(BaseModel):
    """A named role, e.g. admin / editor / viewer."""

    class RoleName(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    name = models.CharField(max_length=50, choices=RoleName.choices, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['name']

    def __str__(self):
        return self.name


class Permission(BaseModel):
    """A single fine-grained capability that can be granted to a Role."""

    class PermissionName(models.TextChoices):
        VIEW_FLAG = 'view_flag', 'View Feature Flags'
        CREATE_FLAG = 'create_flag', 'Create Feature Flags'
        EDIT_FLAG = 'edit_flag', 'Edit Feature Flags'
        DELETE_FLAG = 'delete_flag', 'Delete Feature Flags'
        START_EXPERIMENT = 'start_experiment', 'Start Experiments'
        VIEW_ANALYTICS = 'view_analytics', 'View Analytics'
        MANAGE_USERS = 'manage_users', 'Manage Users'
        APPROVE_CHANGES = 'approve_changes', 'Approve Flag Changes'

    name = models.CharField(max_length=50, choices=PermissionName.choices, unique=True)
    description = models.TextField(blank=True)
    roles = models.ManyToManyField(Role, related_name='permissions', blank=True)

    class Meta:
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserRole(BaseModel):
    """Which Role a given User holds. One role per user in this simplified model."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feature_flag_role')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')

    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'

    def __str__(self):
        return f"{self.user} -> {self.role.name}"
