"""
Experiment service for Feature Flags & A/B Testing.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone

from ..models.experiment import Experiment
from ..experiment_runner import ExperimentRunner
from ..exceptions import ExperimentNotFoundError


class ExperimentService:
    """
    Service for managing experiments.
    """
    
    def __init__(self):
        """Initialize the experiment service."""
        self.runner = ExperimentRunner()
    
    def create_experiment(self, data: Dict[str, Any]) -> Experiment:
        """
        Create a new experiment.
        
        Args:
            data: Experiment data
            
        Returns:
            Created Experiment instance
        """
        return Experiment.objects.create(
            name=data['name'],
            description=data.get('description', ''),
            flag_id=data['flag'],
            status=data.get('status', 'draft'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            target_audience=data.get('target_audience', {}),
            success_metrics=data.get('success_metrics', []),
            min_sample_size=data.get('min_sample_size', 100),
            significance_threshold=data.get('significance_threshold', 0.95),
            metadata=data.get('metadata', {}),
            owner=data.get('owner', ''),
            team=data.get('team', '')
        )
    
    def get_experiment(self, experiment_name: str) -> Optional[Experiment]:
        """
        Get an experiment by name.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            Experiment instance or None
        """
        try:
            return Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            return None
    
    def get_experiments(self, status: Optional[str] = None) -> List[Experiment]:
        """
        Get experiments with optional status filter.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of Experiment instances
        """
        queryset = Experiment.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset.order_by('-created_at'))
    
    def update_experiment(self, experiment_name: str, data: Dict[str, Any]) -> bool:
        """
        Update an experiment.
        
        Args:
            experiment_name: Experiment name
            data: Experiment data to update
            
        Returns:
            True if successful
        """
        experiment = self.get_experiment(experiment_name)
        
        if not experiment:
            return False
        
        for key, value in data.items():
            if hasattr(experiment, key) and key not in ['id', 'created_at', 'updated_at']:
                setattr(experiment, key, value)
        
        experiment.save()
        
        return True
    
    def delete_experiment(self, experiment_name: str) -> bool:
        """
        Delete an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            True if successful
        """
        experiment = self.get_experiment(experiment_name)
        
        if not experiment:
            return False
        
        experiment.delete()
        
        return True
    
    def start_experiment(self, experiment_name: str) -> bool:
        """
        Start an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            True if successful
        """
        return self.update_experiment(experiment_name, {'status': 'running'})
    
    def pause_experiment(self, experiment_name: str) -> bool:
        """
        Pause an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            True if successful
        """
        return self.update_experiment(experiment_name, {'status': 'paused'})
    
    def complete_experiment(self, experiment_name: str) -> bool:
        """
        Complete an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            True if successful
        """
        return self.update_experiment(experiment_name, {'status': 'completed'})
    
    def assign_variant(self, experiment_name: str, context: Dict[str, Any]):
        """
        Assign a variant to a user for an experiment.
        
        Args:
            experiment_name: Experiment name
            context: Context dictionary
            
        Returns:
            Assigned variant
        """
        return self.runner.assign_variant(experiment_name, context)
    
    def track_conversion(self, experiment_name: str, context: Dict[str, Any]) -> bool:
        """
        Track a conversion for an experiment.
        
        Args:
            experiment_name: Experiment name
            context: Context dictionary
            
        Returns:
            True if successful
        """
        return self.runner.track_conversion(experiment_name, context)
    
    def get_results(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get experiment results.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            Dictionary with experiment results
        """
        return self.runner.get_experiment_results(experiment_name)
    
    def get_active_experiments(self) -> List[Experiment]:
        """
        Get all active experiments.
        
        Returns:
            List of active Experiment instances
        """
        return self.runner.get_active_experiments()
