"""
monitoring.py – Monitoring and alerting for postback module.

Provides comprehensive monitoring functionality including:
- System health monitoring
- Performance metrics
- Alert management
- Dashboard data collection
"""
from django.db import models
import logging
import psutil
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from django.conf import settings

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status enumeration."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class MetricType(Enum):
    """Metric type enumeration."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """Metric data structure."""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=timezone.now)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'value': self.value,
            'metric_type': self.metric_type.value,
            'timestamp': self.timestamp.isoformat(),
            'labels': self.labels,
            'unit': self.unit,
            'description': self.description,
        }


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    source: str
    created_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def resolve(self):
        """Resolve alert."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = timezone.now()
    
    def suppress(self):
        """Suppress alert."""
        self.status = AlertStatus.SUPPRESSED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'severity': self.severity.value,
            'status': self.status.value,
            'message': self.message,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'metadata': self.metadata,
        }


class MetricCollector:
    """
    Collector for system and application metrics.
    
    Gathers metrics from various sources including
    database, cache, and system resources.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics: List[Metric] = []
    
    def collect_system_metrics(self) -> List[Metric]:
        """Collect system-level metrics."""
        metrics = []
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(Metric(
                name="system_cpu_percent",
                value=cpu_percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                description="System CPU usage percentage"
            ))
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.append(Metric(
                name="system_memory_percent",
                value=memory.percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                description="System memory usage percentage"
            ))
            
            metrics.append(Metric(
                name="system_memory_used_bytes",
                value=memory.used,
                metric_type=MetricType.GAUGE,
                unit="bytes",
                description="System memory used in bytes"
            ))
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics.append(Metric(
                name="system_disk_percent",
                value=disk.percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                description="System disk usage percentage"
            ))
            
            # Network metrics
            network = psutil.net_io_counters()
            metrics.append(Metric(
                name="system_network_bytes_sent",
                value=network.bytes_sent,
                metric_type=MetricType.COUNTER,
                unit="bytes",
                description="System network bytes sent"
            ))
            
            metrics.append(Metric(
                name="system_network_bytes_recv",
                value=network.bytes_recv,
                metric_type=MetricType.COUNTER,
                unit="bytes",
                description="System network bytes received"
            ))
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {str(e)}")
        
        return metrics
    
    def collect_database_metrics(self) -> List[Metric]:
        """Collect database metrics."""
        metrics = []
        
        try:
            with connection.cursor() as cursor:
                # Database size
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as size,
                        pg_database_size(current_database()) as size_bytes
                """)
                result = cursor.fetchone()
                if result:
                    size_bytes = result[1]
                    metrics.append(Metric(
                        name="database_size_bytes",
                        value=size_bytes,
                        metric_type=MetricType.GAUGE,
                        unit="bytes",
                        description="Database size in bytes"
                    ))
                
                # Connection count
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
                metrics.append(Metric(
                    name="database_active_connections",
                    value=active_connections,
                    metric_type=MetricType.GAUGE,
                    unit="count",
                    description="Active database connections"
                ))
                
                # Table counts
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                """)
                table_stats = cursor.fetchall()
                
                for stat in table_stats:
                    table_name = stat[1]
                    metrics.append(Metric(
                        name="database_table_inserts",
                        value=stat[2],
                        metric_type=MetricType.COUNTER,
                        unit="count",
                        description=f"Table {table_name} inserts",
                        labels={'table': table_name, 'schema': stat[0]}
                    ))
                    
                    metrics.append(Metric(
                        name="database_table_updates",
                        value=stat[3],
                        metric_type=MetricType.COUNTER,
                        unit="count",
                        description=f"Table {table_name} updates",
                        labels={'table': table_name, 'schema': stat[0]}
                    ))
                    
                    metrics.append(Metric(
                        name="database_table_deletes",
                        value=stat[4],
                        metric_type=MetricType.COUNTER,
                        unit="count",
                        description=f"Table {table_name} deletes",
                        labels={'table': table_name, 'schema': stat[0]}
                    ))
        
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {str(e)}")
        
        return metrics
    
    def collect_cache_metrics(self) -> List[Metric]:
        """Collect cache metrics."""
        metrics = []
        
        try:
            # Cache hit/miss ratio
            cache_keys = cache.keys("postback_*")
            hit_count = 0
            miss_count = 0
            
            for key in cache_keys[:100]:  # Sample first 100 keys
                if cache.get(key) is not None:
                    hit_count += 1
                else:
                    miss_count += 1
            
            total_requests = hit_count + miss_count
            if total_requests > 0:
                hit_rate = (hit_count / total_requests) * 100
                metrics.append(Metric(
                    name="cache_hit_rate",
                    value=hit_rate,
                    metric_type=MetricType.GAUGE,
                    unit="percent",
                    description="Cache hit rate percentage"
                ))
            
            metrics.append(Metric(
                name="cache_keys_count",
                value=len(cache_keys),
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Total cache keys"
            ))
        
        except Exception as e:
            self.logger.error(f"Error collecting cache metrics: {str(e)}")
        
        return metrics
    
    def collect_application_metrics(self) -> List[Metric]:
        """Collect application-specific metrics."""
        metrics = []
        
        try:
            # Postback metrics
            total_postbacks = PostbackLog.objects.count()
            metrics.append(Metric(
                name="postback_total_count",
                value=total_postbacks,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Total postback count"
            ))
            
            # Postback status breakdown
            status_counts = {}
            for status in ['received', 'rewarded', 'rejected', 'failed']:
                count = PostbackLog.objects.filter(status=status).count()
                status_counts[status] = count
                metrics.append(Metric(
                    name=f"postback_status_{status}_count",
                    value=count,
                    metric_type=MetricType.GAUGE,
                    unit="count",
                    description=f"Postback {status} count",
                    labels={'status': status}
                ))
            
            # Recent postbacks (last hour)
            one_hour_ago = timezone.now() - timedelta(hours=1)
            recent_postbacks = PostbackLog.objects.filter(received_at__gte=one_hour_ago).count()
            metrics.append(Metric(
                name="postback_recent_hour_count",
                value=recent_postbacks,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Postbacks in last hour"
            ))
            
            # Network metrics
            total_networks = NetworkPostbackConfig.objects.count()
            active_networks = NetworkPostbackConfig.objects.filter(is_active=True).count()
            
            metrics.append(Metric(
                name="network_total_count",
                value=total_networks,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Total networks"
            ))
            
            metrics.append(Metric(
                name="network_active_count",
                value=active_networks,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Active networks"
            ))
            
            # Insight metrics
            total_insights = PostbackInsight.objects.count()
            anomaly_insights = PostbackInsight.objects.filter(anomaly_detected=True).count()
            
            metrics.append(Metric(
                name="insight_total_count",
                value=total_insights,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Total insights"
            ))
            
            metrics.append(Metric(
                name="insight_anomaly_count",
                value=anomaly_insights,
                metric_type=MetricType.GAUGE,
                unit="count",
                description="Insights with anomalies"
            ))
            
            # Average health score
            if total_insights > 0:
                avg_health = PostbackInsight.objects.aggregate(
                    avg_score=models.Avg('health_score')
                )['avg_score'] or 0
                
                metrics.append(Metric(
                    name="insight_avg_health_score",
                    value=float(avg_health),
                    metric_type=MetricType.GAUGE,
                    unit="score",
                    description="Average insight health score"
                ))
        
        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {str(e)}")
        
        return metrics
    
    def collect_all_metrics(self) -> List[Metric]:
        """Collect all metrics."""
        all_metrics = []
        
        all_metrics.extend(self.collect_system_metrics())
        all_metrics.extend(self.collect_database_metrics())
        all_metrics.extend(self.collect_cache_metrics())
        all_metrics.extend(self.collect_application_metrics())
        
        self.metrics = all_metrics
        return all_metrics


class AlertManager:
    """
    Manager for alerts and alerting rules.
    
    Handles alert creation, evaluation, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules = self._setup_default_rules()
        self.alert_history: List[Alert] = []
    
    def _setup_default_rules(self) -> List[Dict[str, Any]]:
        """Setup default alerting rules."""
        return [
            {
                'name': 'high_cpu_usage',
                'condition': lambda metrics: self._get_metric_value(metrics, 'system_cpu_percent', 0) > 80,
                'severity': AlertSeverity.HIGH,
                'message': 'CPU usage is above 80%',
                'cooldown': timedelta(minutes=5),
            },
            {
                'name': 'high_memory_usage',
                'condition': lambda metrics: self._get_metric_value(metrics, 'system_memory_percent', 0) > 85,
                'severity': AlertSeverity.HIGH,
                'message': 'Memory usage is above 85%',
                'cooldown': timedelta(minutes=5),
            },
            {
                'name': 'database_connection_error',
                'condition': lambda metrics: self._get_metric_value(metrics, 'database_active_connections', -1) == -1,
                'severity': AlertSeverity.CRITICAL,
                'message': 'Database connection error detected',
                'cooldown': timedelta(minutes=1),
            },
            {
                'name': 'low_cache_hit_rate',
                'condition': lambda metrics: self._get_metric_value(metrics, 'cache_hit_rate', 100) < 70,
                'severity': AlertSeverity.MEDIUM,
                'message': 'Cache hit rate is below 70%',
                'cooldown': timedelta(hours=1),
            },
            {
                'name': 'high_rejection_rate',
                'condition': lambda metrics: self._calculate_rejection_rate(metrics) > 50,
                'severity': AlertSeverity.HIGH,
                'message': 'Postback rejection rate is above 50%',
                'cooldown': timedelta(minutes=15),
            },
            {
                'name': 'no_recent_postbacks',
                'condition': lambda metrics: self._get_metric_value(metrics, 'postback_recent_hour_count', 0) == 0,
                'severity': AlertSeverity.MEDIUM,
                'message': 'No postbacks received in the last hour',
                'cooldown': timedelta(minutes=30),
            },
            {
                'name': 'multiple_anomalies',
                'condition': lambda metrics: self._get_metric_value(metrics, 'insight_anomaly_count', 0) > 5,
                'severity': AlertSeverity.HIGH,
                'message': 'Multiple anomalies detected in insights',
                'cooldown': timedelta(minutes=30),
            },
        ]
    
    def _get_metric_value(self, metrics: List[Metric], metric_name: str, default: Any = 0) -> Any:
        """Get metric value by name."""
        for metric in metrics:
            if metric.name == metric_name:
                return metric.value
        return default
    
    def _calculate_rejection_rate(self, metrics: List[Metric]) -> float:
        """Calculate rejection rate from metrics."""
        total_count = self._get_metric_value(metrics, 'postback_total_count', 0)
        rejected_count = self._get_metric_value(metrics, 'postback_status_rejected_count', 0)
        
        if total_count == 0:
            return 0.0
        
        return (rejected_count / total_count) * 100
    
    def evaluate_alerts(self, metrics: List[Metric]) -> List[Alert]:
        """
        Evaluate alert rules against metrics.
        
        Args:
            metrics: List of metrics to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for rule in self.alert_rules:
            try:
                # Check cooldown
                last_alert = self._get_last_alert(rule['name'])
                if last_alert and last_alert.status == AlertStatus.ACTIVE:
                    cooldown_end = last_alert.created_at + rule['cooldown']
                    if timezone.now() < cooldown_end:
                        continue
                
                # Evaluate condition
                if rule['condition'](metrics):
                    alert = Alert(
                        id=self._generate_alert_id(),
                        name=rule['name'],
                        severity=rule['severity'],
                        status=AlertStatus.ACTIVE,
                        message=rule['message'],
                        source='monitoring_system',
                        metadata={
                            'rule_name': rule['name'],
                            'triggered_at': timezone.now().isoformat(),
                            'metrics': {m.name: m.value for m in metrics},
                        }
                    )
                    
                    self.alerts[alert.id] = alert
                    self.alert_history.append(alert)
                    triggered_alerts.append(alert)
                    
                    self.logger.warning(f"Alert triggered: {rule['name']} - {rule['message']}")
            
            except Exception as e:
                self.logger.error(f"Error evaluating alert rule {rule['name']}: {str(e)}")
        
        return triggered_alerts
    
    def _get_last_alert(self, rule_name: str) -> Optional[Alert]:
        """Get last alert for rule."""
        for alert in reversed(self.alert_history):
            if alert.name == rule_name:
                return alert
        return None
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        import uuid
        return f"alert_{uuid.uuid4().hex[:12]}"
    
    def create_manual_alert(self, name: str, severity: AlertSeverity, message: str, 
                          source: str = "manual", metadata: Dict[str, Any] = None) -> Alert:
        """
        Create manual alert.
        
        Args:
            name: Alert name
            severity: Alert severity
            message: Alert message
            source: Alert source
            metadata: Additional metadata
            
        Returns:
            Created alert
        """
        alert = Alert(
            id=self._generate_alert_id(),
            name=name,
            severity=severity,
            status=AlertStatus.ACTIVE,
            message=message,
            source=source,
            metadata=metadata or {}
        )
        
        self.alerts[alert.id] = alert
        self.alert_history.append(alert)
        
        self.logger.warning(f"Manual alert created: {name} - {message}")
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if resolved
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False
        
        alert.resolve()
        self.logger.info(f"Alert resolved: {alert_id}")
        return True
    
    def suppress_alert(self, alert_id: str) -> bool:
        """
        Suppress alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if suppressed
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False
        
        alert.suppress()
        self.logger.info(f"Alert suppressed: {alert_id}")
        return True
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active alerts."""
        return [alert for alert in self.alerts.values() if alert.status == AlertStatus.ACTIVE]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        total_alerts = len(self.alert_history)
        active_alerts = len(self.get_active_alerts())
        
        severity_counts = {}
        for alert in self.alert_history:
            severity = alert.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'severity_counts': severity_counts,
            'recent_alerts': [
                alert.to_dict() for alert in self.alert_history[-10:]
            ],
        }


class MonitoringDashboard:
    """
    Dashboard for monitoring data.
    
    Provides aggregated data for monitoring dashboards
    and visualization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metric_collector = MetricCollector()
        self.alert_manager = AlertManager()
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Returns:
            Dashboard data dictionary
        """
        try:
            # Collect metrics
            metrics = self.metric_collector.collect_all_metrics()
            
            # Evaluate alerts
            alerts = self.alert_manager.evaluate_alerts(metrics)
            
            # Get system health
            health_status = self._calculate_health_status(metrics, alerts)
            
            # Get performance summary
            performance_summary = self._calculate_performance_summary(metrics)
            
            return {
                'timestamp': timezone.now().isoformat(),
                'health_status': health_status,
                'metrics': [metric.to_dict() for metric in metrics],
                'alerts': [alert.to_dict() for alert in alerts],
                'performance_summary': performance_summary,
                'alert_statistics': self.alert_manager.get_alert_statistics(),
            }
        
        except Exception as e:
            self.logger.error(f"Error generating dashboard data: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'health_status': 'error',
                'metrics': [],
                'alerts': [],
                'performance_summary': {},
                'alert_statistics': {},
            }
    
    def _calculate_health_status(self, metrics: List[Metric], alerts: List[Alert]) -> str:
        """Calculate overall system health status."""
        critical_alerts = [alert for alert in alerts if alert.severity == AlertSeverity.CRITICAL]
        high_alerts = [alert for alert in alerts if alert.severity == AlertSeverity.HIGH]
        
        if critical_alerts:
            return 'critical'
        elif high_alerts:
            return 'warning'
        
        # Check system metrics
        cpu_usage = self._get_metric_value(metrics, 'system_cpu_percent', 0)
        memory_usage = self._get_metric_value(metrics, 'system_memory_percent', 0)
        
        if cpu_usage > 90 or memory_usage > 90:
            return 'warning'
        elif cpu_usage > 70 or memory_usage > 70:
            return 'degraded'
        
        return 'healthy'
    
    def _calculate_performance_summary(self, metrics: List[Metric]) -> Dict[str, Any]:
        """Calculate performance summary."""
        return {
            'system_performance': {
                'cpu_usage': self._get_metric_value(metrics, 'system_cpu_percent', 0),
                'memory_usage': self._get_metric_value(metrics, 'system_memory_percent', 0),
                'disk_usage': self._get_metric_value(metrics, 'system_disk_percent', 0),
            },
            'application_performance': {
                'total_postbacks': self._get_metric_value(metrics, 'postback_total_count', 0),
                'recent_postbacks': self._get_metric_value(metrics, 'postback_recent_hour_count', 0),
                'active_networks': self._get_metric_value(metrics, 'network_active_count', 0),
                'anomaly_count': self._get_metric_value(metrics, 'insight_anomaly_count', 0),
                'avg_health_score': self._get_metric_value(metrics, 'insight_avg_health_score', 0),
            },
            'infrastructure_performance': {
                'cache_hit_rate': self._get_metric_value(metrics, 'cache_hit_rate', 100),
                'database_connections': self._get_metric_value(metrics, 'database_active_connections', 0),
                'cache_keys': self._get_metric_value(metrics, 'cache_keys_count', 0),
            },
        }
    
    def _get_metric_value(self, metrics: List[Metric], metric_name: str, default: Any = 0) -> Any:
        """Get metric value by name."""
        for metric in metrics:
            if metric.name == metric_name:
                return metric.value
        return default


# Global monitoring instances
metric_collector = MetricCollector()
alert_manager = AlertManager()
monitoring_dashboard = MonitoringDashboard()


# Convenience functions
def collect_metrics() -> List[Metric]:
    """Collect all monitoring metrics."""
    return metric_collector.collect_all_metrics()


def evaluate_alerts() -> List[Alert]:
    """Evaluate all alert rules."""
    metrics = metric_collector.collect_all_metrics()
    return alert_manager.evaluate_alerts(metrics)


def get_dashboard_data() -> Dict[str, Any]:
    """Get monitoring dashboard data."""
    return monitoring_dashboard.get_dashboard_data()


def create_alert(name: str, severity: AlertSeverity, message: str, 
                source: str = "manual", metadata: Dict[str, Any] = None) -> Alert:
    """Create manual alert."""
    return alert_manager.create_manual_alert(name, severity, message, source, metadata)


def resolve_alert(alert_id: str) -> bool:
    """Resolve alert."""
    return alert_manager.resolve_alert(alert_id)


def get_active_alerts() -> List[Alert]:
    """Get active alerts."""
    return alert_manager.get_active_alerts()


def get_alert_statistics() -> Dict[str, Any]:
    """Get alert statistics."""
    return alert_manager.get_alert_statistics()


def get_system_health() -> str:
    """Get system health status."""
    dashboard_data = monitoring_dashboard.get_dashboard_data()
    return dashboard_data.get('health_status', 'unknown')


# Monitoring utilities
def add_alert_rule(name: str, condition: callable, severity: AlertSeverity, 
                   message: str, cooldown: timedelta = timedelta(minutes=5)):
    """Add custom alert rule."""
    rule = {
        'name': name,
        'condition': condition,
        'severity': severity,
        'message': message,
        'cooldown': cooldown,
    }
    
    alert_manager.alert_rules.append(rule)
    logger.info(f"Added alert rule: {name}")


def remove_alert_rule(name: str):
    """Remove alert rule."""
    alert_manager.alert_rules = [rule for rule in alert_manager.alert_rules if rule['name'] != name]
    logger.info(f"Removed alert rule: {name}")


# Monitoring health check
def check_monitoring_health() -> Dict[str, Any]:
    """Check monitoring system health."""
    health_status = {
        'overall': 'healthy',
        'metric_collector': 'healthy',
        'alert_manager': 'healthy',
        'dashboard': 'healthy',
        'issues': [],
    }
    
    # Test metric collector
    try:
        metrics = metric_collector.collect_system_metrics()
        health_status['metric_collector'] = 'healthy'
    except Exception as e:
        health_status['metric_collector'] = 'error'
        health_status['issues'].append(f"Metric collector error: {str(e)}")
    
    # Test alert manager
    try:
        stats = alert_manager.get_alert_statistics()
        health_status['alert_manager'] = 'healthy'
    except Exception as e:
        health_status['alert_manager'] = 'error'
        health_status['issues'].append(f"Alert manager error: {str(e)}")
    
    # Test dashboard
    try:
        dashboard_data = monitoring_dashboard.get_dashboard_data()
        health_status['dashboard'] = 'healthy'
    except Exception as e:
        health_status['dashboard'] = 'error'
        health_status['issues'].append(f"Dashboard error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
