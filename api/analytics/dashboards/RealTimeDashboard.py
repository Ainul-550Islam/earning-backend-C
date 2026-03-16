import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from collections import deque
import asyncio
import json

from ..models import AnalyticsEvent, RealTimeMetric
from ..processors import DataProcessor

logger = logging.getLogger(__name__)

class RealTimeDashboard:
    """
    Real-time dashboard for monitoring live metrics
    """
    
    def __init__(self, history_minutes: int = 60):
        """
        Args:
            history_minutes: Number of minutes of history to keep
        """
        self.history_minutes = history_minutes
        self.data_processor = DataProcessor()
        
        # Real-time data buffers
        self.metric_buffer = {}
        self.event_buffer = deque(maxlen=1000)
        self.alert_buffer = deque(maxlen=100)
        
        # WebSocket connections
        self.connections = set()
    
    def get_data(self) -> Dict:
        """
        Get real-time dashboard data
        
        Returns:
            Real-time dashboard data
        """
        current_time = timezone.now()
        five_min_ago = current_time - timedelta(minutes=5)
        hour_ago = current_time - timedelta(minutes=self.history_minutes)
        
        dashboard_data = {
            'timestamp': current_time.isoformat(),
            'overview': self._get_overview_metrics(five_min_ago, current_time),
            'activity': self._get_activity_stream(five_min_ago, current_time),
            'metrics': self._get_system_metrics(hour_ago, current_time),
            'alerts': self._get_recent_alerts(),
            'performance': self._get_performance_metrics(hour_ago, current_time),
            'health': self._get_system_health(),
            'updates': self._get_live_updates()
        }
        
        return dashboard_data
    
    def _get_overview_metrics(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get overview metrics for real-time dashboard"""
        # Active users in last 5 minutes
        active_users = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).values('user_id').distinct().count()
        
        # Tasks completed in last 5 minutes
        tasks_completed = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        # Offers completed in last 5 minutes
        offers_completed = AnalyticsEvent.objects.filter(
            event_type='offer_completed',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        # Revenue in last 5 minutes
        revenue = AnalyticsEvent.objects.filter(
            event_time__gte=start_time,
            event_time__lte=end_time,
            value__gt=0
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Withdrawals processed in last 5 minutes
        withdrawals = AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        # API requests in last 5 minutes
        api_requests = AnalyticsEvent.objects.filter(
            event_type='api_call',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        return {
            'active_users': active_users,
            'tasks_completed': tasks_completed,
            'offers_completed': offers_completed,
            'revenue': revenue,
            'withdrawals': withdrawals,
            'api_requests': api_requests,
            'period_seconds': 300
        }
    
    def _get_activity_stream(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get real-time activity stream"""
        # Get recent events
        recent_events = AnalyticsEvent.objects.filter(
            event_time__gte=start_time,
            event_time__lte=end_time
        ).select_related('user').order_by('-event_time')[:50]
        
        activity_stream = []
        for event in recent_events:
            activity = {
                'id': str(event.id),
                'type': event.event_type,
                'user': event.user.username if event.user else 'Anonymous',
                'time': event.event_time,
                'value': event.value,
                'metadata': event.metadata
            }
            
            # Format based on event type
            if event.event_type == 'task_completed':
                activity['message'] = f"{event.user.username if event.user else 'User'} completed a task"
                activity['icon'] = '[OK]'
                activity['color'] = 'green'
            elif event.event_type == 'offer_completed':
                activity['message'] = f"{event.user.username if event.user else 'User'} completed an offer"
                activity['icon'] = '🎯'
                activity['color'] = 'blue'
            elif event.event_type == 'withdrawal_processed':
                activity['message'] = f"{event.user.username if event.user else 'User'} withdrew ${abs(event.value)}"
                activity['icon'] = '[MONEY]'
                activity['color'] = 'orange'
            elif event.event_type == 'user_login':
                activity['message'] = f"{event.user.username if event.user else 'User'} logged in"
                activity['icon'] = '👤'
                activity['color'] = 'purple'
            elif event.event_type == 'error_occurred':
                activity['message'] = f"Error: {event.metadata.get('error', 'Unknown error')}"
                activity['icon'] = '🚨'
                activity['color'] = 'red'
            else:
                activity['message'] = f"{event.event_type.replace('_', ' ').title()}"
                activity['icon'] = '[NOTE]'
                activity['color'] = 'gray'
            
            activity_stream.append(activity)
        
        return activity_stream
    
    def _get_system_metrics(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get system metrics for real-time monitoring"""
        # Get metrics from RealTimeMetric model
        metrics = RealTimeMetric.objects.filter(
            metric_time__gte=start_time,
            metric_time__lte=end_time
        ).order_by('metric_time')
        
        # Group by metric type
        metric_data = {}
        for metric in metrics:
            if metric.metric_type not in metric_data:
                metric_data[metric.metric_type] = {
                    'values': [],
                    'timestamps': [],
                    'unit': metric.unit
                }
            
            metric_data[metric.metric_type]['values'].append(metric.value)
            metric_data[metric.metric_type]['timestamps'].append(metric.metric_time)
        
        # Calculate current values and trends
        current_metrics = {}
        for metric_type, data in metric_data.items():
            if data['values']:
                current = data['values'][-1]
                previous = data['values'][0] if len(data['values']) > 1 else current
                
                if previous != 0:
                    trend = ((current - previous) / previous) * 100
                else:
                    trend = 0
                
                current_metrics[metric_type] = {
                    'current': current,
                    'trend': trend,
                    'unit': data['unit'],
                    'history': list(zip(
                        [ts.isoformat() for ts in data['timestamps']],
                        data['values']
                    ))
                }
        
        # Add derived metrics
        if 'active_users' in current_metrics and 'api_requests' in current_metrics:
            active_users = current_metrics['active_users']['current']
            api_requests = current_metrics['api_requests']['current']
            
            if active_users > 0:
                requests_per_user = api_requests / active_users
                current_metrics['requests_per_user'] = {
                    'current': requests_per_user,
                    'trend': 0,
                    'unit': 'requests/user',
                    'history': []
                }
        
        return current_metrics
    
    def _get_recent_alerts(self) -> List[Dict]:
        """Get recent alerts"""
        from ..models import AlertHistory
        
        recent_alerts = AlertHistory.objects.filter(
            triggered_at__gte=timezone.now() - timedelta(minutes=30)
        ).select_related('rule').order_by('-triggered_at')[:10]
        
        alerts = []
        for alert in recent_alerts:
            alerts.append({
                'id': str(alert.id),
                'rule_name': alert.rule.name,
                'severity': alert.severity,
                'triggered_at': alert.triggered_at,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold_value,
                'condition': alert.condition_met,
                'resolved': alert.is_resolved,
                'icon': self._get_alert_icon(alert.severity),
                'color': self._get_alert_color(alert.severity)
            })
        
        return alerts
    
    def _get_performance_metrics(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get performance metrics"""
        # API response times
        api_events = AnalyticsEvent.objects.filter(
            event_type='api_call',
            event_time__gte=start_time,
            event_time__lte=end_time,
            duration__isnull=False
        )
        
        if api_events.exists():
            response_stats = api_events.aggregate(
                avg=Avg('duration'),
                p95=Avg('duration'),  # Simplified - would use percentile
                p99=Avg('duration'),
                max=Max('duration')
            )
        else:
            response_stats = {'avg': 0, 'p95': 0, 'p99': 0, 'max': 0}
        
        # Error rates
        error_events = AnalyticsEvent.objects.filter(
            event_type='error_occurred',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        total_events = AnalyticsEvent.objects.filter(
            event_time__gte=start_time,
            event_time__lte=end_time
        ).count()
        
        error_rate = (error_events / total_events * 100) if total_events > 0 else 0
        
        # Success rates
        task_events = AnalyticsEvent.objects.filter(
            event_type__in=['task_completed', 'task_failed'],
            event_time__gte=start_time,
            event_time__lte=end_time
        )
        
        if task_events.exists():
            completed = task_events.filter(event_type='task_completed').count()
            total_tasks = task_events.count()
            task_success_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0
        else:
            task_success_rate = 0
        
        return {
            'api_response': response_stats,
            'error_rate': error_rate,
            'task_success_rate': task_success_rate,
            'uptime': self._calculate_uptime(start_time, end_time)
        }
    
    def _get_system_health(self) -> Dict:
        """Get system health status"""
        # Check database connection
        db_status = 'healthy'
        try:
            from django.db import connection
            connection.ensure_connection()
        except Exception as e:
            db_status = 'unhealthy'
            logger.error(f"Database health check failed: {str(e)}")
        
        # Check cache
        cache_status = 'healthy'
        try:
            from django.core.cache import cache
            cache.set('health_check', 'test', 1)
            if cache.get('health_check') != 'test':
                cache_status = 'degraded'
        except Exception as e:
            cache_status = 'unhealthy'
            logger.error(f"Cache health check failed: {str(e)}")
        
        # Check external services (simplified)
        services = {
            'database': db_status,
            'cache': cache_status,
            'payment_gateway': 'healthy',  # Would actually check
            'email_service': 'healthy',
            'sms_gateway': 'healthy'
        }
        
        # Overall health
        unhealthy_count = sum(1 for status in services.values() if status == 'unhealthy')
        degraded_count = sum(1 for status in services.values() if status == 'degraded')
        
        if unhealthy_count > 0:
            overall_health = 'unhealthy'
        elif degraded_count > 0:
            overall_health = 'degraded'
        else:
            overall_health = 'healthy'
        
        return {
            'overall': overall_health,
            'services': services,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_live_updates(self) -> Dict:
        """Get live updates for WebSocket clients"""
        # This would be called by WebSocket handler
        updates = {
            'timestamp': timezone.now().isoformat(),
            'new_events': len(self.event_buffer),
            'new_alerts': len(self.alert_buffer),
            'metric_updates': list(self.metric_buffer.keys())[:5]
        }
        
        return updates
    
    # WebSocket methods
    async def add_connection(self, websocket):
        """Add WebSocket connection"""
        self.connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.connections)}")
    
    async def remove_connection(self, websocket):
        """Remove WebSocket connection"""
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info(f"WebSocket connection removed. Total: {len(self.connections)}")
    
    async def broadcast_update(self, update_type: str, data: Any):
        """Broadcast update to all connected clients"""
        if not self.connections:
            return
        
        message = {
            'type': update_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        
        message_json = json.dumps(message, default=str)
        
        disconnected = set()
        for connection in self.connections:
            try:
                await connection.send(message_json)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {str(e)}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            await self.remove_connection(connection)
    
    def process_real_time_event(self, event: Dict):
        """Process a real-time event"""
        # Add to buffer
        self.event_buffer.append(event)
        
        # Update metrics if applicable
        if 'metric_type' in event:
            metric_type = event['metric_type']
            if metric_type not in self.metric_buffer:
                self.metric_buffer[metric_type] = deque(maxlen=100)
            
            self.metric_buffer[metric_type].append(event)
        
        # Check for alerts
        self._check_alerts(event)
    
    def _check_alerts(self, event: Dict):
        """Check event against alert rules"""
        from ..models import AlertRule
        
        if 'metric_type' not in event:
            return
        
        # Get active alert rules for this metric
        alert_rules = AlertRule.objects.filter(
            metric_type=event['metric_type'],
            is_active=True
        )
        
        for rule in alert_rules:
            # Check condition
            condition_met = False
            value = event.get('value', 0)
            
            if rule.condition == 'greater_than':
                condition_met = value > rule.threshold_value
            elif rule.condition == 'less_than':
                condition_met = value < rule.threshold_value
            elif rule.condition == 'equal_to':
                condition_met = value == rule.threshold_value
            elif rule.condition == 'not_equal':
                condition_met = value != rule.threshold_value
            elif rule.condition == 'in_range':
                condition_met = rule.threshold_value <= value <= rule.threshold_value_2
            elif rule.condition == 'out_of_range':
                condition_met = value < rule.threshold_value or value > rule.threshold_value_2
            
            if condition_met:
                # Create alert
                from ..models import AlertHistory
                
                alert = AlertHistory.objects.create(
                    rule=rule,
                    severity=rule.severity,
                    metric_value=value,
                    threshold_value=rule.threshold_value,
                    condition_met=f"{event['metric_type']} {rule.condition} {rule.threshold_value}",
                    triggered_at=timezone.now()
                )
                
                # Add to buffer
                self.alert_buffer.append({
                    'id': str(alert.id),
                    'rule_name': rule.name,
                    'severity': rule.severity,
                    'metric_value': value,
                    'threshold': rule.threshold_value,
                    'timestamp': alert.triggered_at.isoformat()
                })
                
                # Send notifications
                self._send_alert_notifications(alert, rule)
    
    def _send_alert_notifications(self, alert, rule):
        """Send alert notifications"""
        # Send email
        if rule.notify_email and rule.email_recipients:
            from ..tasks import send_alert_email
            send_alert_email.delay(
                alert_id=str(alert.id),
                recipients=rule.email_recipients
            )
        
        # Send Slack
        if rule.notify_slack and rule.slack_webhook:
            from ..tasks import send_slack_alert
            send_slack_alert.delay(
                webhook_url=rule.slack_webhook,
                alert_id=str(alert.id)
            )
        
        # Send webhook
        if rule.notify_webhook and rule.webhook_url:
            from ..tasks import send_webhook_alert
            send_webhook_alert.delay(
                webhook_url=rule.webhook_url,
                alert_id=str(alert.id)
            )
    
    # Helper methods
    def _get_alert_icon(self, severity: str) -> str:
        """Get icon for alert severity"""
        icons = {
            'info': '[INFO]',
            'warning': '[WARN]',
            'error': '🚨',
            'critical': '🔥'
        }
        return icons.get(severity, '[NOTE]')
    
    def _get_alert_color(self, severity: str) -> str:
        """Get color for alert severity"""
        colors = {
            'info': 'blue',
            'warning': 'yellow',
            'error': 'orange',
            'critical': 'red'
        }
        return colors.get(severity, 'gray')
    
    def _calculate_uptime(self, start_time: datetime, end_time: datetime) -> float:
        """Calculate system uptime percentage"""
        # Simplified - would use actual uptime monitoring
        total_minutes = (end_time - start_time).total_seconds() / 60
        
        # Count error minutes
        error_minutes = AnalyticsEvent.objects.filter(
            event_type='error_occurred',
            event_time__gte=start_time,
            event_time__lte=end_time
        ).annotate(
            minute=TruncDate('event_time')
        ).values('minute').distinct().count()
        
        if total_minutes > 0:
            uptime = ((total_minutes - error_minutes) / total_minutes) * 100
        else:
            uptime = 100.0
        
        return uptime