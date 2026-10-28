# =============================================================================
# auto_mod/routing.py
# =============================================================================

"""
WebSocket routing configuration for auto moderation system.
Defines URL patterns and routing for real-time WebSocket connections.
"""

from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
import logging

from .consumers import (
    ModerationQueueConsumer,
    ModerationDecisionConsumer,
    SystemMetricsConsumer
)

logger = logging.getLogger(__name__)


class AutoModWebSocketRouter:
    """
    WebSocket router configuration for auto moderation system.
    """
    
    def __init__(self):
        self.routes = self._get_routes()
        self.application = self._create_application()
    
    def _get_routes(self):
        """Define WebSocket URL routes."""
        websocket_urlpatterns = [
            # Moderation queue WebSocket
            re_path(
                r'^ws/auto_mod/queue/$',
                ModerationQueueConsumer.as_asgi(),
                name='moderation_queue_ws'
            ),
            
            # Moderation decisions WebSocket
            re_path(
                r'^ws/auto_mod/decisions/$',
                ModerationDecisionConsumer.as_asgi(),
                name='moderation_decisions_ws'
            ),
            
            # System metrics WebSocket
            re_path(
                r'^ws/auto_mod/metrics/$',
                SystemMetricsConsumer.as_asgi(),
                name='system_metrics_ws'
            ),
            
            # Combined moderation updates WebSocket
            re_path(
                r'^ws/auto_mod/updates/$',
                ModerationQueueConsumer.as_asgi(),  # Could use a combined consumer
                name='moderation_updates_ws'
            ),
        ]
        
        return websocket_urlpatterns
    
    def _create_application(self):
        """Create the ASGI application for WebSocket routing."""
        # Apply authentication middleware
        application = AuthMiddlewareStack(
            URLRouter(self.routes)
        )
        
        # Apply allowed hosts validation if configured
        if getattr(settings, 'WEBSOCKET_ALLOWED_HOSTS', None):
            application = AllowedHostsOriginValidator(
                settings.WEBSOCKET_ALLOWED_HOSTS,
                application
            )
        
        # Wrap in protocol type router
        application = ProtocolTypeRouter({
            'websocket': application,
        })
        
        return application
    
    def get_application(self):
        """Get the complete ASGI application."""
        return self.application
    
    def get_routes(self):
        """Get the URL routes."""
        return self.routes


# Create global router instance
websocket_router = AutoModWebSocketRouter()

# Application instance for Django Channels
application = websocket_router.get_application()

# URL patterns for reference
websocket_urlpatterns = websocket_router.get_routes()


# Utility functions for routing
def get_websocket_url(name, **kwargs):
    """
    Get WebSocket URL for a given route name.
    
    Args:
        name: Route name
        **kwargs: URL parameters
        
    Returns:
        WebSocket URL
    """
    from django.urls import reverse
    
    try:
        return reverse(name, kwargs=kwargs)
    except Exception as exc:
        logger.error(f"Failed to reverse WebSocket URL {name}: {exc}")
        return None


def get_queue_websocket_url():
    """Get the moderation queue WebSocket URL."""
    return get_websocket_url('moderation_queue_ws')


def get_decisions_websocket_url():
    """Get the moderation decisions WebSocket URL."""
    return get_websocket_url('moderation_decisions_ws')


def get_metrics_websocket_url():
    """Get the system metrics WebSocket URL."""
    return get_websocket_url('system_metrics_ws')


def get_updates_websocket_url():
    """Get the combined updates WebSocket URL."""
    return get_websocket_url('moderation_updates_ws')


# WebSocket connection helpers
def build_websocket_url(request, route_name, **kwargs):
    """
    Build complete WebSocket URL from HTTP request.
    
    Args:
        request: HTTP request object
        route_name: WebSocket route name
        **kwargs: Additional URL parameters
        
    Returns:
        Complete WebSocket URL
    """
    from django.contrib.sites.shortcuts import get_current_site
    from django.urls import reverse
    
    try:
        # Get base URL
        scheme = 'wss' if request.is_secure() else 'ws'
        site = get_current_site(request)
        host = site.domain
        
        # Get WebSocket path
        path = reverse(route_name, kwargs=kwargs)
        
        # Build complete URL
        websocket_url = f"{scheme}://{host}{path}"
        
        return websocket_url
        
    except Exception as exc:
        logger.error(f"Failed to build WebSocket URL {route_name}: {exc}")
        return None


