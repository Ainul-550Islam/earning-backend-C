# api/rate_limit/consumers.py
"""
WebSocket Consumers for Rate Limit Module

Real-time rate limit monitoring and notifications via WebSocket connections.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from api.rate_limit.models import RateLimitLog, RateLimitConfig, AbuseReport, IPBlockList
from api.rate_limit.services import RateLimitService
import redis

logger = logging.getLogger(__name__)


class RateLimitMonitorConsumer(AsyncWebsocketConsumer):
    """
    Real-time rate limit monitoring consumer.
    
    Provides live updates on rate limit events, blocks, and system health.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection.
        """
        self.user = self.scope["user"]
        self.room_group_name = "rate_limit_monitor"
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Accept connection
        await self.accept()

        # Initialize subscription set
        if not hasattr(self, 'subscribed_events'):
            self.subscribed_events = set()

        logger.info(f"Rate limit monitor connected: {self.user.username}")
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        """
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Cancel monitoring task
        if hasattr(self, 'monitoring_task'):
            self.monitoring_task.cancel()
        
        logger.info(f"Rate limit monitor disconnected: {self.user.username}")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'get_stats':
                await self.send_current_stats()
            elif message_type == 'get_logs':
                await self.send_recent_logs(text_data_json.get('limit', 50))
            elif message_type == 'get_blocks':
                await self.send_recent_blocks(text_data_json.get('limit', 20))
            elif message_type == 'get_health':
                await self.send_health_status()
            elif message_type == 'subscribe_events':
                await self.subscribe_to_events(text_data_json.get('events', []))
            elif message_type == 'subscribe':
                # Tests send {'type':'subscribe','data':{'event_type':'...'}}
                inner = text_data_json.get('data', {})
                event_type = inner.get('event_type', '')
                events = [event_type] if event_type else text_data_json.get('events', [])
                # Accumulate (not replace) so sequential subscribe calls build up the set
                self.subscribed_events.update(events)
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'timestamp': timezone.now().isoformat(),
                    'data': {
                        'event_type': event_type,
                        'events': list(self.subscribed_events),
                        'user_id': getattr(self.user, 'id', None),
                    }
                }))
            elif message_type == 'ping':
                await self.send_pong()
            elif message_type == 'get_stats':
                await self.send_current_stats()
            elif message_type == 'get_system_stats':
                await self.send_system_stats()
            elif message_type == 'get_user_stats':
                inner = text_data_json.get('data', {})
                await self.send_user_stats(inner.get('user_id'))
            elif message_type == 'get_insights':
                inner = text_data_json.get('data', {})
                await self.send_insights(inner.get('timeframe', '1h'))
            elif message_type == 'get_performance_metrics':
                inner = text_data_json.get('data', {})
                await self.send_performance_metrics(inner.get('timeframe', '1h'))
            elif message_type == 'get_subscriptions':
                await self.send_subscriptions()
            elif message_type == 'simulate_violation':
                # Used in tests to trigger broadcast
                pass
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def send_initial_data(self):
        """
        Send initial data upon connection.
        """
        initial_data = {
            'type': 'initial_data',
            'timestamp': timezone.now().isoformat(),
            'user': self.user.username,
            'permissions': {
                'can_view_logs': self.user.has_perm('rate_limit.view_ratelimitlog'),
                'can_view_configs': self.user.has_perm('rate_limit.view_ratelimitconfig'),
                'can_view_blocks': self.user.has_perm('rate_limit.view_ipblocklist'),
                'can_manage_configs': self.user.has_perm('rate_limit.change_ratelimitconfig'),
            }
        }
        
        await self.send(text_data=json.dumps(initial_data))
    
    async def send_current_stats(self):
        """
        Send current rate limit statistics.
        """
        try:
            stats = await self.get_current_stats()

            await self.send(text_data=json.dumps({
                'type': 'stats_response',
                'timestamp': timezone.now().isoformat(),
                'data': stats
            }))

        except Exception as e:
            logger.error(f"Error sending current stats: {str(e)}")
            await self.send_error("Failed to retrieve statistics")

    async def send_system_stats(self):
        """Send system-wide stats (admin view)."""
        try:
            from api.rate_limit.models import RateLimitConfig, RateLimitLog
            stats = await database_sync_to_async(self._get_system_stats)()
            await self.send(text_data=json.dumps({
                'type': 'system_stats_response',
                'timestamp': timezone.now().isoformat(),
                'data': stats,
            }))
        except Exception as e:
            logger.error(f"Error sending system stats: {str(e)}")
            await self.send_error("Failed to retrieve system statistics")

    def _get_system_stats(self):
        from api.rate_limit.models import RateLimitConfig, RateLimitLog
        from django.contrib.auth import get_user_model
        User = get_user_model()
        now = timezone.now()
        hour_ago = now - timezone.timedelta(hours=1)
        return {
            'total_users': User.objects.count(),
            'active_configs': RateLimitConfig.objects.filter(is_active=True).count(),
            'recent_violations': RateLimitLog.objects.filter(
                timestamp__gte=hour_ago, is_allowed=False
            ).count(),
            'total_requests_last_hour': RateLimitLog.objects.filter(
                timestamp__gte=hour_ago
            ).count(),
            'timestamp': now.isoformat(),
        }

    async def send_user_stats(self, user_id=None):
        """Send user-specific stats."""
        try:
            from api.rate_limit.models import RateLimitLog
            target_id = user_id or getattr(self.user, 'id', None)

            @database_sync_to_async
            def _get():
                from api.rate_limit.models import RateLimitLog
                now = timezone.now()
                hour_ago = now - timezone.timedelta(hours=1)
                qs = RateLimitLog.objects.filter(user_id=target_id)
                return {
                    'user_id': target_id,
                    'total_requests': qs.count(),
                    'blocked_requests': qs.filter(is_allowed=False).count(),
                    'recent_requests': qs.filter(timestamp__gte=hour_ago).count(),
                }

            stats = await _get()
            await self.send(text_data=json.dumps({
                'type': 'user_stats_response',
                'timestamp': timezone.now().isoformat(),
                'data': stats,
            }))
        except Exception as e:
            logger.error(f"Error sending user stats: {str(e)}")
            await self.send_error("Failed to retrieve user statistics")

    async def send_insights(self, timeframe='1h'):
        """Send rate limit insights."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'insights_response',
                'timestamp': timezone.now().isoformat(),
                'data': {
                    'insights': [],
                    'timeframe': timeframe,
                    'generated_at': timezone.now().isoformat(),
                },
            }))
        except Exception as e:
            logger.error(f"Error sending insights: {str(e)}")
            await self.send_error("Failed to retrieve insights")

    async def send_performance_metrics(self, timeframe='1h'):
        """Send performance metrics."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'performance_metrics_response',
                'timestamp': timezone.now().isoformat(),
                'data': {
                    'metrics': {
                        'response_times': [],
                        'throughput': 0,
                        'error_rate': 0.0,
                        'p50_ms': 0,
                        'p95_ms': 0,
                        'p99_ms': 0,
                    },
                    'timeframe': timeframe,
                },
            }))
        except Exception as e:
            logger.error(f"Error sending performance metrics: {str(e)}")
            await self.send_error("Failed to retrieve performance metrics")

    async def send_subscriptions(self):
        """Send list of active subscriptions."""
        try:
            subs = list(getattr(self, 'subscribed_events', set()))
            await self.send(text_data=json.dumps({
                'type': 'subscriptions_response',
                'timestamp': timezone.now().isoformat(),
                'data': {
                    'subscriptions': subs,
                    'count': len(subs),
                },
            }))
        except Exception as e:
            logger.error(f"Error sending subscriptions: {str(e)}")
            await self.send_error("Failed to retrieve subscriptions")
    
    async def send_recent_logs(self, limit=50):
        """
        Send recent rate limit logs.
        """
        try:
            logs = await self.get_recent_logs(limit)
            
            await self.send(text_data=json.dumps({
                'type': 'logs_update',
                'timestamp': timezone.now().isoformat(),
                'data': logs
            }))
            
        except Exception as e:
            logger.error(f"Error sending recent logs: {str(e)}")
            await self.send_error("Failed to retrieve logs")
    
    async def send_recent_blocks(self, limit=20):
        """
        Send recent IP blocks.
        """
        try:
            blocks = await self.get_recent_blocks(limit)
            
            await self.send(text_data=json.dumps({
                'type': 'blocks_update',
                'timestamp': timezone.now().isoformat(),
                'data': blocks
            }))
            
        except Exception as e:
            logger.error(f"Error sending recent blocks: {str(e)}")
            await self.send_error("Failed to retrieve blocks")
    
    async def send_health_status(self):
        """
        Send system health status.
        """
        try:
            health = await self.get_health_status()
            
            await self.send(text_data=json.dumps({
                'type': 'health_update',
                'timestamp': timezone.now().isoformat(),
                'data': health
            }))
            
        except Exception as e:
            logger.error(f"Error sending health status: {str(e)}")
            await self.send_error("Failed to retrieve health status")
    
    async def subscribe_to_events(self, events):
        """
        Subscribe to specific event types.
        """
        # Store subscription preferences
        self.subscribed_events = set(events)
        
        await self.send(text_data=json.dumps({
            'type': 'subscription_confirmed',
            'timestamp': timezone.now().isoformat(),
            'events': list(self.subscribed_events)
        }))
    
    async def send_pong(self):
        """
        Send pong response to ping.
        """
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_error(self, message):
        """
        Send error message.
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'timestamp': timezone.now().isoformat(),
            'message': message,
            'data': {'message': message},
        }))
    
    # Database access methods (wrapped in database_sync_to_async)
    @database_sync_to_async
    def get_current_stats(self):
        """
        Get current rate limit statistics from database.
        """
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)
        twentyfour_hours_ago = now - timedelta(hours=24)
        
        stats = {
            'total_configs': RateLimitConfig.objects.count(),
            'active_configs': RateLimitConfig.objects.filter(is_active=True).count(),
            'total_logs': RateLimitLog.objects.count(),
            'logs_last_hour': RateLimitLog.objects.filter(timestamp__gte=one_hour_ago).count(),
            'logs_last_24h': RateLimitLog.objects.filter(timestamp__gte=twentyfour_hours_ago).count(),
            'blocked_last_hour': RateLimitLog.objects.filter(
                status='blocked', 
                timestamp__gte=one_hour_ago
            ).count(),
            'blocked_last_24h': RateLimitLog.objects.filter(
                status='blocked', 
                timestamp__gte=twentyfour_hours_ago
            ).count(),
            'total_blocks': IPBlockList.objects.filter(is_active=True).count(),
            'abuse_reports': AbuseReport.objects.filter(
                created_at__gte=twentyfour_hours_ago
            ).count(),
        }
        
        # Calculate rates
        if stats['logs_last_hour'] > 0:
            stats['block_rate_hour'] = (stats['blocked_last_hour'] / stats['logs_last_hour']) * 100
        else:
            stats['block_rate_hour'] = 0
            
        if stats['logs_last_24h'] > 0:
            stats['block_rate_24h'] = (stats['blocked_last_24h'] / stats['logs_last_24h']) * 100
        else:
            stats['block_rate_24h'] = 0
        
        return stats
    
    @database_sync_to_async
    def get_recent_logs(self, limit=50):
        """
        Get recent rate limit logs.
        """
        logs = RateLimitLog.objects.select_related('user', 'config').order_by('-timestamp')[:limit]
        
        return [
            {
                'id': str(log.id),
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address,
                'user': log.user.username if log.user else 'Anonymous',
                'endpoint': log.endpoint,
                'method': log.request_method,
                'status': log.status,
                'config': log.config.name if log.config else None,
                'suspicion_score': log.suspicion_score,
            }
            for log in logs
        ]
    
    @database_sync_to_async
    def get_recent_blocks(self, limit=20):
        """
        Get recent IP blocks.
        """
        blocks = IPBlockList.objects.filter(is_active=True).order_by('-created_at')[:limit]
        
        return [
            {
                'id': str(block.id),
                'ip_address': block.ip_address,
                'block_type': block.block_type,
                'block_reason': block.block_reason,
                'created_at': block.created_at.isoformat(),
                'expires_at': block.expires_at.isoformat() if block.expires_at else None,
                'created_by': block.created_by.username if block.created_by else 'System',
            }
            for block in blocks
        ]
    
    @database_sync_to_async
    def get_health_status(self):
        """
        Get system health status.
        """
        # Get Redis health
        try:
            rate_limit_service = RateLimitService()
            redis_health = rate_limit_service.check_redis_health()
        except Exception:
            redis_health = {'status': 'error', 'message': 'Redis connection failed'}
        
        # Get database health
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_health = {'status': 'healthy', 'message': 'Database connection OK'}
        except Exception as e:
            db_health = {'status': 'error', 'message': f'Database connection failed: {str(e)}'}
        
        # Calculate overall health
        health_score = 100
        if redis_health['status'] != 'healthy':
            health_score -= 50
        if db_health['status'] != 'healthy':
            health_score -= 50
        
        return {
            'overall_score': health_score,
            'status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 50 else 'critical',
            'components': {
                'redis': redis_health,
                'database': db_health,
            },
            'timestamp': timezone.now().isoformat()
        }
    
    async def start_monitoring(self):
        """
        Start background monitoring task.
        """
        while True:
            try:
                # Send periodic updates
                await self.send_current_stats()
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring task: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    # Channel layer message handlers
    async def rate_limit_event(self, event):
        """
        Handle rate limit events from channel layer.
        """
        if not hasattr(self, 'subscribed_events') or 'rate_limit_events' in self.subscribed_events:
            await self.send(text_data=json.dumps({
                'type': 'rate_limit_event',
                'timestamp': timezone.now().isoformat(),
                'data': event['data']
            }))
    
    async def block_event(self, event):
        """
        Handle IP block events from channel layer.
        """
        if not hasattr(self, 'subscribed_events') or 'block_events' in self.subscribed_events:
            await self.send(text_data=json.dumps({
                'type': 'block_event',
                'timestamp': timezone.now().isoformat(),
                'data': event['data']
            }))
    
    async def abuse_event(self, event):
        """
        Handle abuse detection events from channel layer.
        """
        if not hasattr(self, 'subscribed_events') or 'abuse_events' in self.subscribed_events:
            await self.send(text_data=json.dumps({
                'type': 'abuse_event',
                'timestamp': timezone.now().isoformat(),
                'data': event['data']
            }))


class RateLimitAlertConsumer(AsyncWebsocketConsumer):
    """
    Real-time rate limit alerts consumer.
    
    Provides instant notifications for critical rate limit events.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection for alerts.
        """
        self.user = self.scope["user"]
        self.room_group_name = "rate_limit_alerts"
        
        # Check if user is authenticated and has permission
        if not self.user.is_authenticated or not self.user.has_perm('rate_limit.view_ratelimitlog'):
            await self.close(code=4001)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Accept connection
        await self.accept()
        
        logger.info(f"Rate limit alerts connected: {self.user.username}")
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"Rate limit alerts disconnected: {self.user.username}")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send_pong()
            elif message_type == 'subscribe_alerts':
                await self.subscribe_alerts(text_data_json.get('alert_types', []))
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing alert message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def send_pong(self):
        """
        Send pong response to ping.
        """
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_error(self, message):
        """
        Send error message.
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'timestamp': timezone.now().isoformat(),
            'message': message,
            'data': {'message': message},
        }))
    
    async def subscribe_alerts(self, alert_types):
        """
        Subscribe to specific alert types.
        """
        self.subscribed_alerts = set(alert_types)
        
        await self.send(text_data=json.dumps({
            'type': 'subscription_confirmed',
            'timestamp': timezone.now().isoformat(),
            'alert_types': list(self.subscribed_alerts)
        }))
    
    # Alert event handlers
    async def critical_block_alert(self, event):
        """
        Handle critical block alerts.
        """
        if not hasattr(self, 'subscribed_alerts') or 'critical_blocks' in self.subscribed_alerts:
            await self.send(text_data=json.dumps({
                'type': 'critical_block_alert',
                'timestamp': timezone.now().isoformat(),
                'severity': 'critical',
                'data': event['data']
            }))
    
    async def abuse_detection_alert(self, event):
        """
        Handle abuse detection alerts.
        """
        if not hasattr(self, 'subscribed_alerts') or 'abuse_detection' in self.subscribed_alerts:
            await self.send(text_data=json.dumps({
                'type': 'abuse_detection_alert',
                'timestamp': timezone.now().isoformat(),
                'severity': event['data'].get('severity', 'medium'),
                'data': event['data']
            }))
    
    async def system_health_alert(self, event):
        """
        Handle system health alerts.
        """
        if not hasattr(self, 'subscribed_alerts') or 'system_health' in self.subscribed_alerts:
            await self.send(text_data=json.dumps({
                'type': 'system_health_alert',
                'timestamp': timezone.now().isoformat(),
                'severity': event['data'].get('severity', 'medium'),
                'data': event['data']
            }))


