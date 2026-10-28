"""
Security Monitoring Module
Real-time monitoring and alerting system
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.conf import settings
from django.dispatch import Signal

from .models import SecurityLog, SecurityIncident, ThreatIntelligence
from .utils import SecurityUtils
from .helpers import SecurityMetrics

User = get_user_model()
logger = logging.getLogger('security.monitoring')


class AlertLevel:
    """Alert severity levels"""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class MonitorType:
    """Monitor types"""
    THRESHOLD = 'threshold'
    ANOMALY = 'anomaly'
    RATE_LIMIT = 'rate_limit'
    HEALTH_CHECK = 'health_check'
    CUSTOM = 'custom'


class MonitorStatus:
    """Monitor status"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ERROR = 'error'
    MAINTENANCE = 'maintenance'


class SecurityMonitor:
    """Base security monitor class"""
    
    def __init__(self, name: str, monitor_type: str, interval: int = 60):
        self.name = name
        self.monitor_type = monitor_type
        self.interval = interval
        self.status = MonitorStatus.INACTIVE
        self.last_run = None
        self.last_error = None
        self.alert_handlers = []
        self._running = False
        self._thread = None
    
    def start(self):
        """Start the monitor"""
        if self.status == MonitorStatus.ACTIVE:
            return
        
        self.status = MonitorStatus.ACTIVE
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Started security monitor: {self.name}")
    
    def stop(self):
        """Stop the monitor"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        self.status = MonitorStatus.INACTIVE
        logger.info(f"Stopped security monitor: {self.name}")
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler"""
        self.alert_handlers.append(handler)
    
    def check(self) -> Dict[str, Any]:
        """Perform monitoring check - override in subclasses"""
        return {'status': 'ok', 'message': 'Monitor check completed'}
    
    def _run_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                start_time = time.time()
                
                # Perform check
                result = self.check()
                
                # Update status
                self.last_run = timezone.now()
                self.last_error = None
                
                # Process results
                self._process_result(result)
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.last_error = str(e)
                self.status = MonitorStatus.ERROR
                logger.error(f"Monitor {self.name} error: {e}")
                
                # Send error alert
                self._send_alert(AlertLevel.ERROR, f"Monitor error: {e}")
                
                time.sleep(self.interval)
    
    def _process_result(self, result: Dict[str, Any]):
        """Process monitoring result"""
        if result.get('status') != 'ok':
            # Send alert
            level = result.get('level', AlertLevel.WARNING)
            message = result.get('message', 'Monitor alert')
            self._send_alert(level, message, result)
    
    def _send_alert(self, level: str, message: str, data: Dict[str, Any] = None):
        """Send alert to handlers"""
        alert_data = {
            'monitor': self.name,
            'level': level,
            'message': message,
            'timestamp': timezone.now().isoformat(),
            'data': data or {}
        }
        
        for handler in self.alert_handlers:
            try:
                handler(alert_data)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status"""
        return {
            'name': self.name,
            'type': self.monitor_type,
            'status': self.status,
            'interval': self.interval,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_error': self.last_error,
            'is_running': self._running
        }


class ThresholdMonitor(SecurityMonitor):
    """Threshold-based monitor"""
    
    def __init__(self, name: str, metric_name: str, threshold: float, 
                 comparison: str = 'greater_than', **kwargs):
        super().__init__(name, MonitorType.THRESHOLD, **kwargs)
        self.metric_name = metric_name
        self.threshold = threshold
        self.comparison = comparison
    
    def check(self) -> Dict[str, Any]:
        """Check threshold condition"""
        try:
            # Get current metric value
            current_value = self._get_metric_value()
            
            # Check condition
            triggered = self._check_condition(current_value)
            
            if triggered:
                return {
                    'status': 'alert',
                    'level': AlertLevel.WARNING,
                    'message': f"Threshold exceeded: {self.metric_name} = {current_value} (threshold: {self.threshold})",
                    'current_value': current_value,
                    'threshold': self.threshold
                }
            else:
                return {
                    'status': 'ok',
                    'message': f"Threshold normal: {self.metric_name} = {current_value}"
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'level': AlertLevel.ERROR,
                'message': f"Threshold check error: {e}"
            }
    
    def _get_metric_value(self) -> float:
        """Get current metric value - override in subclasses"""
        return 0.0
    
    def _check_condition(self, value: float) -> bool:
        """Check if condition is met"""
        if self.comparison == 'greater_than':
            return value > self.threshold
        elif self.comparison == 'less_than':
            return value < self.threshold
        elif self.comparison == 'equal':
            return value == self.threshold
        elif self.comparison == 'greater_equal':
            return value >= self.threshold
        elif self.comparison == 'less_equal':
            return value <= self.threshold
        else:
            return False


class SecurityEventMonitor(ThresholdMonitor):
    """Monitor for security events"""
    
    def __init__(self, name: str, event_type: str, threshold: int, 
                 time_window_minutes: int = 5, **kwargs):
        super().__init__(
            name, 
            f"security_event_{event_type}", 
            threshold, 
            'greater_than',
            interval=60,
            **kwargs
        )
        self.event_type = event_type
        self.time_window_minutes = time_window_minutes
    
    def _get_metric_value(self) -> float:
        """Get count of events in time window"""
        cutoff_time = timezone.now() - timedelta(minutes=self.time_window_minutes)
        
        count = SecurityLog.objects.filter(
            security_type=self.event_type,
            created_at__gte=cutoff_time
        ).count()
        
        return float(count)


class FailedLoginMonitor(SecurityEventMonitor):
    """Monitor for failed login attempts"""
    
    def __init__(self, threshold: int = 10, time_window_minutes: int = 5):
        super().__init__(
            'failed_login_monitor',
            'login_failed',
            threshold,
            time_window_minutes
        )


class HighRiskEventMonitor(SecurityEventMonitor):
    """Monitor for high risk events"""
    
    def __init__(self, threshold: int = 5, time_window_minutes: int = 5):
        super().__init__(
            'high_risk_monitor',
            'high_risk_event',
            threshold,
            time_window_minutes
        )
    
    def _get_metric_value(self) -> float:
        """Get count of high risk events"""
        cutoff_time = timezone.now() - timedelta(minutes=self.time_window_minutes)
        
        count = SecurityLog.objects.filter(
            risk_score__gte=70,
            created_at__gte=cutoff_time
        ).count()
        
        return float(count)


class IncidentMonitor(ThresholdMonitor):
    """Monitor for security incidents"""
    
    def __init__(self, threshold: int = 5):
        super().__init__(
            'incident_monitor',
            'open_incidents',
            threshold,
            'greater_than',
            interval=300  # 5 minutes
        )
    
    def _get_metric_value(self) -> float:
        """Get count of open incidents"""
        count = SecurityIncident.objects.filter(status='open').count()
        return float(count)


class ThreatMonitor(ThresholdMonitor):
    """Monitor for threat intelligence"""
    
    def __init__(self, threshold: int = 10):
        super().__init__(
            'threat_monitor',
            'active_threats',
            threshold,
            'greater_than',
            interval=600  # 10 minutes
        )
    
    def _get_metric_value(self) -> float:
        """Get count of active threats"""
        count = ThreatIntelligence.objects.filter(is_active=True).count()
        return float(count)


class AnomalyMonitor(SecurityMonitor):
    """Anomaly detection monitor"""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, MonitorType.ANOMALY, **kwargs)
        self.baseline_period_days = 7
        self.sensitivity = 2.0  # Standard deviations from baseline
    
    def check(self) -> Dict[str, Any]:
        """Check for anomalies"""
        try:
            anomalies = self._detect_anomalies()
            
            if anomalies:
                return {
                    'status': 'alert',
                    'level': AlertLevel.WARNING,
                    'message': f"Anomalies detected: {len(anomalies)}",
                    'anomalies': anomalies
                }
            else:
                return {
                    'status': 'ok',
                    'message': 'No anomalies detected'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'level': AlertLevel.ERROR,
                'message': f"Anomaly detection error: {e}"
            }
    
    def _detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in security data"""
        anomalies = []
        
        # Get baseline data
        baseline_start = timezone.now() - timedelta(days=self.baseline_period_days)
        baseline_end = timezone.now() - timedelta(hours=1)
        
        # Get current data
        current_start = timezone.now() - timedelta(hours=1)
        current_end = timezone.now()
        
        # Check login patterns
        login_anomaly = self._check_login_anomaly(baseline_start, baseline_end, current_start, current_end)
        if login_anomaly:
            anomalies.append(login_anomaly)
        
        # Check IP patterns
        ip_anomaly = self._check_ip_anomaly(baseline_start, baseline_end, current_start, current_end)
        if ip_anomaly:
            anomalies.append(ip_anomaly)
        
        # Check event volume
        volume_anomaly = self._check_volume_anomaly(baseline_start, baseline_end, current_start, current_end)
        if volume_anomaly:
            anomalies.append(volume_anomaly)
        
        return anomalies
    
    def _check_login_anomaly(self, baseline_start, baseline_end, current_start, current_end) -> Optional[Dict[str, Any]]:
        """Check for login anomalies"""
        # Baseline stats
        baseline_logins = SecurityLog.objects.filter(
            security_type='login_success',
            created_at__range=[baseline_start, baseline_end]
        ).count()
        
        baseline_period_hours = (baseline_end - baseline_start).total_seconds() / 3600
        baseline_rate = baseline_logins / max(1, baseline_period_hours)
        
        # Current stats
        current_logins = SecurityLog.objects.filter(
            security_type='login_success',
            created_at__range=[current_start, current_end]
        ).count()
        
        current_period_hours = (current_end - current_start).total_seconds() / 3600
        current_rate = current_logins / max(1, current_period_hours)
        
        # Check for anomaly
        if baseline_rate > 0:
            deviation = (current_rate - baseline_rate) / baseline_rate
            
            if abs(deviation) > (self.sensitivity / 10):  # 20% deviation threshold
                return {
                    'type': 'login_anomaly',
                    'baseline_rate': baseline_rate,
                    'current_rate': current_rate,
                    'deviation': deviation,
                    'severity': 'high' if abs(deviation) > 0.5 else 'medium'
                }
        
        return None
    
    def _check_ip_anomaly(self, baseline_start, baseline_end, current_start, current_end) -> Optional[Dict[str, Any]]:
        """Check for IP anomalies"""
        # Get unique IPs in baseline period
        baseline_ips = SecurityLog.objects.filter(
            created_at__range=[baseline_start, baseline_end]
        ).values('ip_address').distinct().count()
        
        # Get unique IPs in current period
        current_ips = SecurityLog.objects.filter(
            created_at__range=[current_start, current_end]
        ).values('ip_address').distinct().count()
        
        # Check for anomaly
        if baseline_ips > 0:
            deviation = (current_ips - baseline_ips) / baseline_ips
            
            if abs(deviation) > (self.sensitivity / 10):  # 20% deviation threshold
                return {
                    'type': 'ip_anomaly',
                    'baseline_ips': baseline_ips,
                    'current_ips': current_ips,
                    'deviation': deviation,
                    'severity': 'high' if abs(deviation) > 0.5 else 'medium'
                }
        
        return None
    
    def _check_volume_anomaly(self, baseline_start, baseline_end, current_start, current_end) -> Optional[Dict[str, Any]]:
        """Check for volume anomalies"""
        # Baseline volume
        baseline_volume = SecurityLog.objects.filter(
            created_at__range=[baseline_start, baseline_end]
        ).count()
        
        # Current volume
        current_volume = SecurityLog.objects.filter(
            created_at__range=[current_start, current_end]
        ).count()
        
        # Normalize by time period
        baseline_hours = (baseline_end - baseline_start).total_seconds() / 3600
        current_hours = (current_end - current_start).total_seconds() / 3600
        
        baseline_rate = baseline_volume / max(1, baseline_hours)
        current_rate = current_volume / max(1, current_hours)
        
        # Check for anomaly
        if baseline_rate > 0:
            deviation = (current_rate - baseline_rate) / baseline_rate
            
            if abs(deviation) > (self.sensitivity / 10):  # 20% deviation threshold
                return {
                    'type': 'volume_anomaly',
                    'baseline_rate': baseline_rate,
                    'current_rate': current_rate,
                    'deviation': deviation,
                    'severity': 'high' if abs(deviation) > 0.5 else 'medium'
                }
        
        return None