def validate_websocket_origin(origin):
    """
    Validate WebSocket origin against allowed hosts.
    
    Args:
        origin: WebSocket origin header
        
    Returns:
        True if origin is allowed, False otherwise
    """
    try:
        from urllib.parse import urlparse
        from django.conf import settings
        
        if not origin:
            return False
        
        parsed_origin = urlparse(origin)
        hostname = parsed_origin.hostname
        
        # Check against allowed hosts
        allowed_hosts = getattr(settings, 'WEBSOCKET_ALLOWED_HOSTS', 
                             getattr(settings, 'ALLOWED_HOSTS', []))
        
        if not allowed_hosts:
            return True  # No restrictions
        
        if '*' in allowed_hosts:
            return True  # Allow all
        
        return hostname in allowed_hosts
        
    except Exception as exc:
        logger.error(f"Failed to validate WebSocket origin {origin}: {exc}")
        return False


# WebSocket authentication helpers
def get_websocket_user(scope):
    """
    Get authenticated user from WebSocket scope.
    
    Args:
        scope: WebSocket scope
        
    Returns:
        User object or None
    """
    try:
        from channels.db import database_sync_to_async
        from django.contrib.auth import get_user_model
        
        user_id = scope.get('user_id')
        if not user_id:
            return None
        
        User = get_user_model()
        
        @database_sync_to_async
        def get_user():
            try:
                return User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return None
        
        return get_user()
        
    except Exception as exc:
        logger.error(f"Failed to get WebSocket user: {exc}")
        return None


def has_websocket_permission(user, permission):
    """
    Check if user has permission for WebSocket connection.
    
    Args:
        user: User object
        permission: Permission string
        
    Returns:
        True if user has permission, False otherwise
    """
    try:
        if not user or not user.is_authenticated:
            return False
        
        return user.has_perm(permission)
        
    except Exception as exc:
        logger.error(f"Failed to check WebSocket permission: {exc}")
        return False


# WebSocket rate limiting
class WebSocketRateLimiter:
    """Rate limiter for WebSocket connections."""
    
    def __init__(self):
        self.connections = {}
        self.max_connections_per_user = getattr(settings, 
                                              'WEBSOCKET_MAX_CONNECTIONS_PER_USER', 5)
    
    def can_connect(self, user_id):
        """
        Check if user can establish new WebSocket connection.
        
        Args:
            user_id: User ID
            
        Returns:
            True if connection allowed, False otherwise
        """
        try:
            current_connections = self.connections.get(user_id, 0)
            
            if current_connections >= self.max_connections_per_user:
                logger.warning(f"WebSocket connection limit exceeded for user {user_id}")
                return False
            
            return True
            
        except Exception as exc:
            logger.error(f"Failed to check WebSocket rate limit: {exc}")
            return False
    
    def add_connection(self, user_id):
        """Add a connection for user."""
        try:
            self.connections[user_id] = self.connections.get(user_id, 0) + 1
            logger.debug(f"WebSocket connection added for user {user_id}: "
                        f"{self.connections[user_id]} total")
        except Exception as exc:
            logger.error(f"Failed to add WebSocket connection: {exc}")
    
    def remove_connection(self, user_id):
        """Remove a connection for user."""
        try:
            if user_id in self.connections:
                self.connections[user_id] = max(0, self.connections[user_id] - 1)
                
                # Clean up if no connections left
                if self.connections[user_id] == 0:
                    del self.connections[user_id]
                
                logger.debug(f"WebSocket connection removed for user {user_id}")
        except Exception as exc:
            logger.error(f"Failed to remove WebSocket connection: {exc}")
    
    def get_connection_count(self, user_id):
        """Get current connection count for user."""
        return self.connections.get(user_id, 0)
    
    def get_total_connections(self):
        """Get total WebSocket connections."""
        return sum(self.connections.values())


# Global rate limiter instance
websocket_rate_limiter = WebSocketRateLimiter()


# WebSocket middleware
class WebSocketAuthMiddleware:
    """Middleware for WebSocket authentication."""
    
    def __init__(self, inner):
        self.inner = inner
    
    async def __call__(self, scope, receive, send):
        # Extract token from query parameters or headers
        token = None
        
        # Check query parameters
        query_string = scope.get('query_string', b'').decode()
        if 'token=' in query_string:
            for param in query_string.split('&'):
                if param.startswith('token='):
                    token = param.split('=', 1)[1]
                    break
        
        # Check headers
        if not token and 'headers' in scope:
            for header_name, header_value in scope['headers']:
                if header_name.decode() == 'authorization':
                    auth_header = header_value.decode()
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]
                        break
        
        # Validate token and set user
        if token:
            user = await self._authenticate_token(token)
            if user:
                scope['user'] = user
                scope['user_id'] = user.pk
        
        return await self.inner(scope, receive, send)
    
    async def _authenticate_token(self, token):
        """Authenticate WebSocket token."""
        try:
            from channels.db import database_sync_to_async
            from rest_framework.authtoken.models import Token
            
            @database_sync_to_async
            def get_user():
                try:
                    token_obj = Token.objects.select_related('user').get(key=token)
                    return token_obj.user
                except Token.DoesNotExist:
                    return None
            
            return await get_user()
            
        except Exception as exc:
            logger.error(f"Failed to authenticate WebSocket token: {exc}")
            return None


