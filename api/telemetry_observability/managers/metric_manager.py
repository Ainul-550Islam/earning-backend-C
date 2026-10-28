"""
Metric manager for Telemetry Observability.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.metric_event import MetricEvent


class MetricManager(models.Manager):
    """
    Custom manager for MetricEvent model.
    """
    
    def by_name(self, name):
        """
        Get metrics by name.
        
        Args:
            name: Metric name
            
        Returns:
            QuerySet
        """
        return self.filter(name=name)
    
    def by_type(self, metric_type):
        """
        Get metrics by type.
        
        Args:
            metric_type: Metric type
            
        Returns:
            QuerySet
        """
        return self.filter(metric_type=metric_type)
    
    def by_service(self, service):
        """
        Get metrics by service.
        
        Args:
            service: Service name
            
        Returns:
            QuerySet
        """
        return self.filter(service=service)
    
    def by_environment(self, environment):
        """
        Get metrics by environment.
        
        Args:
            environment: Environment name
            
        Returns:
            QuerySet
        """
        return self.filter(environment=environment)
    
    def recent(self, hours=24):
        """
        Get metrics from the last N hours.
        
        Args:
            hours: Number of hours
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=since)
    
    def with_value_range(self, min_value, max_value):
        """
        Get metrics within a value range.
        
        Args:
            min_value: Minimum value
            max_value: Maximum value
            
        Returns:
            QuerySet
        """
        return self.filter(value__gte=min_value, value__lte=max_value)
    
    def search(self, query):
        """
        Search metrics by name.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(name__icontains=query)