class HealthCheckMonitor(SecurityMonitor):
    """Health check monitor"""
    
    def __init__(self, **kwargs):
        super().__init__('health_check_monitor', MonitorType.HEALTH_CHECK, **kwargs)
    
    def check(self) -> Dict[str, Any]:
        """Perform health checks"""
        try:
            health_status = {
                'database': self._check_database(),
                'cache': self._check_cache(),
                'storage': self._check_storage(),
                'memory': self._check_memory(),
                'overall': 'healthy'
            }
            
            # Determine overall health
            unhealthy_services = [k for k, v in health_status.items() if v != 'healthy']
            if unhealthy_services:
                health_status['overall'] = 'unhealthy'
                return {
                    'status': 'alert',
                    'level': AlertLevel.ERROR,
                    'message': f"Health check failed for: {', '.join(unhealthy_services)}",
                    'health_status': health_status
                }
            else:
                return {
                    'status': 'ok',
                    'message': 'All systems healthy',
                    'health_status': health_status
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'level': AlertLevel.CRITICAL,
                'message': f"Health check error: {e}"
            }
    
    def _check_database(self) -> str:
        """Check database connectivity"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return 'healthy'
        except Exception:
            return 'unhealthy'
    
    def _check_cache(self) -> str:
        """Check cache connectivity"""
        try:
            cache.set('health_check', 'ok', 10)
            result = cache.get('health_check')
            cache.delete('health_check')
            return 'healthy' if result == 'ok' else 'unhealthy'
        except Exception:
            return 'unhealthy'
    
    def _check_storage(self) -> str:
        """Check storage availability"""
        try:
            import os
            media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
            test_file = os.path.join(media_root, 'health_check.tmp')
            
            with open(test_file, 'w') as f:
                f.write('test')
            
            with open(test_file, 'r') as f:
                content = f.read()
            
            os.remove(test_file)
            
            return 'healthy' if content == 'test' else 'unhealthy'
        except Exception:
            return 'unhealthy'
    
    def _check_memory(self) -> str:
        """Check memory usage"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 90:
                return 'critical'
            elif memory_percent > 80:
                return 'warning'
            else:
                return 'healthy'
        except ImportError:
            return 'unknown'
        except Exception:
            return 'unhealthy'