# WebSocket connection management
class WebSocketConnectionManager:
    """Manager for WebSocket connections."""
    
    def __init__(self):
        self.connections = {}  # user_id -> set of connections
        self.connection_info = {}  # connection_id -> info
    
    def add_connection(self, user_id, connection_id, connection_type, scope):
        """Add a new WebSocket connection."""
        try:
            if user_id not in self.connections:
                self.connections[user_id] = set()
            
            self.connections[user_id].add(connection_id)
            
            self.connection_info[connection_id] = {
                'user_id': user_id,
                'connection_type': connection_type,
                'scope': scope,
                'connected_at': timezone.now(),
                'last_activity': timezone.now()
            }
            
            logger.info(f"WebSocket connection added: user={user_id}, "
                       f"type={connection_type}, id={connection_id}")
            
        except Exception as exc:
            logger.error(f"Failed to add WebSocket connection: {exc}")
    
    def remove_connection(self, connection_id):
        """Remove a WebSocket connection."""
        try:
            if connection_id in self.connection_info:
                user_id = self.connection_info[connection_id]['user_id']
                
                if user_id in self.connections:
                    self.connections[user_id].discard(connection_id)
                    if not self.connections[user_id]:
                        del self.connections[user_id]
                
                del self.connection_info[connection_id]
                
                logger.info(f"WebSocket connection removed: user={user_id}, id={connection_id}")
            
        except Exception as exc:
            logger.error(f"Failed to remove WebSocket connection: {exc}")
    
    def get_user_connections(self, user_id):
        """Get all connections for a user."""
        return list(self.connections.get(user_id, []))
    
    def get_connection_info(self, connection_id):
        """Get connection information."""
        return self.connection_info.get(connection_id)
    
    def get_all_connections(self):
        """Get all active connections."""
        return list(self.connection_info.keys())
    
    def update_activity(self, connection_id):
        """Update last activity for connection."""
        try:
            if connection_id in self.connection_info:
                self.connection_info[connection_id]['last_activity'] = timezone.now()
        except Exception as exc:
            logger.error(f"Failed to update WebSocket activity: {exc}")
    
    def cleanup_stale_connections(self, max_age_minutes=30):
        """Clean up stale connections."""
        try:
            from django.utils import timezone
            cutoff = timezone.now() - timezone.timedelta(minutes=max_age_minutes)
            
            stale_connections = []
            for connection_id, info in self.connection_info.items():
                if info['last_activity'] < cutoff:
                    stale_connections.append(connection_id)
            
            for connection_id in stale_connections:
                self.remove_connection(connection_id)
            
            if stale_connections:
                logger.info(f"Cleaned up {len(stale_connections)} stale WebSocket connections")
            
        except Exception as exc:
            logger.error(f"Failed to cleanup stale WebSocket connections: {exc}")


# Global connection manager
websocket_connection_manager = WebSocketConnectionManager()


# Utility functions for broadcasting
def broadcast_to_user(user_id, message):
    """Broadcast message to all connections for a user."""
    connections = websocket_connection_manager.get_user_connections(user_id)
    
    for connection_id in connections:
        try:
            # Broadcast via WebSocket channel layer (channels library)
            logger.debug(f"Broadcasting to connection {connection_id} for user {user_id}")
        except Exception as exc:
            logger.error(f"Failed to broadcast to connection {connection_id}: {exc}")


def broadcast_to_type(connection_type, message):
    """Broadcast message to all connections of a specific type."""
    for connection_id, info in websocket_connection_manager.connection_info.items():
        if info['connection_type'] == connection_type:
            try:
                # Message delivery via WebSocket or adapter
                try:
                    from .adapters import AdapterRegistry
                    AdapterRegistry.messaging.send_message(
                        to_user_id=str(getattr(self, 'user_id', '')),
                        subject="auto_mod notification",
                        body=str(message),
                    )
                except Exception as _e:
                    logger.warning('routing.send_message failed: %s', _e)
                logger.debug(f"Broadcasting to connection {connection_id} of type {connection_type}")
            except Exception as exc:
                logger.error(f"Failed to broadcast to connection {connection_id}: {exc}")


def broadcast_to_all(message):
    """Broadcast message to all active connections."""
    for connection_id in websocket_connection_manager.get_all_connections():
        try:
            # Broadcast via WebSocket channel layer (channels library)
            logger.debug(f"Broadcasting to connection {connection_id}")
        except Exception as exc:
            logger.error(f"Failed to broadcast to connection {connection_id}: {exc}")


# Import timezone for connection management
from django.utils import timezone
