"""
Security WebSocket Consumers
Real-time security event streaming and monitoring
Author: System Security Team
Version: 1.0.0
"""
from django.db.models import Count
from django.urls import path

import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone
from typing import Dict, List, Any, Optional
import asyncio

logger = logging.getLogger(__name__)


class SecurityEventConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time security events
    """
    
    async def connect(self):
        """
        Handle WebSocket connection
        """
        try:
            # Authenticate user
            self.user = self.scope.get('user')
            if not self.user or self.user.is_anonymous:
                await self.close(code=4001)
                return
            
            # Check permissions
            if not await self.has_security_permissions():
                await self.close(code=4003)
                return
            
            # Create unique group for this user
            self.group_name = f"security_user_{self.user.id}"
            
            # Join user group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Join global security group if admin
            if await self.is_security_admin():
                await self.channel_layer.group_add(
                    "security_global",
                    self.channel_name
                )
            
            # Accept connection
            await self.accept()
            
            # Send initial status
            await self.send_initial_status()
            
            # Log connection
            await self.log_security_event('websocket_connected')
            
        except Exception as e:
            logger.error(f"Error in SecurityEventConsumer.connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        try:
            # Leave groups
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            
            if await self.is_security_admin():
                await self.channel_layer.group_discard(
                    "security_global",
                    self.channel_name
                )
            
            # Log disconnection
            await self.log_security_event('websocket_disconnected', {
                'close_code': close_code
            })
            
        except Exception as e:
            logger.error(f"Error in SecurityEventConsumer.disconnect: {e}")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'unknown')
            
            if message_type == 'subscribe':
                await self.handle_subscription(data)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscription(data)
            elif message_type == 'ping':
                await self.handle_ping()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error in SecurityEventConsumer.receive: {e}")
            await self.send_error("Internal server error")
    
    async def handle_subscription(self, data):
        """
        Handle subscription to specific security events
        """
        try:
            event_types = data.get('event_types', [])
            
            if not isinstance(event_types, list):
                await self.send_error("event_types must be a list")
                return
            
            # Validate event types
            valid_types = [
                'login_attempts', 'security_breaches', 'threat_alerts',
                'system_alerts', 'user_activity', 'ip_blacklist',
                'device_trust', 'rate_limits', 'vulnerability_scans'
            ]
            
            invalid_types = [t for t in event_types if t not in valid_types]
            if invalid_types:
                await self.send_error(f"Invalid event types: {invalid_types}")
                return
            
            # Store subscriptions in cache
            cache_key = f"security_subscriptions_{self.user.id}"
            current_subscriptions = cache.get(cache_key, [])
            
            # Add new subscriptions
            for event_type in event_types:
                if event_type not in current_subscriptions:
                    current_subscriptions.append(event_type)
                    # Join event-specific group
                    await self.channel_layer.group_add(
                        f"security_event_{event_type}",
                        self.channel_name
                    )
            
            cache.set(cache_key, current_subscriptions, timeout=3600)
            
            await self.send_success({
                'message': f"Subscribed to {len(event_types)} event types",
                'subscriptions': current_subscriptions
            })
            
        except Exception as e:
            logger.error(f"Error in handle_subscription: {e}")
            await self.send_error("Subscription failed")
    
    async def handle_unsubscription(self, data):
        """
        Handle unsubscription from specific security events
        """
        try:
            event_types = data.get('event_types', [])
            
            if not isinstance(event_types, list):
                await self.send_error("event_types must be a list")
                return
            
            # Get current subscriptions
            cache_key = f"security_subscriptions_{self.user.id}"
            current_subscriptions = cache.get(cache_key, [])
            
            # Remove subscriptions
            for event_type in event_types:
                if event_type in current_subscriptions:
                    current_subscriptions.remove(event_type)
                    # Leave event-specific group
                    await self.channel_layer.group_discard(
                        f"security_event_{event_type}",
                        self.channel_name
                    )
            
            cache.set(cache_key, current_subscriptions, timeout=3600)
            
            await self.send_success({
                'message': f"Unsubscribed from {len(event_types)} event types",
                'subscriptions': current_subscriptions
            })
            
        except Exception as e:
            logger.error(f"Error in handle_unsubscription: {e}")
            await self.send_error("Unsubscription failed")
    
    async def handle_ping(self):
        """
        Handle ping message
        """
        await self.send_success({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        })
    
    async def send_initial_status(self):
        """
        Send initial connection status
        """
        try:
            # Get user's current subscriptions
            cache_key = f"security_subscriptions_{self.user.id}"
            subscriptions = cache.get(cache_key, [])
            
            await self.send_success({
                'type': 'connection_status',
                'status': 'connected',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_admin': await self.is_security_admin(),
                'subscriptions': subscriptions,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in send_initial_status: {e}")
    
    async def send_security_event(self, event_data: Dict[str, Any]):
        """
        Send security event to client
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'security_event',
                'data': event_data,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in send_security_event: {e}")
    
    async def send_success(self, data: Dict[str, Any]):
        """
        Send success message
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'success',
                'data': data,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in send_success: {e}")
    
    async def send_error(self, message: str):
        """
        Send error message
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': message,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in send_error: {e}")
    
    @database_sync_to_async
    def has_security_permissions(self) -> bool:
        """
        Check if user has security permissions
        """
        try:
            return (
                self.user.is_staff or
                self.user.is_superuser or
                self.user.has_perm('security.view_security_logs') or
                self.user.has_perm('security.manage_security')
            )
        except Exception:
            return False
    
    @database_sync_to_async
    def is_security_admin(self) -> bool:
        """
        Check if user is security admin
        """
        try:
            return (
                self.user.is_superuser or
                self.user.has_perm('security.manage_security')
            )
        except Exception:
            return False
    
    @database_sync_to_async
    def log_security_event(self, event_type: str, metadata: Dict[str, Any] = None):
        """
        Log security event
        """
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                user=self.user,
                security_type=event_type,
                severity='info',
                ip_address=self.get_client_ip(),
                user_agent=self.get_user_agent(),
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
    
    def get_client_ip(self) -> str:
        """
        Get client IP address
        """
        # Implementation depends on ASGI scope
        return self.scope.get('client', ['127.0.0.1'])[0]
    
    def get_user_agent(self) -> str:
        """
        Get user agent
        """
        # Implementation depends on ASGI scope
        headers = dict(self.scope.get('headers', []))
        return headers.get(b'user-agent', b'').decode('utf-8')


class SecurityDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for security dashboard updates
    """
    
    async def connect(self):
        """
        Handle dashboard connection
        """
        try:
            # Authenticate user
            self.user = self.scope.get('user')
            if not self.user or self.user.is_anonymous:
                await self.close(code=4001)
                return
            
            # Check dashboard permissions
            if not await self.has_dashboard_permissions():
                await self.close(code=4003)
                return
            
            # Create dashboard group
            self.group_name = f"security_dashboard_{self.user.id}"
            
            # Join dashboard group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Join global dashboard group if admin
            if await self.is_security_admin():
                await self.channel_layer.group_add(
                    "security_dashboard_global",
                    self.channel_name
                )
            
            # Accept connection
            await self.accept()
            
            # Send initial dashboard data
            await self.send_dashboard_initial_data()
            
        except Exception as e:
            logger.error(f"Error in SecurityDashboardConsumer.connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """
        Handle dashboard disconnection
        """
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            
            if await self.is_security_admin():
                await self.channel_layer.group_discard(
                    "security_dashboard_global",
                    self.channel_name
                )
                
        except Exception as e:
            logger.error(f"Error in SecurityDashboardConsumer.disconnect: {e}")
    
    async def receive(self, text_data):
        """
        Handle dashboard messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'unknown')
            
            if message_type == 'refresh_data':
                await self.send_dashboard_data()
            elif message_type == 'get_metrics':
                await self.send_security_metrics()
            elif message_type == 'ping':
                await self.handle_ping()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error in SecurityDashboardConsumer.receive: {e}")
            await self.send_error("Internal server error")
    
    async def send_dashboard_initial_data(self):
        """
        Send initial dashboard data
        """
        try:
            dashboard_data = await self.get_dashboard_data()
            await self.send_success({
                'type': 'dashboard_initial',
                'data': dashboard_data
            })
            
        except Exception as e:
            logger.error(f"Error in send_dashboard_initial_data: {e}")
            await self.send_error("Failed to load dashboard data")
    
    async def send_dashboard_data(self):
        """
        Send updated dashboard data
        """
        try:
            dashboard_data = await self.get_dashboard_data()
            await self.send_success({
                'type': 'dashboard_update',
                'data': dashboard_data
            })
            
        except Exception as e:
            logger.error(f"Error in send_dashboard_data: {e}")
            await self.send_error("Failed to update dashboard data")
    
    async def send_security_metrics(self):
        """
        Send security metrics
        """
        try:
            metrics = await self.get_security_metrics()
            await self.send_success({
                'type': 'security_metrics',
                'data': metrics
            })
            
        except Exception as e:
            logger.error(f"Error in send_security_metrics: {e}")
            await self.send_error("Failed to load security metrics")
    
    async def handle_ping(self):
        """
        Handle ping message
        """
        await self.send_success({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        })
    
    @database_sync_to_async
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data
        """
        try:
            from .models import SecurityLog, SecurityIncident, UserBan, IPBlacklist
            
            # Get recent statistics
            now = timezone.now()
            last_24h = now - timezone.timedelta(hours=24)
            last_7d = now - timezone.timedelta(days=7)
            
            return {
                'overview': {
                    'total_security_events': SecurityLog.objects.filter(created_at__gte=last_24h).count(),
                    'active_incidents': SecurityIncident.objects.filter(status='open').count(),
                    'banned_users': UserBan.objects.filter(is_active=True).count(),
                    'blocked_ips': IPBlacklist.objects.filter(is_active=True).count(),
                },
                'recent_events': [
                    {
                        'id': log.id,
                        'event_type': log.event_type,
                        'severity': log.severity,
                        'created_at': log.created_at.isoformat(),
                        'user': log.user.username if log.user else None,
                        'ip_address': log.ip_address
                    }
                    for log in SecurityLog.objects.filter(
                        created_at__gte=last_24h
                    ).order_by('-created_at')[:10]
                ],
                'threat_summary': {
                    'high_risk_events': SecurityLog.objects.filter(
                        created_at__gte=last_24h,
                        severity__in=['error', 'critical', 'security']
                    ).count(),
                    'suspicious_logins': SecurityLog.objects.filter(
                        created_at__gte=last_24h,
                        security_type__contains='login'
                    ).count(),
                    'vpn_detections': SecurityLog.objects.filter(
                        created_at__gte=last_24h,
                        security_type='vpn_detected'
                    ).count(),
                },
                'trends': {
                    'daily_events': SecurityLog.objects.filter(
                        created_at__gte=last_7d
                    ).extra(
                        select={'day': 'date(created_at)'}
                    ).values('day').annotate(count=Count('id')).order_by('day')
                }
            }
            
        except Exception as e:
            logger.error(f"Error in get_dashboard_data: {e}")
            return {}
    
    @database_sync_to_async
    def get_security_metrics(self) -> Dict[str, Any]:
        """
        Get security metrics
        """
        try:
            from .models import SecurityLog, RiskScore
            
            return {
                'event_types': list(
                    SecurityLog.objects.values('event_type')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:10]
                ),
                'severity_distribution': list(
                    SecurityLog.objects.values('severity')
                    .annotate(count=Count('id'))
                    .order_by('severity')
                ),
                'risk_scores': list(
                    RiskScore.objects.values('current_score')
                    .annotate(count=Count('id'))
                    .order_by('current_score')
                ),
            }
            
        except Exception as e:
            logger.error(f"Error in get_security_metrics: {e}")
            return {}
    
    async def send_success(self, data: Dict[str, Any]):
        """
        Send success message
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'success',
                'data': data,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in send_success: {e}")
    
    async def send_error(self, message: str):
        """
        Send error message
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': message,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in send_error: {e}")
    
    @database_sync_to_async
    def has_dashboard_permissions(self) -> bool:
        """
        Check if user has dashboard permissions
        """
        try:
            return (
                self.user.is_staff or
                self.user.is_superuser or
                self.user.has_perm('security.view_security_dashboard')
            )
        except Exception:
            return False
    
    @database_sync_to_async
    def is_security_admin(self) -> bool:
        """
        Check if user is security admin
        """
        try:
            return (
                self.user.is_superuser or
                self.user.has_perm('security.manage_security')
            )
        except Exception:
            return False


# WebSocket routing configuration
websocket_urlpatterns = [
    path('ws/security/events/', SecurityEventConsumer.as_asgi()),
    path('ws/security/dashboard/', SecurityDashboardConsumer.as_asgi()),
]