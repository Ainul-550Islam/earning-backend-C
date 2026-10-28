"""
Alert manager for Telemetry Observability.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from ..models.alert import Alert


class AlertManager(models.Manager):
    """
    Custom manager for Alert model.
    """
    
    def by_type(self, alert_type):
        """
        Get alerts by type.
        
        Args:
            alert_type: Alert type
            
        Returns:
            QuerySet
        """
        return self.filter(alert_type=alert_type)
    
    def by_severity(self, severity):
        """
        Get alerts by severity.
        
        Args:
            severity: Alert severity
            
        Returns:
            QuerySet
        """
        return self.filter(severity=severity)
    
    def by_status(self, status):
        """
        Get alerts by status.
        
        Args:
            status: Alert status
            
        Returns:
            QuerySet
        """
        return self.filter(status=status)
    
    def by_service(self, service):
        """
        Get alerts by service.
        
        Args:
            service: Service name
            
        Returns:
            QuerySet
        """
        return self.filter(service=service)
    
    def open(self):
        """
        Get open alerts.
        
        Returns:
            QuerySet
        """
        return self.filter(status='open')
    
    def critical(self):
        """
        Get critical alerts.
        
        Returns:
            QuerySet
        """
        return self.filter(severity='critical')
    
    def recent(self, hours=24):
        """
        Get alerts from the last N hours.
        
        Args:
            hours: Number of hours
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(triggered_at__gte=since)
    
    def search(self, query):
        """
        Search alerts by name or message.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(models.Q(name__icontains=query) | models.Q(message__icontains=query))
