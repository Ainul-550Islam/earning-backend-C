"""
Base Models

This module contains base model classes that provide common functionality
for all tenant management models.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides timestamp fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract base model that provides soft delete functionality.
    """
    is_deleted = models.BooleanField(default=False, verbose_name=_('Is Deleted'))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Deleted At'))
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Soft delete the model instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore the soft deleted model instance."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class BaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Base model that combines timestamp and soft delete functionality.
    """
    
    class Meta:
        abstract = True
