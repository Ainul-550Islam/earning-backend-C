"""
Experiment Participant model for Feature Flags & A/B Testing.
"""
from django.db import models

from .base import BaseModel
from .experiment import Experiment
from .flag_variant import FlagVariant


class ExperimentParticipant(BaseModel):
    """
    Model for tracking experiment participants.
    """
    
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='participants')
    variant = models.ForeignKey(FlagVariant, on_delete=models.CASCADE, related_name='participants')
    
    # User identifier
    user_id = models.CharField(max_length=255, db_index=True)
    
    # Session identifier
    session_id = models.CharField(max_length=255, blank=True, db_index=True)
    
    # Has the user converted?
    converted = models.BooleanField(default=False)
    
    # Conversion timestamp
    converted_at = models.DateTimeField(null=True, blank=True)
    
    # Additional context
    context = models.JSONField(default=dict)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'Experiment Participant'
        verbose_name_plural = 'Experiment Participants'
        ordering = ['-created_at']
        unique_together = [['experiment', 'user_id']]
        indexes = [
            models.Index(fields=['experiment'], name='participant_exp_idx'),
            models.Index(fields=['variant'], name='participant_variant_idx'),
            models.Index(fields=['user_id'], name='participant_user_idx'),
            models.Index(fields=['converted'], name='participant_converted_idx'),
        ]
    
    def __str__(self):
        return f"{self.experiment.name} - {self.user_id} ({self.variant.name})"
