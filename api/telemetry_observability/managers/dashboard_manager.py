"""
Dashboard manager for Telemetry Observability.
"""
from django.db import models

from ..models.dashboard_widget import DashboardWidget


class DashboardManager(models.Manager):
    """
    Custom manager for DashboardWidget model.
    """
    
    def by_type(self, widget_type):
        """
        Get widgets by type.
        
        Args:
            widget_type: Widget type
            
        Returns:
            QuerySet
        """
        return self.filter(widget_type=widget_type)
    
    def by_data_source(self, data_source):
        """
        Get widgets by data source.
        
        Args:
            data_source: Data source
            
        Returns:
            QuerySet
        """
        return self.filter(data_source=data_source)
    
    def by_dashboard(self, dashboard_id):
        """
        Get widgets by dashboard ID.
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            QuerySet
        """
        return self.filter(dashboard_id=dashboard_id)
    
    def active(self):
        """
        Get active widgets.
        
        Returns:
            QuerySet
        """
        return self.filter(is_active=True)
    
    def inactive(self):
        """
        Get inactive widgets.
        
        Returns:
            QuerySet
        """
        return self.filter(is_active=False)
    
    def search(self, query):
        """
        Search widgets by name.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(name__icontains=query)
