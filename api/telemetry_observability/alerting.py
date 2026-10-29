"""
Alerting for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone

from .models.alert import Alert
from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.health_status import HealthStatus
from .exceptions import AlertException, MetricThresholdExceededError


class AlertingService:
    """
    Service for managing alerts.
    """
    
    def __init__(self):
        """
        Initialize the alerting service.
        """
        pass
    
    def create_alert(
        self,
        name: str,
        alert_type: str,
        severity: str,
        message: str,
        condition: Optional[Dict[str, Any]] = None,
        source: str = "system",
        service: str = "default",
        environment: str = "production",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Create a new alert.
        
        Args:
            name: Alert name
            alert_type: Type of alert
            severity: Alert severity
            message: Alert message
            condition: Alert condition
            source: Source of the alert
            service: Service name
            environment: Environment name
            metadata: Additional metadata
            
        Returns:
            Created Alert instance
        """
        return Alert.objects.create(
            name=name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            condition=condition or {},
            source=source,
            service=service,
            environment=environment,
            metadata=metadata or {}
        )
    
    def check_metric_threshold(self, metric: MetricEvent):
        """
        Check if a metric exceeds its threshold and create alert if needed.
        
        Args:
            metric: MetricEvent instance
        """
        # Define default thresholds
        thresholds = {
            'error_rate': 0.05,  # 5%
            'response_time': 1000,  # 1000ms
            'memory_usage': 0.9,  # 90%
        }
        
        # Check if metric name matches any threshold
        for metric_name, threshold in thresholds.items():
            if metric_name in metric.name.lower():
                if metric.value > threshold:
                    self.create_alert(
                        name=f"{metric.name} threshold exceeded",
                        alert_type='metric',
                        severity='warning' if metric.value < threshold * 2 else 'critical',
                        message=f"Metric '{metric.name}' exceeded threshold {threshold} with value {metric.value}",
                        condition={'metric_name': metric.name, 'threshold': threshold, 'actual_value': metric.value},
                        source=metric.source,
                        service=metric.service,
                        environment=metric.environment
                    )
    
    def check_log_threshold(self, log: LogEntry):
        """
        Check if log level exceeds threshold and create alert if needed.
        
        Args:
            log: LogEntry instance
        """
        # Count recent error logs
        since = timezone.now() - timezone.timedelta(minutes=5)
        error_count = LogEntry.objects.filter(
            level='error',
            source=log.source,
            service=log.service,
            timestamp__gte=since
        ).count()
        
        # Alert if more than 10 errors in 5 minutes
        if error_count > 10:
            self.create_alert(
                name=f"High error rate in {log.service}",
                alert_type='log',
                severity='critical',
                message=f"Detected {error_count} error logs in the last 5 minutes",
                condition={'error_count': error_count, 'threshold': 10},
                source=log.source,
                service=log.service,
                environment=log.environment
            )
    
    def check_trace_threshold(self, trace: TraceSpan):
        """
        Check if trace duration exceeds threshold and create alert if needed.
        
        Args:
            trace: TraceSpan instance
        """
        # Define default threshold (5 seconds)
        threshold = 5000  # 5000ms
        
        if trace.duration_ms and trace.duration_ms > threshold:
            self.create_alert(
                name=f"Slow trace detected: {trace.operation_name}",
                alert_type='trace',
                severity='warning',
                message=f"Trace operation '{trace.operation_name}' took {trace.duration_ms}ms, exceeding threshold {threshold}ms",
                condition={'operation_name': trace.operation_name, 'threshold': threshold, 'actual_duration': trace.duration_ms},
                source='tracing',
                service=trace.service,
                environment='production'
            )
    
    def check_health_threshold(self, health: HealthStatus):
        """
        Check if health score is below threshold and create alert if needed.
        
        Args:
            health: HealthStatus instance
        """
        # Define default threshold (70)
        threshold = 70
        
        if health.health_score < threshold:
            self.create_alert(
                name=f"Health check failed: {health.service_name}",
                alert_type='health',
                severity='critical' if health.health_score < 50 else 'warning',
                message=f"Service '{health.service_name}' health score {health.health_score} is below threshold {threshold}",
                condition={'service_name': health.service_name, 'threshold': threshold, 'actual_score': health.health_score},
                source='health_check',
                service=health.service_name,
                environment=health.environment
            )
    
    def get_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        since: Optional[timezone.datetime] = None
    ) -> List[Alert]:
        """
        Get alerts with optional filters.
        
        Args:
            alert_type: Optional alert type filter
            severity: Optional severity filter
            status: Optional status filter
            source: Optional source filter
            service: Optional service filter
            environment: Optional environment filter
            since: Optional start time filter
            
        Returns:
            List of Alert instances
        """
        queryset = Alert.objects.all()
        
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if source:
            queryset = queryset.filter(source=source)
        
        if service:
            queryset = queryset.filter(service=service)
        
        if environment:
            queryset = queryset.filter(environment=environment)
        
        if since:
            queryset = queryset.filter(triggered_at__gte=since)
        
        return list(queryset.order_by('-triggered_at'))
    
    def acknowledge_alert(self, alert_id: int, user: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User who is acknowledging
            
        Returns:
            True if successful
        """
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.acknowledge(user)
            return True
        except Alert.DoesNotExist:
            return False
    
    def resolve_alert(self, alert_id: int) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if successful
        """
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.resolve()
            return True
        except Alert.DoesNotExist:
            return False
    
    def get_open_alerts(self, service: Optional[str] = None) -> List[Alert]:
        """Return all open alerts, optionally filtered by service."""
        qs = Alert.objects.open()
        if service:
            qs = qs.filter(service=service)
        return list(qs)

    def get_critical_alerts(self, service: Optional[str] = None) -> List[Alert]:
        """Return all critical-severity alerts, optionally filtered by service."""
        qs = Alert.objects.critical()
        if service:
            qs = qs.filter(service=service)
        return list(qs)

    def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get alert statistics for the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with alert statistics
        """
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        total_alerts = Alert.objects.filter(triggered_at__gte=since).count()
        open_alerts = Alert.objects.filter(
            triggered_at__gte=since,
            status='open'
        ).count()
        resolved_alerts = Alert.objects.filter(
            triggered_at__gte=since,
            status='resolved'
        ).count()
        
        # Count by severity
        critical_alerts = Alert.objects.filter(
            triggered_at__gte=since,
            severity='critical'
        ).count()
        warning_alerts = Alert.objects.filter(
            triggered_at__gte=since,
            severity='warning'
        ).count()
        
        return {
            'period_hours': hours,
            'total_alerts': total_alerts,
            'open_alerts': open_alerts,
            'resolved_alerts': resolved_alerts,
            'critical_alerts': critical_alerts,
            'warning_alerts': warning_alerts
        }


class AlertRule:
    """
    Rule for triggering alerts.
    """
    
    def __init__(
        self,
        name: str,
        condition: Dict[str, Any],
        severity: str = 'warning',
        alert_type: str = 'custom'
    ):
        """
        Initialize an alert rule.
        
        Args:
            name: Rule name
            condition: Condition dictionary
            severity: Alert severity
            alert_type: Type of alert
        """
        self.name = name
        self.condition = condition
        self.severity = severity
        self.alert_type = alert_type
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        Evaluate the rule against data.
        
        Args:
            data: Data to evaluate
            
        Returns:
            True if condition is met
        """
        # Simple evaluation - can be extended
        for key, value in self.condition.items():
            if key not in data:
                return False
            if data[key] != value and not self._compare(data[key], value):
                return False
        return True
    
    def _compare(self, actual, expected) -> bool:
        """
        Compare actual value with expected value.
        
        Args:
            actual: Actual value
            expected: Expected value
            
        Returns:
            True if condition is met
        """
        if isinstance(expected, dict):
            # Handle comparison operators
            if 'gt' in expected:
                return actual > expected['gt']
            if 'lt' in expected:
                return actual < expected['lt']
            if 'gte' in expected:
                return actual >= expected['gte']
            if 'lte' in expected:
                return actual <= expected['lte']
        return actual == expected
