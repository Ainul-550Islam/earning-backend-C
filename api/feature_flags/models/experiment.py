"""
Experiment model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta

from .base import BaseModel
from .feature_flag import FeatureFlag


class Experiment(BaseModel):
    """
    Model for A/B testing experiments.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        RUNNING = 'running', 'Running'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Associated feature flag
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='experiments')
    
    # Experiment status
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.DRAFT)
    
    # Experiment duration
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Target audience
    target_audience = models.JSONField(default=dict)
    
    # Success metrics
    success_metrics = models.JSONField(default=list)
    
    # Minimum sample size
    min_sample_size = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)]
    )
    
    # Statistical significance threshold (0-1)
    significance_threshold = models.FloatField(
        default=0.95,
        validators=[MinValueValidator(0.01), MaxValueValidator(1.0)]
    )
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    # Owner information
    owner = models.CharField(max_length=255, blank=True)
    team = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = 'Experiment'
        verbose_name_plural = 'Experiments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='exp_name_idx'),
            models.Index(fields=['status'], name='exp_status_idx'),
            models.Index(fields=['flag'], name='exp_flag_idx'),
            models.Index(fields=['start_date'], name='exp_start_idx'),
            models.Index(fields=['end_date'], name='exp_end_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    def is_active(self) -> bool:
        """
        Check if the experiment is currently active.
        
        Returns:
            True if experiment is active
        """
        if self.status != self.Status.RUNNING:
            return False
        
        now = timezone.now()
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    def get_participant_count(self) -> int:
        """
        Get the total number of participants.
        
        Returns:
            Participant count
        """
        from .experiment_participant import ExperimentParticipant
        return ExperimentParticipant.objects.filter(experiment=self).count()
    
    def get_variant_stats(self) -> dict:
        """
        Get statistics for each variant.
        
        Returns:
            Dictionary with variant statistics
        """
        from .experiment_participant import ExperimentParticipant
        from .flag_variant import FlagVariant
        
        variants = FlagVariant.objects.filter(flag=self.flag, is_active=True)
        stats = {}
        
        for variant in variants:
            participants = ExperimentParticipant.objects.filter(
                experiment=self,
                variant=variant
            )
            
            stats[variant.name] = {
                'participant_count': participants.count(),
                'conversion_count': participants.filter(converted=True).count(),
                'conversion_rate': 0.0
            }
            
            if stats[variant.name]['participant_count'] > 0:
                stats[variant.name]['conversion_rate'] = round(
                    stats[variant.name]['conversion_count'] / stats[variant.name]['participant_count'] * 100,
                    2
                )
        
        return stats
