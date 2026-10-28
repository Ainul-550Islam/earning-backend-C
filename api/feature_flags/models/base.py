"""
Base model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base model with common fields.
    """
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """
        Override save to update timestamps.
        """
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
