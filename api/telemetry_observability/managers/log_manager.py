"""
Log manager for Telemetry Observability.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.log_entry import LogEntry


class LogManager(models.Manager):
    """
    Custom manager for LogEntry model.
    """
    
    def by_level(self, level):
        """
        Get logs by level.
        
        Args:
            level: Log level
            
        Returns:
            QuerySet
        """
        return self.filter(level=level)
    
    def by_service(self, service):
        """
        Get logs by service.
        
        Args:
            service: Service name
            
        Returns:
            QuerySet
        """
        return self.filter(service=service)
    
    def by_environment(self, environment):
        """
        Get logs by environment.
        
        Args:
            environment: Environment name
            
        Returns:
            QuerySet
        """
        return self.filter(environment=environment)
    
    def errors(self):
        """
        Get error logs.
        
        Returns:
            QuerySet
        """
        return self.filter(level='error')
    
    def critical(self):
        """
        Get critical logs.
        
        Returns:
            QuerySet
        """
        return self.filter(level='critical')
    
    def recent(self, hours=24):
        """
        Get logs from the last N hours.
        
        Args:
            hours: Number of hours
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=since)
    
    def search(self, query):
        """
        Search logs by message.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(message__icontains=query)
    
    def by_logger(self, logger_name):
        """
        Get logs by logger name.
        
        Args:
            logger_name: Logger name
            
        Returns:
            QuerySet
        """
        return self.filter(logger_name=logger_name)
