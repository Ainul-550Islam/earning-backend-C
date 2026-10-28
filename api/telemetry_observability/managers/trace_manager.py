"""
Trace manager for Telemetry Observability.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.trace_span import TraceSpan


class TraceManager(models.Manager):
    """
    Custom manager for TraceSpan model.
    """
    
    def by_trace_id(self, trace_id):
        """
        Get spans by trace ID.
        
        Args:
            trace_id: Trace ID
            
        Returns:
            QuerySet
        """
        return self.filter(trace_id=trace_id)
    
    def by_service(self, service):
        """
        Get spans by service.
        
        Args:
            service: Service name
            
        Returns:
            QuerySet
        """
        return self.filter(service=service)
    
    def by_status(self, status):
        """
        Get spans by status.
        
        Args:
            status: Trace status
            
        Returns:
            QuerySet
        """
        return self.filter(status=status)
    
    def errors(self):
        """
        Get error spans.
        
        Returns:
            QuerySet
        """
        return self.filter(status='error')
    
    def slow(self, threshold_ms=5000):
        """
        Get slow spans.
        
        Args:
            threshold_ms: Duration threshold in milliseconds
            
        Returns:
            QuerySet
        """
        return self.filter(duration_ms__gte=threshold_ms)
    
    def recent(self, hours=24):
        """
        Get spans from the last N hours.
        
        Args:
            hours: Number of hours
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(start_time__gte=since)
    
    def by_operation(self, operation_name):
        """
        Get spans by operation name.
        
        Args:
            operation_name: Operation name
            
        Returns:
            QuerySet
        """
        return self.filter(operation_name=operation_name)
