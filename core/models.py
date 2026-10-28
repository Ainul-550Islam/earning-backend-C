# core/models.py
# Central abstract base models — used by CMS and all api apps.
# All other apps (cms, wallet, users, etc.) import from here.

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base: created_at + updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class SoftDeleteModel(models.Model):
    """Abstract base: soft-delete support (is_deleted flag)."""
    is_deleted  = models.BooleanField(default=False, db_index=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class BaseModel(TimeStampedModel, SoftDeleteModel):
    """Full base model: timestamps + soft-delete."""
    class Meta(TimeStampedModel.Meta):
        abstract = True
