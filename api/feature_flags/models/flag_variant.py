"""
Flag Variant model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.core.validators import MinValueValidator

from .base import BaseModel
from .feature_flag import FeatureFlag


class FlagVariant(BaseModel):
    """
    Model for flag variants used in A/B testing.
    """
    
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='variants')
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Variant value.
    # FIX: the original field had no `default`, which made it hard to create
    # variants in tests/services without always supplying an explicit value,
    # and caused NOT NULL IntegrityErrors whenever code forgot to pass one
    # (e.g. clone operations). An empty dict is a sensible sentinel value for
    # "no value configured yet".
    value = models.JSONField(default=dict)
    
    # Weight for traffic allocation (0-100)
    weight = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0)]
    )
    
    # Is this the control variant?
    is_control = models.BooleanField(default=False)
    
    # Is this variant active?
    is_active = models.BooleanField(default=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'Flag Variant'
        verbose_name_plural = 'Flag Variants'
        ordering = ['-weight']
        unique_together = [['flag', 'name']]
        indexes = [
            models.Index(fields=['flag'], name='variant_flag_idx'),
            models.Index(fields=['is_active'], name='variant_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.flag.name} - {self.name}"
