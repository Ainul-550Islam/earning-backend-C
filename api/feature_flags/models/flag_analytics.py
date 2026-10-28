"""
Flag Analytics model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .base import BaseModel
from .feature_flag import FeatureFlag
from .flag_variant import FlagVariant


class FlagAnalytics(BaseModel):
    """
    Model for tracking flag analytics and usage.
    """
    
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='analytics')
    variant = models.ForeignKey(FlagVariant, on_delete=models.CASCADE, related_name='analytics', null=True, blank=True)
    
    # Date for aggregation
    date = models.DateField(db_index=True)
    
    # Hour for hourly aggregation
    hour = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)]
    )
    
    # Number of evaluations
    evaluation_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Number of times flag was enabled
    enabled_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Number of times flag was disabled
    disabled_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Unique users
    unique_users = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Conversion events
    conversion_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Additional metrics
    metrics = models.JSONField(default=dict)
    
    # Environment
    environment = models.CharField(max_length=50, default='production')
    
    class Meta:
        verbose_name = 'Flag Analytics'
        verbose_name_plural = 'Flag Analytics'
        ordering = ['-date', '-hour']
        unique_together = [['flag', 'variant', 'date', 'hour', 'environment']]
        indexes = [
            models.Index(fields=['flag'], name='analytics_flag_idx'),
            models.Index(fields=['variant'], name='analytics_variant_idx'),
            models.Index(fields=['date'], name='analytics_date_idx'),
            models.Index(fields=['environment'], name='analytics_env_idx'),
        ]
    
    def __str__(self):
        variant_name = self.variant.name if self.variant else 'default'
        return f"{self.flag.name} - {variant_name} - {self.date}"
    
    def get_enable_rate(self) -> float:
        """
        Get the enable rate percentage.
        
        Returns:
            Enable rate as percentage
        """
        if self.evaluation_count == 0:
            return 0.0
        
        return round((self.enabled_count / self.evaluation_count) * 100, 2)
    
    def get_conversion_rate(self) -> float:
        """
        Get the conversion rate percentage.
        
        Returns:
            Conversion rate as percentage
        """
        if self.unique_users == 0:
            return 0.0
        
        return round((self.conversion_count / self.unique_users) * 100, 2)
