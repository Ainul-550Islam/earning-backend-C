"""
Experiment Runner for Feature Flags & A/B Testing.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta

from .models.experiment import Experiment
from .models.experiment_participant import ExperimentParticipant
from .models.flag_variant import FlagVariant
from .exceptions import ExperimentNotFoundError, ExperimentNotActiveError, InvalidVariantError


class ExperimentRunner:
    """
    Runner for managing A/B testing experiments.
    """
    
    def __init__(self):
        """Initialize the experiment runner."""
        pass
    
    def initialize_experiment(self, experiment: Experiment) -> bool:
        """
        Initialize an experiment.
        
        Args:
            experiment: Experiment instance
            
        Returns:
            True if successful
        """
        # Validate experiment
        if not experiment.flag:
            return False
        
        # Ensure variants exist
        variants = FlagVariant.objects.filter(flag=experiment.flag, is_active=True)
        
        if not variants.exists():
            return False
        
        return True
    
    def start_experiment(self, experiment: Experiment) -> bool:
        """
        Start an experiment.
        
        Args:
            experiment: Experiment instance
            
        Returns:
            True if successful
        """
        if experiment.status != Experiment.Status.RUNNING:
            return False
        
        # Set start date if not set
        if not experiment.start_date:
            experiment.start_date = timezone.now()
            experiment.save()
        
        return True
    
    def assign_variant(self, experiment_name: str, context: Dict[str, Any]) -> Optional[FlagVariant]:
        """
        Assign a variant to a user for an experiment.
        
        Args:
            experiment_name: Name of the experiment
            context: Context dictionary
            
        Returns:
            Assigned FlagVariant instance or None
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            raise ExperimentNotFoundError(f"Experiment '{experiment_name}' not found")
        
        if not experiment.is_active():
            raise ExperimentNotActiveError(f"Experiment '{experiment_name}' is not active")
        
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
            raise InvalidVariantError("No active variants found")
        
        # Assign variant based on hash
        from .utils import get_user_hash
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
                        # FIX: ExperimentParticipant.session_id is `blank=True`
                        # but NOT `null=True` (CharField convention — empty
                        # string, not NULL, represents "no value" at the DB
                        # level). The original `context.get('session_id')`
                        # returned None whenever the caller's context dict
                        # didn't include a session_id key, which raised
                        # `IntegrityError: NOT NULL constraint failed` on
                        # every such call. Default to '' instead.
                        ExperimentParticipant.objects.create(
                            experiment=experiment,
                            variant=variant,
                            user_id=user_id,
                            session_id=context.get('session_id') or '',
                            context=context
                        )
                    
                    return variant
        
        return variants.first()
    
    def track_conversion(self, experiment_name: str, context: Dict[str, Any]) -> bool:
        """
        Track a conversion for an experiment.
        
        Args:
            experiment_name: Name of the experiment
            context: Context dictionary
            
        Returns:
            True if successful
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            raise ExperimentNotFoundError(f"Experiment '{experiment_name}' not found")
        
        user_id = context.get('user_id')
        
        if not user_id:
            return False
        
        try:
            participant = ExperimentParticipant.objects.get(
                experiment=experiment,
                user_id=user_id
            )
            
            if not participant.converted:
                participant.converted = True
                participant.converted_at = timezone.now()
                participant.save()
                return True
            
        except ExperimentParticipant.DoesNotExist:
            return False
        
        return False
    
    def get_experiment_results(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get results for an experiment.
        
        Args:
            experiment_name: Name of the experiment
            
        Returns:
            Dictionary with experiment results
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            raise ExperimentNotFoundError(f"Experiment '{experiment_name}' not found")
        
        return {
            'experiment_name': experiment.name,
            'status': experiment.status,
            'start_date': experiment.start_date,
            'end_date': experiment.end_date,
            'participant_count': experiment.get_participant_count(),
            'variant_stats': experiment.get_variant_stats()
        }
    
    def get_active_experiments(self) -> List[Experiment]:
        """
        Get all active experiments.
        
        Returns:
            List of active Experiment instances
        """
        now = timezone.now()
        return list(Experiment.objects.filter(
            status=Experiment.Status.RUNNING,
            start_date__lte=now
        ).exclude(end_date__lt=now))
