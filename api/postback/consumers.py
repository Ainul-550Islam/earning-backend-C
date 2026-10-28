"""
consumers.py – WebSocket consumers for postback module.

Provides real-time WebSocket consumers for postback monitoring,
analytics updates, and live status tracking using Django Channels.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus
from .permissions import IsPostbackAdmin

logger = logging.getLogger(__name__)


class PostbackLogConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time postback log monitoring.
    
    Provides live updates for:
    - New postback arrivals
    - Status changes
    - Processing progress
    - Error notifications
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        # Check authentication
        if not await self.is_authenticated():
            await self.close(code=4001)
            return
        
        # Check permissions
        if not await self.has_permission():
            await self.close(code=4003)
            return
        
        # Create group name based on user permissions
        self.group_name = await self.get_group_name()
        
        # Join appropriate groups
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Join global postback updates group
        await self.channel_layer.group_add(
            'postback_updates',
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
        
        logger.info(f"PostbackLogConsumer connected: {self.group_name}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave groups
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            'postback_updates',
            self.channel_name
        )
        
        logger.info(f"PostbackLogConsumer disconnected: {self.group_name}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe':
                await self.handle_subscribe(data)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(data)
            elif message_type == 'get_logs':
                await self.handle_get_logs(data)
            elif message_type == 'get_stats':
                await self.handle_get_stats(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
            await self.send_error("Internal server error")
    
    async def postback_log_created(self, event):
        """Handle new postback log creation event."""
        try:
            log_data = event['data']
            
            # Filter based on user permissions
            if await self.can_access_log(log_data):
                await self.send_text(json.dumps({
                    'type': 'postback_created',
                    'data': log_data,
                    'timestamp': timezone.now().isoformat()
                }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in postback_log_created: {str(e)}")
    
    async def postback_log_updated(self, event):
        """Handle postback log update event."""
        try:
            log_data = event['data']
            
            # Filter based on user permissions
            if await self.can_access_log(log_data):
                await self.send_text(json.dumps({
                    'type': 'postback_updated',
                    'data': log_data,
                    'timestamp': timezone.now().isoformat()
                }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in postback_log_updated: {str(e)}")
    
    async def postback_status_changed(self, event):
        """Handle postback status change event."""
        try:
            log_data = event['data']
            
            # Filter based on user permissions
            if await self.can_access_log(log_data):
                await self.send_text(json.dumps({
                    'type': 'status_changed',
                    'data': log_data,
                    'timestamp': timezone.now().isoformat()
                }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in postback_status_changed: {str(e)}")
    
    async def analytics_updated(self, event):
        """Handle analytics update event."""
        try:
            analytics_data = event['data']
            
            await self.send_text(json.dumps({
                'type': 'analytics_updated',
                'data': analytics_data,
                'timestamp': timezone.now().isoformat()
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in analytics_updated: {str(e)}")
    
    # Helper methods
    async def is_authenticated(self):
        """Check if user is authenticated."""
        return hasattr(self.scope, 'user') and self.scope['user'].is_authenticated
    
    async def has_permission(self):
        """Check if user has required permissions."""
        user = self.scope.get('user')
        if isinstance(user, AnonymousUser):
            return False
        
        return await database_sync_to_async(
            IsPostbackAdmin().has_permission
        )(None, user)
    
    async def get_group_name(self):
        """Get group name based on user permissions."""
        user = self.scope.get('user')
        
        if user and user.is_superuser:
            return 'postback_admin'
        elif user and user.is_staff:
            return 'postback_staff'
        else:
            return f'postback_user_{user.id}'
    
    async def can_access_log(self, log_data):
        """Check if user can access specific log."""
        user = self.scope.get('user')
        
        # Superusers can access all logs
        if user and user.is_superuser:
            return True
        
        # Staff can access logs from their networks
        if user and user.is_staff:
            # Add logic to check network ownership
            return True
        
        # Regular users can only access their own logs
        if user:
            return log_data.get('resolved_user_id') == str(user.id)
        
        return False
    
    async def send_initial_data(self):
        """Send initial data to connected client."""
        try:
            # Send recent logs
            recent_logs = await self.get_recent_logs(limit=10)
            
            await self.send_text(json.dumps({
                'type': 'initial_data',
                'data': {
                    'recent_logs': recent_logs,
                    'user_info': {
                        'username': self.scope['user'].username,
                        'is_staff': self.scope['user'].is_staff,
                        'is_superuser': self.scope['user'].is_superuser,
                    },
                    'connection_time': timezone.now().isoformat()
                }
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error sending initial data: {str(e)}")
    
    async def handle_subscribe(self, data):
        """Handle subscription to specific events."""
        try:
            subscription_type = data.get('subscription_type')
            filters = data.get('filters', {})
            
            if subscription_type == 'network':
                network_id = filters.get('network_id')
                if network_id:
                    group_name = f'postback_network_{network_id}'
                    await self.channel_layer.group_add(
                        group_name,
                        self.channel_name
                    )
                    await self.send_success(f"Subscribed to network {network_id}")
            
            elif subscription_type == 'status':
                status = filters.get('status')
                if status:
                    group_name = f'postback_status_{status}'
                    await self.channel_layer.group_add(
                        group_name,
                        self.channel_name
                    )
                    await self.send_success(f"Subscribed to status {status}")
            
            else:
                await self.send_error(f"Unknown subscription type: {subscription_type}")
        
        except Exception as e:
            logger.error(f"Error in handle_subscribe: {str(e)}")
            await self.send_error("Subscription failed")
    
    async def handle_unsubscribe(self, data):
        """Handle unsubscription from specific events."""
        try:
            subscription_type = data.get('subscription_type')
            filters = data.get('filters', {})
            
            if subscription_type == 'network':
                network_id = filters.get('network_id')
                if network_id:
                    group_name = f'postback_network_{network_id}'
                    await self.channel_layer.group_discard(
                        group_name,
                        self.channel_name
                    )
                    await self.send_success(f"Unsubscribed from network {network_id}")
            
            elif subscription_type == 'status':
                status = filters.get('status')
                if status:
                    group_name = f'postback_status_{status}'
                    await self.channel_layer.group_discard(
                        group_name,
                        self.channel_name
                    )
                    await self.send_success(f"Unsubscribed from status {status}")
            
            else:
                await self.send_error(f"Unknown subscription type: {subscription_type}")
        
        except Exception as e:
            logger.error(f"Error in handle_unsubscribe: {str(e)}")
            await self.send_error("Unsubscription failed")
    
    async def handle_get_logs(self, data):
        """Handle request for postback logs."""
        try:
            limit = data.get('limit', 50)
            offset = data.get('offset', 0)
            filters = data.get('filters', {})
            
            logs = await self.get_filtered_logs(limit=limit, offset=offset, filters=filters)
            
            await self.send_text(json.dumps({
                'type': 'logs_response',
                'data': {
                    'logs': logs,
                    'limit': limit,
                    'offset': offset,
                    'total': len(logs)
                }
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in handle_get_logs: {str(e)}")
            await self.send_error("Failed to get logs")
    
    async def handle_get_stats(self, data):
        """Handle request for statistics."""
        try:
            stats = await self.get_statistics()
            
            await self.send_text(json.dumps({
                'type': 'stats_response',
                'data': stats
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in handle_get_stats: {str(e)}")
            await self.send_error("Failed to get statistics")
    
    # Database access methods
    @database_sync_to_async
    def get_recent_logs(self, limit=10):
        """Get recent postback logs."""
        user = self.scope.get('user')
        
        if user and user.is_superuser:
            logs = PostbackLog.objects.select_related('network', 'resolved_user')[:limit]
        elif user and user.is_staff:
            # Staff can see logs from their assigned networks
            logs = PostbackLog.objects.select_related('network', 'resolved_user')[:limit]
        else:
            # Regular users can only see their own logs
            logs = PostbackLog.objects.filter(
                resolved_user=user
            ).select_related('network', 'resolved_user')[:limit]
        
        return [
            {
                'id': str(log.id),
                'network_key': log.network.network_key,
                'status': log.status,
                'received_at': log.received_at.isoformat(),
                'processed_at': log.processed_at.isoformat() if log.processed_at else None,
                'payout': float(log.payout) if log.payout else None,
                'rejection_reason': log.rejection_reason,
            }
            for log in logs
        ]
    
    @database_sync_to_async
    def get_filtered_logs(self, limit=50, offset=0, filters=None):
        """Get filtered postback logs."""
        user = self.scope.get('user')
        filters = filters or {}
        
        queryset = PostbackLog.objects.select_related('network', 'resolved_user')
        
        # Apply filters based on user permissions
        if not (user and user.is_superuser):
            if user and user.is_staff:
                # Staff filters
                pass  # Add staff-specific filtering
            else:
                # Regular user filters
                queryset = queryset.filter(resolved_user=user)
        
        # Apply additional filters
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        
        if filters.get('network_id'):
            queryset = queryset.filter(network_id=filters['network_id'])
        
        if filters.get('date_from'):
            queryset = queryset.filter(received_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            queryset = queryset.filter(received_at__lte=filters['date_to'])
        
        logs = queryset[offset:offset + limit]
        
        return [
            {
                'id': str(log.id),
                'network_key': log.network.network_key,
                'status': log.status,
                'received_at': log.received_at.isoformat(),
                'processed_at': log.processed_at.isoformat() if log.processed_at else None,
                'payout': float(log.payout) if log.payout else None,
                'rejection_reason': log.rejection_reason,
                'lead_id': log.lead_id,
                'offer_id': log.offer_id,
            }
            for log in logs
        ]
    
    @database_sync_to_async
    def get_statistics(self):
        """Get postback statistics."""
        user = self.scope.get('user')
        
        if not (user and user.is_superuser):
            # Return limited stats for non-superusers
            return {
                'total_logs': 0,
                'status_distribution': {},
                'network_distribution': {},
                'recent_activity': []
            }
        
        # Get overall statistics
        total_logs = PostbackLog.objects.count()
        
        # Status distribution
        status_dist = {}
        for status in PostbackStatus:
            count = PostbackLog.objects.filter(status=status).count()
            status_dist[status.value] = count
        
        # Network distribution
        network_dist = {}
        for network in NetworkPostbackConfig.objects.all():
            count = PostbackLog.objects.filter(network=network).count()
            network_dist[network.network_key] = count
        
        # Recent activity (last hour)
        from datetime import timedelta
        recent_time = timezone.now() - timedelta(hours=1)
        recent_logs = PostbackLog.objects.filter(
            received_at__gte=recent_time
        ).values('received_at', 'status')[:10]
        
        return {
            'total_logs': total_logs,
            'status_distribution': status_dist,
            'network_distribution': network_dist,
            'recent_activity': [
                {
                    'received_at': log['received_at'].isoformat(),
                    'status': log['status']
                }
                for log in recent_logs
            ]
        }
    
    # Message sending methods
    async def send_success(self, message):
        """Send success message."""
        await self.send_text(json.dumps({
            'type': 'success',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_error(self, message):
        """Send error message."""
        await self.send_text(json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))


class PostbackAnalyticsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time postback analytics.
    
    Provides live updates for:
    - Analytics calculations
    - Health scores
    - Anomaly detection
    - Performance metrics
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        if not await self.is_authenticated():
            await self.close(code=4001)
            return
        
        if not await self.has_permission():
            await self.close(code=4003)
            return
        
        self.group_name = 'postback_analytics'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial analytics data
        await self.send_initial_analytics()
        
        logger.info("PostbackAnalyticsConsumer connected")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        
        logger.info("PostbackAnalyticsConsumer disconnected")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_insights':
                await self.handle_get_insights(data)
            elif message_type == 'get_health_scores':
                await self.handle_get_health_scores(data)
            elif message_type == 'get_anomalies':
                await self.handle_get_anomalies(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
            await self.send_error("Internal server error")
    
    async def analytics_updated(self, event):
        """Handle analytics update event."""
        try:
            analytics_data = event['data']
            
            await self.send_text(json.dumps({
                'type': 'analytics_updated',
                'data': analytics_data,
                'timestamp': timezone.now().isoformat()
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in analytics_updated: {str(e)}")
    
    async def health_score_updated(self, event):
        """Handle health score update event."""
        try:
            health_data = event['data']
            
            await self.send_text(json.dumps({
                'type': 'health_score_updated',
                'data': health_data,
                'timestamp': timezone.now().isoformat()
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in health_score_updated: {str(e)}")
    
    async def anomaly_detected(self, event):
        """Handle anomaly detection event."""
        try:
            anomaly_data = event['data']
            
            await self.send_text(json.dumps({
                'type': 'anomaly_detected',
                'data': anomaly_data,
                'timestamp': timezone.now().isoformat()
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in anomaly_detected: {str(e)}")
    
    # Helper methods
    async def is_authenticated(self):
        """Check if user is authenticated."""
        return hasattr(self.scope, 'user') and self.scope['user'].is_authenticated
    
    async def has_permission(self):
        """Check if user has required permissions."""
        user = self.scope.get('user')
        if isinstance(user, AnonymousUser):
            return False
        
        return await database_sync_to_async(
            IsPostbackAdmin().has_permission
        )(None, user)
    
    async def send_initial_analytics(self):
        """Send initial analytics data."""
        try:
            analytics = await self.get_current_analytics()
            
            await self.send_text(json.dumps({
                'type': 'initial_analytics',
                'data': analytics,
                'timestamp': timezone.now().isoformat()
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error sending initial analytics: {str(e)}")
    
    async def handle_get_insights(self, data):
        """Handle request for insights data."""
        try:
            network_id = data.get('network_id')
            days = data.get('days', 7)
            
            insights = await self.get_insights(network_id=network_id, days=days)
            
            await self.send_text(json.dumps({
                'type': 'insights_response',
                'data': insights
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in handle_get_insights: {str(e)}")
            await self.send_error("Failed to get insights")
    
    async def handle_get_health_scores(self, data):
        """Handle request for health scores."""
        try:
            network_id = data.get('network_id')
            hours = data.get('hours', 24)
            
            health_scores = await self.get_health_scores(network_id=network_id, hours=hours)
            
            await self.send_text(json.dumps({
                'type': 'health_scores_response',
                'data': health_scores
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in handle_get_health_scores: {str(e)}")
            await self.send_error("Failed to get health scores")
    
    async def handle_get_anomalies(self, data):
        """Handle request for anomaly data."""
        try:
            network_id = data.get('network_id')
            days = data.get('days', 7)
            
            anomalies = await self.get_anomalies(network_id=network_id, days=days)
            
            await self.send_text(json.dumps({
                'type': 'anomalies_response',
                'data': anomalies
            }, cls=DjangoJSONEncoder))
        
        except Exception as e:
            logger.error(f"Error in handle_get_anomalies: {str(e)}")
            await self.send_error("Failed to get anomalies")
    
    # Database access methods
    @database_sync_to_async
    def get_current_analytics(self):
        """Get current analytics data."""
        # Get today's insights
        from datetime import date
        today = date.today()
        
        insights = PostbackInsight.objects.filter(date=today).select_related('network')
        
        return [
            {
                'network_key': insight.network.network_key,
                'date': insight.date.isoformat(),
                'received_count': insight.received_count,
                'rewarded_count': insight.rewarded_count,
                'rejected_count': insight.rejected_count,
                'health_score': float(insight.health_score),
                'total_payout': float(insight.total_payout),
                'anomaly_detected': insight.anomaly_detected,
            }
            for insight in insights
        ]
    
    @database_sync_to_async
    def get_insights(self, network_id=None, days=7):
        """Get insights data."""
        from datetime import date, timedelta
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        queryset = PostbackInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('network')
        
        if network_id:
            queryset = queryset.filter(network_id=network_id)
        
        return [
            {
                'network_key': insight.network.network_key,
                'date': insight.date.isoformat(),
                'received_count': insight.received_count,
                'rewarded_count': insight.rewarded_count,
                'rejected_count': insight.rejected_count,
                'health_score': float(insight.health_score),
                'total_payout': float(insight.total_payout),
                'anomaly_detected': insight.anomaly_detected,
            }
            for insight in queryset.order_by('date')
        ]
    
    @database_sync_to_async
    def get_health_scores(self, network_id=None, hours=24):
        """Get health score data."""
        from datetime import datetime, timedelta
        
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)
        
        # This would be implemented with actual health score calculation
        # For now, return placeholder data
        return {
            'overall_health': 85.5,
            'network_health': {
                'network1': 90.2,
                'network2': 78.8,
            },
            'trend': 'stable',
            'period_hours': hours,
        }
    
    @database_sync_to_async
    def get_anomalies(self, network_id=None, days=7):
        """Get anomaly data."""
        from datetime import date, timedelta
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        queryset = PostbackInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            anomaly_detected=True
        ).select_related('network')
        
        if network_id:
            queryset = queryset.filter(network_id=network_id)
        
        return [
            {
                'network_key': insight.network.network_key,
                'date': insight.date.isoformat(),
                'anomaly_details': insight.anomaly_details,
                'health_score': float(insight.health_score),
            }
            for insight in queryset.order_by('date')
        ]
    
    async def send_error(self, message):
        """Send error message."""
        await self.send_text(json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))


# WebSocket URL routing
websocket_urlpatterns = [
    # These would be included in the main routing.py
    # path('ws/postback/logs/', PostbackLogConsumer.as_asgi()),
    # path('ws/postback/analytics/', PostbackAnalyticsConsumer.as_asgi()),
]
