"""
Feature Flag manager for Feature Flags & A/B Testing.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.feature_flag import FeatureFlag


class FeatureFlagManager(models.Manager):
    """
    Custom manager for FeatureFlag model.
    """
    
    def by_name(self, name):
        """
        Get flags by name.
        
        Args:
            name: Flag name
            
        Returns:
            QuerySet
        """
        return self.filter(name=name)
    
    def by_type(self, flag_type):
        """
        Get flags by type.
        
        Args:
            flag_type: Flag type
            
        Returns:
            QuerySet
        """
        return self.filter(flag_type=flag_type)
    
    def by_status(self, status):
        """
        Get flags by status.
        
        Args:
            status: Flag status
            
        Returns:
            QuerySet
        """
        return self.filter(status=status)
    
    def by_environment(self, environment):
        """
        Get flags by environment.
        
        Args:
            environment: Environment name
            
        Returns:
            QuerySet
        """
        return self.filter(environment=environment)
    
    def active(self):
        """
        Get active flags.
        
        Returns:
            QuerySet
        """
        return self.filter(status=FeatureFlag.Status.ACTIVE)
    
    def draft(self):
        """
        Get draft flags.
        
        Returns:
            QuerySet
        """
        return self.filter(status=FeatureFlag.Status.DRAFT)
    
    def archived(self):
        """
        Get archived flags.
        
        Returns:
            QuerySet
        """
        return self.filter(status=FeatureFlag.Status.ARCHIVED)
    
    def recent(self, days=30):
        """
        Get flags from the last N days.
        
        Args:
            days: Number of days
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def search(self, query):
        """
        Search flags by name or description.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(models.Q(name__icontains=query) | models.Q(description__icontains=query))
