# api/admin_panel/abstracts.py
"""
Abstract base classes for admin_panel.
All other modules inherit from here — single source of truth.
"""
from __future__ import annotations
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """All admin models have created_at + updated_at."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Primary key is UUID."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class AdminBaseModel(TimeStampedModel):
    """Base for all admin_panel DB models."""
    class Meta:
        abstract = True

    def to_dict(self) -> dict:
        from django.forms.models import model_to_dict
        return model_to_dict(self)


class SoftDeleteModel(TimeStampedModel):
    """Soft delete — never hard delete admin records."""
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    deleted_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])


class AuditedModel(AdminBaseModel):
    """Created/updated by tracking."""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        abstract = True


class SingletonModel(models.Model):
    """Only one instance allowed — e.g. SystemSettings."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CachedModel(AdminBaseModel):
    """Model with built-in cache invalidation."""
    CACHE_TTL = 300  # 5 min default

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._invalidate_cache()

    def delete(self, *args, **kwargs):
        self._invalidate_cache()
        super().delete(*args, **kwargs)

    def _invalidate_cache(self):
        from django.core.cache import cache
        cache.delete(self._cache_key())

    def _cache_key(self) -> str:
        return f'admin_panel:{self.__class__.__name__.lower()}:{self.pk}'