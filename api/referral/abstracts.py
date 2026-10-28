# api/referral/abstracts.py
# Abstract base models — DRY foundation for all referral models
# Every concrete model inherits from these
# ============================================================

from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base with created_at + updated_at.
    All referral models that need timestamps inherit this.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimeStampedModel):
    """
    Abstract base with tenant FK + timestamps.
    Multi-tenant isolation — most referral models use this.
    """
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


class UserOwnedModel(TenantScopedModel):
    """
    Abstract base for models owned by a single user.
    Adds user FK + soft-delete.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='%(class)s_owned',
        db_index=True,
    )
    is_deleted    = models.BooleanField(default=False, db_index=True)
    deleted_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class StatusModel(TenantScopedModel):
    """
    Abstract base with is_active status field.
    Campaigns, campaigns, rules, etc.
    """
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    def activate(self) -> None:
        self.is_active = True
        self.save(update_fields=['is_active'])

    def deactivate(self) -> None:
        self.is_active = False
        self.save(update_fields=['is_active'])


class FinancialModel(TenantScopedModel):
    """
    Abstract base for models that handle money.
    Decimal precision, currency, audit trail.
    """
    amount        = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    currency      = models.CharField(max_length=3, default='BDT')

    class Meta:
        abstract = True


class DateRangeModel(TenantScopedModel):
    """
    Abstract base for time-bounded entities.
    Campaigns, contests, surge periods, etc.
    """
    start_date = models.DateTimeField()
    end_date   = models.DateTimeField()

    class Meta:
        abstract = True

    @property
    def is_currently_active(self) -> bool:
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start_date

    @property
    def has_ended(self) -> bool:
        return timezone.now() > self.end_date

    @property
    def duration_days(self) -> int:
        delta = self.end_date - self.start_date
        return delta.days


class AuditedModel(TenantScopedModel):
    """
    Abstract base with full audit trail.
    Tracks who created, modified, approved records.
    """
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_created',
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_modified',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True, default='')

    class Meta:
        abstract = True


class OrderedModel(TenantScopedModel):
    """
    Abstract base for ordered/ranked records.
    Leaderboards, tiers, rules, etc.
    """
    display_order = models.IntegerField(default=0, db_index=True)
    rank          = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['display_order', 'rank']