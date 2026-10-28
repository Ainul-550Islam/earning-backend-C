# api/djoyalty/abstracts.py
"""
Djoyalty Abstract Models -- Base classes for all loyalty models।
Provides: TimestampMixin, TenantMixin, SoftDeleteMixin, etc।

AUDIT FIX (2.5): TenantMixin previously contained only a nullable
`tenant` FK.  DjoyaltyTenantMixin.get_queryset() filtered with
  Q(tenant=tenant) | Q(tenant__isnull=True)
which matched ANY record whose tenant was never set — orphaned rows,
test fixtures, partially migrated data — not just deliberately shared
"global" records.  This is a data-leak risk: a tenant could silently
see records that were never meant to be cross-tenant.

Fix: Added `is_global` BooleanField to TenantMixin.
  - Default: False  (no record is global unless explicitly flagged)
  - db_index: True  (used in every tenant-scoped queryset)
  - Admin-only: never auto-set by service code

DjoyaltyTenantMixin.get_queryset() now filters with:
  Q(tenant=tenant) | Q(is_global=True)

Records that need cross-tenant visibility must have is_global=True set
explicitly.  tenant__isnull=True no longer leaks data.

Migration: run `python manage.py makemigrations djoyalty` then
`python manage.py migrate` to add the is_global column to every
model that inherits TenantMixin (directly or via LoyaltyBaseModel).
"""
from django.db import models
from django.utils import timezone


class TimestampMixin(models.Model):
    """Adds created_at and updated_at to any model।"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantMixin(models.Model):
    """
    Adds optional tenant FK for multi-tenancy।

    AUDIT FIX (2.5): `is_global` added।
    Records with is_global=True are returned to ALL tenants.
    Records with tenant=None and is_global=False are returned to NO tenant
    (orphaned/draft — not leaked through the mixin queryset filter).
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    is_global = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Global Record',
        help_text=(
            'If True, this record is visible to ALL tenants. '
            'Set by admin only — never auto-set by service code. '
            'Replaces the previous tenant__isnull=True data-leak pattern.'
        ),
    )

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Soft-delete: marks records as deleted without DB removal।"""
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class StatusMixin(models.Model):
    """Adds a standard status field।"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                               default='active', db_index=True)

    class Meta:
        abstract = True

    @property
    def is_active(self):
        return self.status == 'active'


class MetadataMixin(models.Model):
    """Adds a flexible JSONField for extra data।"""
    metadata = models.JSONField(default=dict, blank=True,
                                 help_text='Flexible extra data -- do not rely on structure.')

    class Meta:
        abstract = True


class AuditMixin(TimestampMixin):
    """Adds created_by and updated_by tracking।"""
    created_by = models.CharField(max_length=200, null=True, blank=True)
    updated_by = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        abstract = True


class PointsMixin(models.Model):
    """Common points fields for earn/redeem models।"""
    points = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    points_value_bdt = models.DecimalField(
        max_digits=14, decimal_places=4, default=0,
        verbose_name='BDT Value of Points',
    )

    class Meta:
        abstract = True


class LoyaltyBaseModel(TimestampMixin, TenantMixin):
    """
    Base model for all Djoyalty models।
    Provides: tenant FK + is_global flag + timestamps।

    All models inheriting this class automatically receive the is_global
    field via TenantMixin (audit fix 2.5).
    """
    class Meta:
        abstract = True