class MonitoringManager:
    """Manager for all security monitors"""
    
    def __init__(self):
        self.monitors = {}
        self.alert_handlers = []
        self._running = False
    
    def add_monitor(self, monitor: SecurityMonitor):
        """Add a monitor"""
        self.monitors[monitor.name] = monitor
        
        # Add default alert handlers
        for handler in self.alert_handlers:
            monitor.add_alert_handler(handler)
        
        logger.info(f"Added monitor: {monitor.name}")
    
    def remove_monitor(self, name: str):
        """Remove a monitor"""
        if name in self.monitors:
            monitor = self.monitors[name]
            monitor.stop()
            del self.monitors[name]
            logger.info(f"Removed monitor: {name}")
    
    def start_all(self):
        """Start all monitors"""
        for monitor in self.monitors.values():
            monitor.start()
        
        self._running = True
        logger.info("Started all security monitors")
    
    def stop_all(self):
        """Stop all monitors"""
        for monitor in self.monitors.values():
            monitor.stop()
        
        self._running = False
        logger.info("Stopped all security monitors")
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler to all monitors"""
        self.alert_handlers.append(handler)
        
        for monitor in self.monitors.values():
            monitor.add_alert_handler(handler)
    
    def get_monitor_status(self) -> Dict[str, Any]:
        """Get status of all monitors"""
        status = {
            'manager_running': self._running,
            'total_monitors': len(self.monitors),
            'monitors': {}
        }
        
        for name, monitor in self.monitors.items():
            status['monitors'][name] = monitor.get_status()
        
        return status
    
    def get_monitor(self, name: str) -> Optional[SecurityMonitor]:
        """Get specific monitor"""
        return self.monitors.get(name)
    
    def initialize_default_monitors(self):
        """Initialize default security monitors"""
        # Failed login monitor
        failed_login_monitor = FailedLoginMonitor(threshold=10)
        self.add_monitor(failed_login_monitor)
        
        # High risk event monitor
        high_risk_monitor = HighRiskEventMonitor(threshold=5)
        self.add_monitor(high_risk_monitor)
        
        # Incident monitor
        incident_monitor = IncidentMonitor(threshold=5)
        self.add_monitor(incident_monitor)
        
        # Threat monitor
        threat_monitor = ThreatMonitor(threshold=10)
        self.add_monitor(threat_monitor)
        
        # Anomaly monitor
        anomaly_monitor = AnomalyMonitor('security_anomaly_monitor', interval=300)
        self.add_monitor(anomaly_monitor)
        
        # Health check monitor
        health_monitor = HealthCheckMonitor(interval=60)
        self.add_monitor(health_monitor)
        
        logger.info("Initialized default security monitors")


# Alert handlers
class DatabaseAlertHandler:
    """Database alert handler"""
    
    def __call__(self, alert_data: Dict[str, Any]):
        """Handle alert by storing in database"""
        try:
            # Store alert in database (would need Alert model)
            logger.info(f"Database alert: {alert_data['message']}")
        except Exception as e:
            logger.error(f"Database alert handler error: {e}")


class EmailAlertHandler:
    """Email alert handler"""
    
    def __init__(self, recipients: List[str]):
        self.recipients = recipients
    
    def __call__(self, alert_data: Dict[str, Any]):
        """Handle alert by sending email"""
        try:
            from django.core.mail import send_mail
            
            subject = f"Security Alert: {alert_data['monitor']}"
            message = f"""
