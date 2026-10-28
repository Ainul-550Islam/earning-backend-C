"""
Django model managers for Telemetry Observability.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta

from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.alert import Alert
from .models.health_status import HealthStatus


class MetricEventManager(models.Manager):
    """
    Custom manager for MetricEvent.
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


class LogEntryManager(models.Manager):
    """
    Custom manager for LogEntry.
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
            query: Search query
            
        Returns:
            QuerySet
        """
        return self.filter(message__icontains=query)


class TraceSpanManager(models.Manager):
    """
    Custom manager for TraceSpan.
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


class AlertManager(models.Manager):
    """
    Custom manager for Alert.
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


class HealthStatusManager(models.Manager):
    """
    Custom manager for HealthStatus.
    """
    
    def by_service(self, service_name):
        """
        Get health statuses by service.
        
        Args:
            service_name: Service name
            
        Returns:
            QuerySet
        """
        return self.filter(service_name=service_name)
    
    def by_status(self, status):
        """
        Get health statuses by status.
        
        Args:
            status: Health status
            
        Returns:
            QuerySet
        """
        return self.filter(status=status)
    
    def by_environment(self, environment):
        """
        Get health statuses by environment.
        
        Args:
            environment: Environment name
            
        Returns:
            QuerySet
        """
        return self.filter(environment=environment)
    
    def healthy(self):
        """
        Get healthy statuses.
        
        Returns:
            QuerySet
        """
        return self.filter(status='healthy')
    
    def unhealthy(self):
        """
        Get unhealthy statuses.
        
        Returns:
            QuerySet
        """
        return self.filter(status__in=['degraded', 'unhealthy'])
    
    def critical(self):
        """
        Get critical health issues.
        
        Returns:
            QuerySet
        """
        return self.filter(status='unhealthy', health_score__lt=50)
    
    def recent(self, hours=24):
        """
        Get health statuses from the last N hours.
        
        Args:
            hours: Number of hours
            
        Returns:
            QuerySet
        """
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(last_check__gte=since)
