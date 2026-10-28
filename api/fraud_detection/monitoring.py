# =============================================================================
# fraud_detection/monitoring.py
# =============================================================================
"""
Real-time Monitoring Layer for Fraud Detection System.

Provides real-time fraud detection monitoring, alert processing,
and system health monitoring with dashboard data generation.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Q
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from api.fraud_detection.repositories import (
    fraud_case_repository, fraud_alert_repository, fraud_risk_profile_repository
)
from api.fraud_detection.selectors import (
    fraud_case_selector, fraud_alert_selector, fraud_risk_profile_selector
)
from api.fraud_detection.encryption import generate_integrity_hash
from api.fraud_detection.exceptions import MonitoringError
from api.fraud_detection.constants import CACHE_KEYS, CACHE_TTL, REALTIME_CONFIG


logger = logging.getLogger(__name__)


@dataclass
class MonitoringMetric:
    """Data class for monitoring metrics."""
    name: str
    value: Union[int, float, str]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class RealTimeMonitor:
    """
    Real-time fraud detection monitor.
    
    Tracks fraud detection metrics, system performance,
    and generates real-time alerts for dashboard display.
    """
    
    def __init__(self):
        """Initialize real-time monitor."""
        self.metrics_buffer = deque(maxlen=1000)  # Rolling buffer of recent metrics
        self.alert_buffer = deque(maxlen=500)    # Rolling buffer of recent alerts
        self.channel_layer = get_channel_layer()
        self.monitoring_room = REALTIME_CONFIG.get('websocket_room', 'fraud_monitoring')
        self.heartbeat_interval = REALTIME_CONFIG.get('heartbeat_interval', 30)
        self.max_connections = REALTIME_CONFIG.get('max_concurrent_connections', 100)
        
        # Initialize monitoring state
        self.last_heartbeat = timezone.now()
        self.active_connections = 0
        self.system_health = 'healthy'
        
        # Load monitoring configuration
        self.thresholds = self._load_monitoring_thresholds()
        self.metrics_config = self._load_metrics_config()
    
    def _load_monitoring_thresholds(self) -> Dict[str, Any]:
        """Load monitoring thresholds and alert levels."""
        default_thresholds = {
            'risk_score_critical': 80,
            'risk_score_high': 60,
            'alert_rate_critical': 10,      # alerts per minute
            'case_rate_critical': 5,        # cases per hour
            'system_load_critical': 0.9,
            'error_rate_critical': 0.15,
            'response_time_critical': 5000,  # milliseconds
        }
        
        return getattr(settings, 'FRAUD_MONITORING_THRESHOLDS', default_thresholds)
    
    def _load_metrics_config(self) -> Dict[str, Any]:
        """Load metrics configuration."""
        default_config = {
            'retention_hours': 24,
            'aggregation_interval': 60,     # seconds
            'dashboard_refresh_rate': 30,    # seconds
            'metrics_buffer_size': 1000,
            'alert_buffer_size': 500,
        }
        
        return getattr(settings, 'FRAUD_METRICS_CONFIG', default_config)
    
    def record_metric(self, metric_name: str, value: Union[int, float, str],
                     metadata: Optional[Dict[str, Any]] = None):
        """
        Record a monitoring metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            metadata: Additional metadata
        """
        metric = MonitoringMetric(
            name=metric_name,
            value=value,
            timestamp=timezone.now(),
            metadata=metadata
        )
        
        self.metrics_buffer.append(metric)
        
        # Check for threshold violations
        self._check_metric_thresholds(metric)
        
        # Broadcast to monitoring room
        self._broadcast_metric(metric)
        
        logger.debug(f"Recorded metric: {metric_name} = {value}")
    
    def record_alert(self, alert_data: Dict[str, Any]):
        """
        Record a fraud alert for monitoring.
        
        Args:
            alert_data: Alert data dictionary
        """
        alert_record = {
            'alert_id': alert_data.get('alert_id'),
            'alert_type': alert_data.get('alert_type'),
            'severity': alert_data.get('severity'),
            'user_id': alert_data.get('user_id'),
            'risk_score': alert_data.get('risk_score'),
            'description': alert_data.get('description'),
            'timestamp': timezone.now().isoformat(),
            'metadata': alert_data.get('metadata', {})
        }
        
        self.alert_buffer.append(alert_record)
        
        # Check for alert rate thresholds
        self._check_alert_rate_thresholds()
        
        # Broadcast to monitoring room
        self._broadcast_alert(alert_record)
        
        logger.info(f"Recorded fraud alert: {alert_data.get('alert_type')} for user {alert_data.get('user_id')}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current monitoring metrics.
        
        Returns:
            Dictionary of current metrics
        """
        now = timezone.now()
        recent_cutoff = now - timedelta(minutes=5)
        
        # Get recent metrics
        recent_metrics = [
            metric for metric in self.metrics_buffer
            if metric.timestamp >= recent_cutoff
        ]
        
        # Aggregate metrics by type
        aggregated_metrics = defaultdict(list)
        for metric in recent_metrics:
            aggregated_metrics[metric.name].append(metric.value)
        
        # Calculate statistics
        current_metrics = {
            'timestamp': now.isoformat(),
            'system_health': self.system_health,
            'active_connections': self.active_connections,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'metrics_summary': {}
        }
        
        for metric_name, values in aggregated_metrics.items():
            if values:
                if isinstance(values[0], (int, float)):
                    current_metrics['metrics_summary'][metric_name] = {
                        'current': values[-1] if values else 0,
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'count': len(values)
                    }
                else:
                    current_metrics['metrics_summary'][metric_name] = {
                        'current': values[-1] if values else '',
                        'count': len(values)
                    }
        
        # Add fraud-specific metrics
        current_metrics['fraud_metrics'] = self._get_fraud_metrics()
        
        return current_metrics
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent fraud alerts.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        return list(self.alert_buffer)[-limit:]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Returns:
            Dashboard data dictionary
        """
        dashboard_data = {
            'timestamp': timezone.now().isoformat(),
            'system_status': self._get_system_status(),
            'fraud_overview': self._get_fraud_overview(),
            'risk_distribution': self._get_risk_distribution(),
            'alert_trends': self._get_alert_trends(),
            'case_management': self._get_case_management_stats(),
            'performance_metrics': self._get_performance_metrics(),
            'geographic_analysis': self._get_geographic_analysis(),
            'real_time_alerts': self.get_recent_alerts(10)
        }
        
        return dashboard_data
    
    def _check_metric_thresholds(self, metric: MonitoringMetric):
        """Check if metric exceeds configured thresholds."""
        threshold_key = f"{metric.name}_critical"
        threshold = self.thresholds.get(threshold_key)
        
        if threshold is not None and isinstance(metric.value, (int, float)):
            if metric.value > threshold:
                self._trigger_threshold_alert(metric, threshold)
    
    def _check_alert_rate_thresholds(self):
        """Check alert rate thresholds."""
        now = timezone.now()
        recent_cutoff = now - timedelta(minutes=1)
        
        recent_alerts = [
            alert for alert in self.alert_buffer
            if datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00')) >= recent_cutoff
        ]
        
        alert_rate = len(recent_alerts)
        critical_threshold = self.thresholds.get('alert_rate_critical', 10)
        
        if alert_rate > critical_threshold:
            self._trigger_rate_alert('alert_rate', alert_rate, critical_threshold)
    
    def _trigger_threshold_alert(self, metric: MonitoringMetric, threshold: float):
        """Trigger threshold violation alert."""
        alert_data = {
            'alert_type': 'threshold_violation',
            'severity': 'high',
            'metric_name': metric.name,
            'metric_value': metric.value,
            'threshold': threshold,
            'description': f"Metric {metric.name} exceeded threshold: {metric.value} > {threshold}",
            'timestamp': metric.timestamp.isoformat()
        }
        
        self.record_alert(alert_data)
        logger.warning(f"Threshold violation: {metric.name} = {metric.value} (threshold: {threshold})")
    
    def _trigger_rate_alert(self, rate_type: str, current_rate: float, threshold: float):
        """Trigger rate-based alert."""
        alert_data = {
            'alert_type': 'rate_violation',
            'severity': 'high',
            'rate_type': rate_type,
            'current_rate': current_rate,
            'threshold': threshold,
            'description': f"Rate {rate_type} exceeded threshold: {current_rate} > {threshold}",
            'timestamp': timezone.now().isoformat()
        }
        
        self.record_alert(alert_data)
        logger.warning(f"Rate violation: {rate_type} = {current_rate} (threshold: {threshold})")
    
    def _broadcast_metric(self, metric: MonitoringMetric):
        """Broadcast metric to WebSocket clients."""
        try:
            message = {
                'type': 'metric_update',
                'data': {
                    'name': metric.name,
                    'value': metric.value,
                    'timestamp': metric.timestamp.isoformat(),
                    'metadata': metric.metadata
                }
            }
            
            async_to_sync(self.channel_layer.group_send)(
                self.monitoring_room,
                {
                    'type': 'broadcast_message',
                    'message': message
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast metric: {e}")
    
    def _broadcast_alert(self, alert_record: Dict[str, Any]):
        """Broadcast alert to WebSocket clients."""
        try:
            message = {
                'type': 'fraud_alert',
                'data': alert_record
            }
            
            async_to_sync(self.channel_layer.group_send)(
                self.monitoring_room,
                {
                    'type': 'broadcast_message',
                    'message': message
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast alert: {e}")
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            'health': self.system_health,
            'uptime': (timezone.now() - self.last_heartbeat).total_seconds(),
            'active_connections': self.active_connections,
            'max_connections': self.max_connections,
            'last_heartbeat': self.last_heartbeat.isoformat()
        }
    
    def _get_fraud_metrics(self) -> Dict[str, Any]:
        """Get fraud-specific metrics."""
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Get recent fraud cases and alerts
        recent_cases = fraud_case_selector.get_cases_by_time_pattern(hours=1)
        recent_alerts = fraud_alert_selector.get_alerts_by_risk_trend(hours=1)
        
        return {
            'cases_last_hour': len(recent_cases),
            'alerts_last_hour': len(recent_alerts),
            'high_risk_cases': len([case for case in recent_cases if case.risk_score >= 70]),
            'critical_alerts': len([alert for alert in recent_alerts if alert.severity_score >= 80]),
            'average_risk_score': sum(case.risk_score for case in recent_cases) / len(recent_cases) if recent_cases else 0
        }
    
    def _get_fraud_overview(self) -> Dict[str, Any]:
        """Get fraud overview statistics."""
        # Get overview from database (simplified)
        total_cases = fraud_case_selector.list(limit=None)
        total_alerts = fraud_alert_selector.list(limit=None)
        
        open_cases = [case for case in total_cases if case.status == 'open']
        high_risk_profiles = fraud_risk_profile_selector.get_high_risk_users()
        
        return {
            'total_cases': len(total_cases),
            'open_cases': len(open_cases),
            'total_alerts': len(total_alerts),
            'unacknowledged_alerts': len([alert for alert in total_alerts if not alert.acknowledged]),
            'high_risk_users': len(high_risk_profiles),
            'cases_today': len([case for case in total_cases if case.created_at.date() == timezone.now().date()]),
            'alerts_today': len([alert for alert in total_alerts if alert.created_at.date() == timezone.now().date()])
        }
    
    def _get_risk_distribution(self) -> Dict[str, Any]:
        """Get risk score distribution."""
        risk_profiles = fraud_risk_profile_selector.list(limit=None)
        
        distribution = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        
        for profile in risk_profiles:
            score = profile.risk_score
            if score >= 80:
                distribution['critical'] += 1
            elif score >= 60:
                distribution['high'] += 1
            elif score >= 40:
                distribution['medium'] += 1
            else:
                distribution['low'] += 1
        
        total = sum(distribution.values())
        
        return {
            'distribution': distribution,
            'percentages': {
                key: (count / total * 100) if total > 0 else 0
                for key, count in distribution.items()
            },
            'total_profiles': total
        }
    
    def _get_alert_trends(self) -> Dict[str, Any]:
        """Get alert trends over time."""
        # Get hourly alert trends for last 24 hours
        now = timezone.now()
        hourly_data = []
        
        for i in range(24):
            hour_start = now - timedelta(hours=i+1)
            hour_end = now - timedelta(hours=i)
            
            alerts_in_hour = fraud_alert_selector.get_alerts_by_risk_trend(hours=1)
            hour_alerts = [
                alert for alert in alerts_in_hour
                if hour_start <= alert.created_at < hour_end
            ]
            
            hourly_data.append({
                'hour': hour_start.strftime('%H:00'),
                'alert_count': len(hour_alerts),
                'high_severity_count': len([alert for alert in hour_alerts if alert.severity_score >= 70])
            })
        
        return {
            'hourly_trends': list(reversed(hourly_data)),
            'peak_hour': max(hourly_data, key=lambda x: x['alert_count']) if hourly_data else None
        }
    
    def _get_case_management_stats(self) -> Dict[str, Any]:
        """Get case management statistics."""
        all_cases = fraud_case_selector.list(limit=None)
        
        status_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for case in all_cases:
            status_counts[case.status] += 1
            severity_counts[case.severity] += 1
        
        # Calculate average resolution time
        resolved_cases = [case for case in all_cases if case.status == 'resolved']
        avg_resolution_time = 0
        
        if resolved_cases:
            resolution_times = []
            for case in resolved_cases:
                if hasattr(case, 'resolved_at') and case.resolved_at:
                    resolution_time = (case.resolved_at - case.created_at).total_seconds()
                    resolution_times.append(resolution_time)
            
            if resolution_times:
                avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        return {
            'status_distribution': dict(status_counts),
            'severity_distribution': dict(severity_counts),
            'total_cases': len(all_cases),
            'resolved_cases': len(resolved_cases),
            'average_resolution_time_hours': avg_resolution_time / 3600 if avg_resolution_time > 0 else 0
        }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        # Get recent performance metrics from buffer
        recent_metrics = [
            metric for metric in self.metrics_buffer
            if metric.name in ['response_time', 'system_load', 'error_rate']
            and metric.timestamp >= timezone.now() - timedelta(minutes=5)
        ]
        
        performance_data = defaultdict(list)
        for metric in recent_metrics:
            performance_data[metric.name].append(metric.value)
        
        return {
            'response_time': {
                'current_ms': performance_data['response_time'][-1] if performance_data.get('response_time') else 0,
                'average_ms': sum(performance_data['response_time']) / len(performance_data['response_time']) if performance_data.get('response_time') else 0,
                'max_ms': max(performance_data['response_time']) if performance_data.get('response_time') else 0
            },
            'system_load': {
                'current': performance_data['system_load'][-1] if performance_data.get('system_load') else 0,
                'average': sum(performance_data['system_load']) / len(performance_data['system_load']) if performance_data.get('system_load') else 0
            },
            'error_rate': {
                'current': performance_data['error_rate'][-1] if performance_data.get('error_rate') else 0,
                'average': sum(performance_data['error_rate']) / len(performance_data['error_rate']) if performance_data.get('error_rate') else 0
            }
        }
    
    def _get_geographic_analysis(self) -> Dict[str, Any]:
        """Get geographic fraud analysis."""
        # Simplified geographic analysis
        # In practice, this would analyze IP geolocation data
        
        return {
            'high_risk_countries': ['US', 'GB', 'CA', 'AU'],
            'suspicious_regions': ['EU', 'APAC'],
            'country_distribution': {
                'US': 45,
                'GB': 20,
                'CA': 15,
                'AU': 10,
                'Other': 10
            },
            'total_countries': 50
        }
    
    def update_system_health(self, health_status: str):
        """Update system health status."""
        self.system_health = health_status
        self.last_heartbeat = timezone.now()
        
        # Broadcast health update
        self.record_metric('system_health', health_status, {'type': 'status_update'})
    
    def increment_connections(self):
        """Increment active connections count."""
        self.active_connections = min(self.active_connections + 1, self.max_connections)
    
    def decrement_connections(self):
        """Decrement active connections count."""
        self.active_connections = max(self.active_connections - 1, 0)


class FraudMonitoringConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time fraud monitoring.
    
    Handles WebSocket connections for real-time dashboard updates.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = None
        self.room_group_name = REALTIME_CONFIG.get('websocket_room', 'fraud_monitoring')
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Accept connection
            await self.accept()
            
            # Get monitor instance
            self.monitor = get_real_time_monitor()
            
            # Join monitoring room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Increment connection count
            self.monitor.increment_connections()
            
            # Send initial dashboard data
            dashboard_data = self.monitor.get_dashboard_data()
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': dashboard_data
            }))
            
            logger.info(f"WebSocket connected: {self.channel_name}")
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            # Leave monitoring room
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Decrement connection count
            if self.monitor:
                self.monitor.decrement_connections()
            
            logger.info(f"WebSocket disconnected: {self.channel_name}")
            
        except Exception as e:
            logger.error(f"WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')
            
            if message_type == 'request_dashboard':
                # Send updated dashboard data
                dashboard_data = self.monitor.get_dashboard_data()
                await self.send(text_data=json.dumps({
                    'type': 'dashboard_update',
                    'data': dashboard_data
                }))
            
            elif message_type == 'request_metrics':
                # Send current metrics
                metrics_data = self.monitor.get_current_metrics()
                await self.send(text_data=json.dumps({
                    'type': 'metrics_update',
                    'data': metrics_data
                }))
            
            elif message_type == 'request_alerts':
                # Send recent alerts
                limit = message.get('limit', 50)
                alerts_data = self.monitor.get_recent_alerts(limit)
                await self.send(text_data=json.dumps({
                    'type': 'alerts_update',
                    'data': alerts_data
                }))
            
            else:
                logger.warning(f"Unknown WebSocket message type: {message_type}")
                
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
    
    async def broadcast_message(self, event):
        """Handle broadcast messages from channel layer."""
        try:
            message = event['message']
            await self.send(text_data=json.dumps(message))
        except Exception as e:
            logger.error(f"WebSocket broadcast error: {e}")


# Global monitor instance
_real_time_monitor = None


def get_real_time_monitor() -> RealTimeMonitor:
    """Get or create real-time monitor instance."""
    global _real_time_monitor
    if _real_time_monitor is None:
        _real_time_monitor = RealTimeMonitor()
    return _real_time_monitor


def record_fraud_metric(metric_name: str, value: Union[int, float, str],
                       metadata: Optional[Dict[str, Any]] = None):
    """
    Convenience function for recording fraud metrics.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        metadata: Additional metadata
    """
    monitor = get_real_time_monitor()
    monitor.record_metric(metric_name, value, metadata)


def record_fraud_alert(alert_data: Dict[str, Any]):
    """
    Convenience function for recording fraud alerts.
    
    Args:
        alert_data: Alert data dictionary
    """
    monitor = get_real_time_monitor()
    monitor.record_alert(alert_data)


def get_dashboard_data() -> Dict[str, Any]:
    """
    Convenience function for getting dashboard data.
    
    Returns:
        Dashboard data dictionary
    """
    monitor = get_real_time_monitor()
    return monitor.get_dashboard_data()
