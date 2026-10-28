# =============================================================================
# fraud_detection/consumers.py
# =============================================================================
"""
WebSocket Consumers for Fraud Detection System.

Provides real-time WebSocket consumers for fraud notifications,
monitoring updates, and live dashboard data streaming.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

from api.fraud_detection.monitoring import get_real_time_monitor
from api.fraud_detection.analytics import get_fraud_analytics
from api.fraud_detection.exceptions import ConsumerError


logger = logging.getLogger(__name__)


class FraudMonitoringConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time fraud monitoring dashboard.
    
    Handles live fraud detection updates, metrics streaming,
    and real-time alert notifications.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = None
        self.room_group_name = 'fraud_monitoring'
        self.user_id = None
        self.is_authenticated = False
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Check authentication
            user = self.scope.get('user')
            if not user or not user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            self.user_id = user.id
            self.is_authenticated = True
            
            # Initialize monitor
            self.monitor = get_real_time_monitor()
            
            # Join monitoring room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Increment connection count
            self.monitor.increment_connections()
            
            # Send initial dashboard data
            await self.send_initial_data()
            
            logger.info(f"Fraud monitoring WebSocket connected: user {self.user_id}")
            
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
            
            logger.info(f"Fraud monitoring WebSocket disconnected: user {self.user_id}")
            
        except Exception as e:
            logger.error(f"WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')
            
            if message_type == 'request_dashboard':
                await self.send_dashboard_update()
            elif message_type == 'request_metrics':
                await self.send_metrics_update()
            elif message_type == 'request_alerts':
                limit = message.get('limit', 50)
                await self.send_alerts_update(limit)
            elif message_type == 'request_analytics':
                period_days = message.get('period_days', 30)
                await self.send_analytics_update(period_days)
            elif message_type == 'heartbeat':
                await self.send_heartbeat_response()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            await self.send_error("Internal server error")
    
    async def send_initial_data(self):
        """Send initial dashboard data to newly connected client."""
        try:
            dashboard_data = self.monitor.get_dashboard_data()
            
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': dashboard_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
    
    async def send_dashboard_update(self):
        """Send updated dashboard data."""
        try:
            dashboard_data = self.monitor.get_dashboard_data()
            
            await self.send(text_data=json.dumps({
                'type': 'dashboard_update',
                'data': dashboard_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending dashboard update: {e}")
    
    async def send_metrics_update(self):
        """Send current metrics update."""
        try:
            metrics_data = self.monitor.get_current_metrics()
            
            await self.send(text_data=json.dumps({
                'type': 'metrics_update',
                'data': metrics_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending metrics update: {e}")
    
    async def send_alerts_update(self, limit: int = 50):
        """Send recent alerts update."""
        try:
            alerts_data = self.monitor.get_recent_alerts(limit)
            
            await self.send(text_data=json.dumps({
                'type': 'alerts_update',
                'data': alerts_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending alerts update: {e}")
    
    async def send_analytics_update(self, period_days: int = 30):
        """Send analytics update."""
        try:
            analytics = get_fraud_analytics()
            analytics_data = analytics.get_fraud_overview(period_days)
            
            await self.send(text_data=json.dumps({
                'type': 'analytics_update',
                'data': analytics_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending analytics update: {e}")
    
    async def send_heartbeat_response(self):
        """Send heartbeat response."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'heartbeat_response',
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending heartbeat response: {e}")
    
    async def send_error(self, error_message: str):
        """Send error message to client."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': error_message,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    # Channel message handlers
    async def fraud_alert(self, event):
        """Handle fraud alert broadcast."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'fraud_alert',
                'data': event['data'],
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error handling fraud alert: {e}")
    
    async def metric_update(self, event):
        """Handle metric update broadcast."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'metric_update',
                'data': event['data'],
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error handling metric update: {e}")
    
    async def system_status(self, event):
        """Handle system status broadcast."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'system_status',
                'data': event['data'],
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error handling system status: {e}")


class FraudNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for fraud notifications.
    
    Handles real-time fraud alert notifications and case updates
    for administrators and staff.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_group_name = 'fraud_notifications'
        self.user_id = None
        self.user_groups = []
        self.is_authenticated = False
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Check authentication
            user = self.scope.get('user')
            if not user or not user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            self.user_id = user.id
            self.user_groups = [group.name for group in user.groups.all()]
            self.is_authenticated = True
            
            # Check if user has permission to receive notifications
            if not self._has_notification_permission():
                await self.close(code=4003)  # Forbidden
                return
            
            # Join notifications room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'user_id': self.user_id,
                'user_groups': self.user_groups,
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"Fraud notification WebSocket connected: user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Notification WebSocket connection error: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            # Leave notifications room
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"Fraud notification WebSocket disconnected: user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Notification WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')
            
            if message_type == 'mark_read':
                await self.handle_mark_read(message)
            elif message_type == 'get_unread_count':
                await self.send_unread_count()
            elif message_type == 'subscribe':
                await self.handle_subscribe(message)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(message)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Notification WebSocket receive error: {e}")
            await self.send_error("Internal server error")
    
    def _has_notification_permission(self) -> bool:
        """Check if user has permission to receive notifications."""
        required_groups = {'fraud_analyst', 'security_staff', 'compliance_officer'}
        return any(group in required_groups for group in self.user_groups)
    
    async def handle_mark_read(self, message):
        """Handle mark notification as read."""
        try:
            notification_id = message.get('notification_id')
            if not notification_id:
                await self.send_error("Missing notification_id")
                return
            
            # In practice, this would mark notification as read in database
            await self.send(text_data=json.dumps({
                'type': 'notification_marked_read',
                'notification_id': notification_id,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            await self.send_error("Failed to mark as read")
    
    async def send_unread_count(self):
        """Send unread notification count."""
        try:
            # In practice, this would query database for unread count
            unread_count = 0
            
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread_count,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending unread count: {e}")
    
    async def handle_subscribe(self, message):
        """Handle subscription to specific notification types."""
        try:
            notification_types = message.get('types', [])
            
            # In practice, this would update user's subscription preferences
            await self.send(text_data=json.dumps({
                'type': 'subscription_updated',
                'types': notification_types,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error handling subscription: {e}")
    
    async def handle_unsubscribe(self, message):
        """Handle unsubscription from specific notification types."""
        try:
            notification_types = message.get('types', [])
            
            # In practice, this would update user's subscription preferences
            await self.send(text_data=json.dumps({
                'type': 'unsubscription_updated',
                'types': notification_types,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error handling unsubscription: {e}")
    
    async def send_error(self, error_message: str):
        """Send error message to client."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': error_message,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    # Channel message handlers
    async def notification_message(self, event):
        """Handle notification broadcast."""
        try:
            notification_data = event['message']
            
            # Check if user should receive this notification
            if self._should_receive_notification(notification_data):
                await self.send(text_data=json.dumps({
                    'type': 'notification',
                    'data': notification_data,
                    'timestamp': timezone.now().isoformat()
                }))
            
        except Exception as e:
            logger.error(f"Error handling notification message: {e}")
    
    def _should_receive_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Check if user should receive this notification."""
        # Check if notification is for user's role
        recipient_roles = notification_data.get('recipient_roles', [])
        return any(role in self.user_groups for role in recipient_roles)


class FraudAnalyticsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for fraud analytics dashboard.
    
    Handles real-time analytics data streaming and
    interactive chart updates.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_group_name = 'fraud_analytics'
        self.user_id = None
        self.is_authenticated = False
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Check authentication
            user = self.scope.get('user')
            if not user or not user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            self.user_id = user.id
            self.is_authenticated = True
            
            # Check if user has analytics permission
            if not self._has_analytics_permission():
                await self.close(code=4003)  # Forbidden
                return
            
            # Join analytics room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Send initial analytics data
            await self.send_initial_analytics()
            
            logger.info(f"Fraud analytics WebSocket connected: user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Analytics WebSocket connection error: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"Fraud analytics WebSocket disconnected: user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Analytics WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')
            
            if message_type == 'request_chart_data':
                await self.send_chart_data(message)
            elif message_type == 'request_trend_data':
                await self.send_trend_data(message)
            elif message_type == 'request_report':
                await self.send_report_data(message)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Analytics WebSocket receive error: {e}")
            await self.send_error("Internal server error")
    
    def _has_analytics_permission(self) -> bool:
        """Check if user has analytics permission."""
        user = self.scope.get('user')
        if not user:
            return False
        
        # Check if user is staff or has analytics permission
        return user.is_staff or user.groups.filter(name__in=['fraud_analyst', 'compliance_officer']).exists()
    
    async def send_initial_analytics(self):
        """Send initial analytics data."""
        try:
            analytics = get_fraud_analytics()
            overview_data = analytics.get_fraud_overview()
            
            await self.send(text_data=json.dumps({
                'type': 'initial_analytics',
                'data': overview_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending initial analytics: {e}")
    
    async def send_chart_data(self, message):
        """Send chart data for specific chart type."""
        try:
            chart_type = message.get('chart_type')
            period_days = message.get('period_days', 30)
            
            analytics = get_fraud_analytics()
            
            if chart_type == 'risk_trends':
                data = analytics.get_risk_score_trends(period_days)
            elif chart_type == 'case_trends':
                data = analytics.get_fraud_case_trends(period_days)
            elif chart_type == 'alert_frequency':
                data = analytics.get_alert_frequency_analysis(period_days)
            else:
                await self.send_error(f"Unknown chart type: {chart_type}")
                return
            
            # Convert data to JSON-serializable format
            serializable_data = []
            for point in data:
                serializable_data.append({
                    'timestamp': point.timestamp.isoformat(),
                    'value': point.value,
                    'label': point.label,
                    'metadata': point.metadata
                })
            
            await self.send(text_data=json.dumps({
                'type': 'chart_data',
                'chart_type': chart_type,
                'data': serializable_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending chart data: {e}")
    
    async def send_trend_data(self, message):
        """Send trend analysis data."""
        try:
            trend_type = message.get('trend_type')
            period_days = message.get('period_days', 30)
            
            analytics = get_fraud_analytics()
            
            if trend_type == 'risk_distribution':
                data = analytics._get_risk_distribution()
            elif trend_type == 'case_analysis':
                from api.fraud_detection.analytics import FraudAnalytics
                fraud_analytics = FraudAnalytics()
                data = fraud_analytics._get_case_analysis(
                    timezone.now() - timedelta(days=period_days),
                    timezone.now()
                )
            else:
                await self.send_error(f"Unknown trend type: {trend_type}")
                return
            
            await self.send(text_data=json.dumps({
                'type': 'trend_data',
                'trend_type': trend_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending trend data: {e}")
    
    async def send_report_data(self, message):
        """Send report data."""
        try:
            report_type = message.get('report_type')
            period_days = message.get('period_days', 30)
            
            analytics = get_fraud_analytics()
            report_data = analytics.generate_analytics_report(report_type, period_days)
            
            await self.send(text_data=json.dumps({
                'type': 'report_data',
                'report_type': report_type,
                'data': report_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending report data: {e}")
    
    async def send_error(self, error_message: str):
        """Send error message to client."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': error_message,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    # Channel message handlers
    async def analytics_update(self, event):
        """Handle analytics update broadcast."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'analytics_update',
                'data': event['data'],
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error handling analytics update: {e}")


# WebSocket message handlers for channel layer
async def notification_message(message):
    """Handle notification message broadcasts."""
    room_group_name = message['room_group_name']
    
    # Send to all consumers in the room
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        room_group_name,
        {
            'type': 'notification_message',
            'message': message['message']
        }
    )


async def analytics_update(message):
    """Handle analytics update broadcasts."""
    room_group_name = message['room_group_name']
    
    # Send to all consumers in the room
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        room_group_name,
        {
            'type': 'analytics_update',
            'data': message['data']
        }
    )