Monitor: {alert_data['monitor']}
Level: {alert_data['level']}
Message: {alert_data['message']}
Time: {alert_data['timestamp']}
"""
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                self.recipients,
                fail_silently=False
            )
            
            logger.info(f"Email alert sent for: {alert_data['monitor']}")
        except Exception as e:
            logger.error(f"Email alert handler error: {e}")


class WebhookAlertHandler:
    """Webhook alert handler"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def __call__(self, alert_data: Dict[str, Any]):
        """Handle alert by sending webhook"""
        try:
            import requests
            
            response = requests.post(
                self.webhook_url,
                json=alert_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook alert sent for: {alert_data['monitor']}")
            else:
                logger.error(f"Webhook alert failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Webhook alert handler error: {e}")


class LogAlertHandler:
    """Logging alert handler"""
    
    def __call__(self, alert_data: Dict[str, Any]):
        """Handle alert by logging"""
        level = alert_data.get('level', 'info')
        message = f"Security Alert [{level.upper()}]: {alert_data['message']}"
        
        if level == AlertLevel.CRITICAL:
            logger.critical(message)
        elif level == AlertLevel.ERROR:
            logger.error(message)
        elif level == AlertLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)


# Global monitoring manager
monitoring_manager = MonitoringManager()


# Initialize default monitors
def initialize_security_monitoring():
    """Initialize default security monitoring"""
    monitoring_manager.initialize_default_monitors()
    
    # Add default alert handlers
    monitoring_manager.add_alert_handler(LogAlertHandler())
    
    # Add email handler if configured
    if hasattr(settings, 'SECURITY_ALERT_EMAILS'):
        monitoring_manager.add_alert_handler(EmailAlertHandler(settings.SECURITY_ALERT_EMAILS))
    
    # Add webhook handler if configured
    if hasattr(settings, 'SECURITY_ALERT_WEBHOOK'):
        monitoring_manager.add_alert_handler(WebhookAlertHandler(settings.SECURITY_ALERT_WEBHOOK))


# Export classes and utilities
__all__ = [
    'AlertLevel',
    'MonitorType',
    'MonitorStatus',
    'SecurityMonitor',
    'ThresholdMonitor',
    'SecurityEventMonitor',
    'FailedLoginMonitor',
    'HighRiskEventMonitor',
    'IncidentMonitor',
    'ThreatMonitor',
    'AnomalyMonitor',
    'HealthCheckMonitor',
    'MonitoringManager',
    'monitoring_manager',
    'DatabaseAlertHandler',
    'EmailAlertHandler',
    'WebhookAlertHandler',
    'LogAlertHandler',
    'initialize_security_monitoring'
]