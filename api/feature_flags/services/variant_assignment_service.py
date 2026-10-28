"""
Variant Assignment service for Feature Flags & A/B Testing.
"""
from typing import Dict, Any, Optional
from django.utils import timezone

from ..models.flag_variant import FlagVariant
from ..models.experiment_participant import ExperimentParticipant
from ..models.experiment import Experiment
from ..utils import get_user_hash


class VariantAssignmentService:
    """
    Service for assigning variants to users.
    """
    
    def __init__(self):
        """Initialize the variant assignment service."""
        pass
    
    def assign_variant_for_flag(self, flag_name: str, context: Dict[str, Any]) -> Optional[FlagVariant]:
        """
        Assign a variant for a feature flag.
        
        Args:
            flag_name: Flag name
            context: Context dictionary
            
        Returns:
            Assigned FlagVariant instance or None
        """
        from ..models.feature_flag import FeatureFlag
        
        try:
            flag = FeatureFlag.objects.get(name=flag_name)
        except FeatureFlag.DoesNotExist:
            return None
        
        variants = FlagVariant.objects.filter(flag=flag, is_active=True)
        
        if not variants.exists():
            return None
        
        user_id = context.get('user_id')
        user_hash = get_user_hash(user_id or context.get('session_id', ''))
        total_weight = sum(v.weight for v in variants)
        
        if total_weight > 0:
            threshold = (user_hash % 100) / 100 * total_weight
            current_weight = 0
            
            for variant in variants:
                current_weight += variant.weight
                if threshold <= current_weight:
                    return variant
        
        return variants.first()
    
    def assign_variant_for_experiment(self, experiment_name: str, context: Dict[str, Any]) -> Optional[FlagVariant]:
        """
        Assign a variant for an experiment.
        
        Args:
            experiment_name: Experiment name
            context: Context dictionary
            
        Returns:
            Assigned FlagVariant instance or None
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            return None
        
        if not experiment.is_active():
            return None
        
        # Check if user is already assigned
        user_id = context.get('user_id')
        if user_id:
            try:
                participant = ExperimentParticipant.objects.get(
                    experiment=experiment,
                    user_id=user_id
                )
                return participant.variant
            except ExperimentParticipant.DoesNotExist:
                pass
        
        # Get variants
        variants = FlagVariant.objects.filter(flag=experiment.flag, is_active=True)
        
        if not variants.exists():
            return None
        
        # Assign variant based on hash
        user_hash = get_user_hash(user_id or context.get('session_id', ''))
        total_weight = sum(v.weight for v in variants)
        
        if total_weight > 0:
            threshold = (user_hash % 100) / 100 * total_weight
            current_weight = 0
            
            for variant in variants:
                current_weight += variant.weight
                if threshold <= current_weight:
                    # Create participant record
                    if user_id:
                        # FIX: same NOT NULL bug as experiment_runner.py
                        # (this duplicated block is exactly the DRY violation
                        # flagged in the audit) — session_id is blank=True
                        # but not null=True, so None must become ''.
                        ExperimentParticipant.objects.create(
                            experiment=experiment,
                            variant=variant,
                            user_id=user_id,
                            session_id=context.get('session_id') or '',
                            context=context
                        )
                    
                    return variant
        
        return variants.first()
    
    def get_assigned_variant(self, experiment_name: str, user_id: str) -> Optional[FlagVariant]:
        """
        Get the assigned variant for a user in an experiment.
        
        Args:
            experiment_name: Experiment name
            user_id: User ID
            
        Returns:
            Assigned FlagVariant instance or None
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
            participant = ExperimentParticipant.objects.get(
                experiment=experiment,
                user_id=user_id
            )
            return participant.variant
        except (Experiment.DoesNotExist, ExperimentParticipant.DoesNotExist):
            return None
