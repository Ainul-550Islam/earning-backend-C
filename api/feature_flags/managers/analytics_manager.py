"""
Analytics manager for Feature Flags & A/B Testing.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.flag_analytics import FlagAnalytics


class AnalyticsManager(models.Manager):
    """
    Custom manager for FlagAnalytics model.
    """
    
    def by_flag(self, flag_id):
        """
        Get analytics by flag.
        
        Args:
            flag_id: Flag ID
            
        Returns:
            QuerySet
        """
        return self.filter(flag_id=flag_id)
    
    def by_variant(self, variant_id):
        """
        Get analytics by variant.
        
        Args:
            variant_id: Variant ID
            
        Returns:
            QuerySet
        """
        return self.filter(variant_id=variant_id)
    
    def by_date(self, date):
        """
        Get analytics by date.
        
        Args:
            date: Date
            
        Returns:
            QuerySet
        """
        return self.filter(date=date)
    
    def by_environment(self, environment):
        """
        Get analytics by environment.
        
        Args:
            environment: Environment name
            
        Returns:
            QuerySet
        """
        return self.filter(environment=environment)
    
    def recent(self, days=7):
        """
        Get analytics from the last N days.
        
        Args:
            days: Number of days
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(days=days)
        return self.filter(date__gte=since)
    
    def by_date_range(self, start_date, end_date):
        """
        Get analytics within a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            QuerySet
        """
        return self.filter(date__gte=start_date, date__lte=end_date)