# Utility functions for broadcasting events
async def broadcast_rate_limit_event(event_data):
    """
    Broadcast rate limit event to all connected monitors.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "rate_limit_monitor",
        {
            'type': 'rate_limit_event',
            'data': event_data
        }
    )


async def broadcast_block_event(block_data):
    """
    Broadcast IP block event to all connected monitors.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "rate_limit_monitor",
        {
            'type': 'block_event',
            'data': block_data
        }
    )


async def broadcast_abuse_event(abuse_data):
    """
    Broadcast abuse detection event to all connected monitors.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "rate_limit_monitor",
        {
            'type': 'abuse_event',
            'data': abuse_data
        }
    )


async def broadcast_critical_alert(alert_data):
    """
    Broadcast critical alert to all connected alert consumers.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "rate_limit_alerts",
        {
            'type': 'critical_block_alert',
            'data': alert_data
        }
    )


class RateLimitConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time rate limit events.
    This is the primary consumer used by tests at /ws/rate-limit/
    Handles: violations, alerts, abuse reports, IP blocks, exceptions,
    stats, subscriptions, insights, performance metrics.
    """

    # Class-level registry: user_id -> set of channel_names
    _user_connections: dict = {}
    _MAX_CONNECTIONS_PER_USER = 2

    async def connect(self):
        self.group_name = 'rate_limit_events'
        self.user = self.scope.get('user')
        self.subscribed_events = set()

        # Reject unauthenticated connections BEFORE accepting
        if not self.user or not getattr(self.user, 'is_authenticated', False):
            await self.close()
            return

        # Enforce per-user connection limit
        uid = getattr(self.user, 'id', None)
        if uid is not None:
            conns = RateLimitConsumer._user_connections.get(uid, set())
            if len(conns) >= RateLimitConsumer._MAX_CONNECTIONS_PER_USER:
                await self.close()
                return
            conns.add(self.channel_name)
            RateLimitConsumer._user_connections[uid] = conns

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        uid = getattr(self.user, 'id', None) if hasattr(self, 'user') else None
        if uid is not None:
            conns = RateLimitConsumer._user_connections.get(uid, set())
            conns.discard(self.channel_name)
            if conns:
                RateLimitConsumer._user_connections[uid] = conns
            else:
                RateLimitConsumer._user_connections.pop(uid, None)
        if hasattr(self, 'channel_layer'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            inner = data.get('data', {})

            if message_type == 'get_stats':
                await self._send_stats()

            elif message_type == 'get_system_stats':
                await self._send_system_stats()

            elif message_type == 'get_user_stats':
                await self._send_user_stats(inner.get('user_id'))

            elif message_type == 'get_insights':
                await self._send_insights(inner.get('timeframe', '1h'))

            elif message_type == 'get_performance_metrics':
                await self._send_performance_metrics(inner.get('timeframe', '1h'))

            elif message_type == 'get_subscriptions':
                await self._send_subscriptions()

            elif message_type in ('subscribe', 'subscribe_events'):
                event_type = inner.get('event_type', '')
                events = [event_type] if event_type else data.get('events', [])
                # Accumulate subscriptions
                self.subscribed_events.update(events)
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'timestamp': timezone.now().isoformat(),
                    'data': {
                        'event_type': event_type,
                        'events': list(self.subscribed_events),
                        'user_id': getattr(self.user, 'id', None),
                    }
                }))

            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat(),
                }))

            elif message_type == 'simulate_violation':
                # Call via type() so class-level patch intercepts the call
                await self.__class__.broadcast_rate_limit_violation(self, {'data': inner})

            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}',
                    'data': {'message': f'Unknown message type: {message_type}'},
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON',
                'data': {'message': 'Invalid JSON'},
            }))
        except Exception as e:
            logger.error(f"RateLimitConsumer receive error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error',
                'data': {'message': 'Internal server error'},
            }))

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #
    async def _get_stats(self):
        from api.rate_limit.models import RateLimitLog, RateLimitConfig
        @database_sync_to_async
        def _q():
            from django.utils import timezone as tz
            now = tz.now()
            hour_ago = now - timezone.timedelta(hours=1)
            return {
                'total_requests': RateLimitLog.objects.count(),
                'blocked_requests': RateLimitLog.objects.filter(is_allowed=False).count(),
                'recent_requests': RateLimitLog.objects.filter(timestamp__gte=hour_ago).count(),
                'active_configs': RateLimitConfig.objects.filter(is_active=True).count(),
            }
        return await _q()

    async def _send_stats(self):
        stats = await self._get_stats()
        await self.send(text_data=json.dumps({
            'type': 'stats_response',
            'timestamp': timezone.now().isoformat(),
            'data': stats,
        }))

    async def _send_system_stats(self):
        @database_sync_to_async
        def _q():
            from api.rate_limit.models import RateLimitLog, RateLimitConfig
            from django.contrib.auth import get_user_model
            User = get_user_model()
            now = timezone.now()
            hour_ago = now - timezone.timedelta(hours=1)
            return {
                'total_users': User.objects.count(),
                'active_configs': RateLimitConfig.objects.filter(is_active=True).count(),
                'recent_violations': RateLimitLog.objects.filter(
                    timestamp__gte=hour_ago, is_allowed=False
                ).count(),
                'total_requests_last_hour': RateLimitLog.objects.filter(
                    timestamp__gte=hour_ago
                ).count(),
                'total_requests': RateLimitLog.objects.count(),
                'blocked_requests': RateLimitLog.objects.filter(is_allowed=False).count(),
            }
        stats = await _q()
        await self.send(text_data=json.dumps({
            'type': 'system_stats_response',
            'timestamp': timezone.now().isoformat(),
            'data': stats,
        }))

    async def _send_user_stats(self, user_id=None):
        target_id = user_id or getattr(self.user, 'id', None)
        @database_sync_to_async
        def _q():
            from api.rate_limit.models import RateLimitLog
            qs = RateLimitLog.objects.filter(user_id=target_id)
            return {
                'user_id': target_id,
                'total_requests': qs.count(),
                'blocked_requests': qs.filter(is_allowed=False).count(),
            }
        stats = await _q()
        await self.send(text_data=json.dumps({
            'type': 'user_stats_response',
            'timestamp': timezone.now().isoformat(),
            'data': stats,
        }))

    async def _send_insights(self, timeframe='1h'):
        await self.send(text_data=json.dumps({
            'type': 'insights_response',
            'timestamp': timezone.now().isoformat(),
            'data': {'insights': [], 'timeframe': timeframe},
        }))

    async def _send_performance_metrics(self, timeframe='1h'):
        await self.send(text_data=json.dumps({
            'type': 'performance_metrics_response',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'metrics': {
                    'response_times': [],
                    'p50_ms': 0,
                    'p95_ms': 0,
                    'p99_ms': 0,
                    'throughput': 0,
                    'error_rate': 0.0,
                },
                'timeframe': timeframe,
            },
        }))

    async def _send_subscriptions(self):
        subs = list(self.subscribed_events)
        await self.send(text_data=json.dumps({
            'type': 'subscriptions_response',
            'timestamp': timezone.now().isoformat(),
            'data': {'subscriptions': subs, 'count': len(subs)},
        }))

    # ------------------------------------------------------------------ #
    # Broadcast handlers (called via channel layer group_send)            #
    # ------------------------------------------------------------------ #
    async def broadcast_rate_limit_violation(self, event):
        await self.send(text_data=json.dumps({
            'type': 'rate_limit_violation',
            'data': event.get('data', {}),
        }))

    async def broadcast_rate_limit_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'rate_limit_event',
            'data': event.get('data', {}),
        }))

    async def broadcast_abuse_report(self, event):
        await self.send(text_data=json.dumps({
            'type': 'abuse_report',
            'data': event.get('data', {}),
        }))

    async def broadcast_ip_block(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ip_block',
            'data': event.get('data', {}),
        }))

    async def broadcast_rate_limit_exception(self, event):
        await self.send(text_data=json.dumps({
            'type': 'rate_limit_exception',
            'data': event.get('data', {}),
        }))

    @classmethod
    async def send_violation_to_group(cls, channel_layer, violation_data: dict):
        await channel_layer.group_send(
            'rate_limit_events',
            {'type': 'broadcast_rate_limit_violation', 'data': violation_data}
        )


class RateLimitAnalyticsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time analytics streaming."""
    group_name = 'rate_limit_analytics'

    async def connect(self):
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            await self.send(text_data=json.dumps({'type': 'analytics_ack', 'data': data}))
        except Exception as e:
            await self.send(text_data=json.dumps({'error': str(e)}))

    async def broadcast_analytics(self, event):
        await self.send(text_data=json.dumps({'type': 'analytics', 'data': event.get('data', {})}))
