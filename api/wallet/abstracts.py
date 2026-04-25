# api/wallet/abstracts.py
"""
Abstract base models for DRY inheritance.
All wallet models inherit from these.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    """All models get created_at + updated_at."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """UUID primary key model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantModel(models.Model):
    """Multi-tenant support via ForeignKey."""
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
    )

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Soft delete — mark as deleted instead of removing."""
    is_deleted    = models.BooleanField(default=False, db_index=True)
    deleted_at    = models.DateTimeField(null=True, blank=True)
    deleted_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self, user_id=None):
        self.is_deleted    = True
        self.deleted_at    = timezone.now()
        self.deleted_by_id = user_id
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by_id"])


class ImmutableModel(models.Model):
    """Immutable model — cannot be updated or deleted (audit logs, ledger entries)."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError(f"{self.__class__.__name__} is immutable — cannot update.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(f"{self.__class__.__name__} is immutable — cannot delete.")


class MoneyModel(models.Model):
    """Base for models with financial amounts."""
    amount   = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="BDT")

    class Meta:
        abstract = True

    @property
    def amount_display(self):
        return f"{self.amount:.2f} {self.currency}"


class StatusModel(models.Model):
    """Model with status + timestamps for lifecycle tracking."""
    status     = models.CharField(max_length=20, db_index=True)
    status_at  = models.DateTimeField(null=True, blank=True)
    status_note= models.TextField(blank=True)

    class Meta:
        abstract = True

    def set_status(self, new_status: str, note: str = ""):
        self.status      = new_status
        self.status_at   = timezone.now()
        self.status_note = note
        self.save(update_fields=["status", "status_at", "status_note"])


class BaseWalletModel(TenantModel, TimestampedModel):
    """Base for all wallet models — tenant + timestamps."""
    class Meta:
        abstract = True
