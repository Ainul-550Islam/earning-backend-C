"""
Experiment manager for Feature Flags & A/B Testing.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.experiment import Experiment


class ExperimentManager(models.Manager):
    """
    Custom manager for Experiment model.
    """
    
    def by_name(self, name):
        """
        Get experiments by name.
        
        Args:
            name: Experiment name
            
        Returns:
            QuerySet
        """
        return self.filter(name=name)
    
    def by_status(self, status):
        """
        Get experiments by status.
        
        Args:
            status: Experiment status
            
        Returns:
            QuerySet
        """
        return self.filter(status=status)
    
    def by_flag(self, flag_id):
        """
        Get experiments by flag.
        
        Args:
            flag_id: Flag ID
            
        Returns:
            QuerySet
        """
        return self.filter(flag_id=flag_id)
    
    def active(self):
        """
        Get active experiments.
        
        Returns:
            QuerySet
        """
        now = timezone.now()
        return self.filter(
            status=Experiment.Status.RUNNING,
            start_date__lte=now
        ).exclude(end_date__lt=now)
    
    def running(self):
        """
        Get running experiments.
        
        Returns:
            QuerySet
        """
        return self.filter(status=Experiment.Status.RUNNING)
    
    def completed(self):
        """
        Get completed experiments.
        
        Returns:
            QuerySet
        """
        return self.filter(status=Experiment.Status.COMPLETED)
    
    def recent(self, days=30):
        """
        Get experiments from the last N days.
        
        Args:
            days: Number of days
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def search(self, query):
        """
        Search experiments by name or description.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(models.Q(name__icontains=query) | models.Q(description__icontains=query))
