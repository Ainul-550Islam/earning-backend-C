# api/support/abstracts.py
"""
Abstract base model classes for support system.
These are NOT registered in the database — they provide shared fields.
Full code — no summarizing.
"""
from django.db import models
from django.conf import settings


class TimestampedModel(models.Model):
    """Add created_at and updated_at to any model."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(models.Model):
    """Add tenant FK to any model for multi-tenancy."""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    class Meta:
        abstract = True


class UserOwnerModel(models.Model):
    """Model owned by a specific user."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        db_index=True,
    )

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Soft delete — records are not physically deleted.
    Use .objects.active() for active records.
    """
    is_deleted  = models.BooleanField(default=False, db_index=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    deleted_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_deleted',
    )

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by=None):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])


class StatusModel(models.Model):
    """Model with a status field and helpers."""
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    def activate(self):
        self.is_active = True
        self.save(update_fields=['is_active'])

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=['is_active'])


class OrderedModel(models.Model):
    """Model with ordering support."""
    order = models.IntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ['order']


class SupportBaseModel(TimestampedModel, TenantModel):
    """
    Base model for all support models.
    Combines timestamps and tenant filtering.
    """
    class Meta:
        abstract = True


class AuditedModel(SupportBaseModel):
    """
    Model that tracks who created/updated it.
    Use for sensitive models: disputes, wallet operations.
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_updated',
    )

    class Meta:
        abstract = True