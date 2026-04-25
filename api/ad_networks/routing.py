"""
api/ad_networks/routing.py
URL routing configuration for Django Channels
SaaS-ready with tenant support
"""

from django.urls import re_path
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from . import consumers

# WebSocket URL patterns
websocket_urlpatterns = [
    # Offer updates WebSocket
    re_path(
        r'ws/ad_networks/offers/(?P<tenant_id>\w+)/$',
        consumers.OfferUpdatesConsumer.as_asgi(),
        name='offer_updates_ws'
    ),
    
    # Network health WebSocket
    re_path(
        r'ws/ad_networks/health/(?P<tenant_id>\w+)/$',
        consumers.NetworkHealthConsumer.as_asgi(),
        name='network_health_ws'
    ),
    
    # Conversion updates WebSocket
    re_path(
        r'ws/ad_networks/conversions/(?P<tenant_id>\w+)/$',
        consumers.ConversionUpdatesConsumer.as_asgi(),
        name='conversion_updates_ws'
    ),
]

# HTTP URL patterns for API endpoints
urlpatterns = [
    # Include the main URLs
    path('api/', include('api.ad_networks.urls')),
]

# Static files
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ASGI application configuration
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})

# Channel layer configuration
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security import AllowedHostsOriginValidator

# Middleware stack
middleware_stack = [
    AllowedHostsOriginValidator(
        # Add your allowed hosts here
        allowed_hosts=settings.ALLOWED_HOSTS,
    ),
    AuthMiddlewareStack,
]

# Apply middleware to WebSocket routes
websocket_urlpatterns = [
    URLRouter(
        [
            re_path(
                r'ws/ad_networks/offers/(?P<tenant_id>\w+)/$',
                consumers.OfferUpdatesConsumer.as_asgi(),
                name='offer_updates_ws'
            ),
            re_path(
                r'ws/ad_networks/health/(?P<tenant_id>\w+)/$',
                consumers.NetworkHealthConsumer.as_asgi(),
                name='network_health_ws'
            ),
            re_path(
                r'ws/ad_networks/conversions/(?P<tenant_id>\w+)/$',
                consumers.ConversionUpdatesConsumer.as_asgi(),
                name='conversion_updates_ws'
            ),
        ]
    )
]

# Final ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

# Channel layer configuration
from channels.layers import get_channel_layer

# Get default channel layer
channel_layer = get_channel_layer()

# Custom routing for tenant isolation
class TenantRouter:
    """
    Router for tenant-based WebSocket routing
    """
    
    def __init__(self):
        self.tenant_routes = {}
    
    def add_tenant_route(self, tenant_id, pattern, consumer):
        """Add route for specific tenant"""
        if tenant_id not in self.tenant_routes:
            self.tenant_routes[tenant_id] = []
        
        self.tenant_routes[tenant_id].append((pattern, consumer))
    
    def get_routes_for_tenant(self, tenant_id):
        """Get all routes for specific tenant"""
        return self.tenant_routes.get(tenant_id, [])
    
    def route_message(self, message):
        """Route message to appropriate consumer"""
        # Extract tenant from message
        tenant_id = message.get('tenant_id')
        
        if tenant_id and tenant_id in self.tenant_routes:
            routes = self.tenant_routes[tenant_id]
            
            for pattern, consumer in routes:
                if pattern.matches(message):
                    return consumer(message)
        
        return None


# Create tenant router instance
tenant_router = TenantRouter()

# Add tenant-specific routes
tenant_router.add_tenant_route(
    'default',
    re_path(r'offers/(?P<offer_id>\d+)/$', consumers.OfferUpdatesConsumer.as_asgi()),
    consumers.OfferUpdatesConsumer
)

tenant_router.add_tenant_route(
    'default',
    re_path(r'health/(?P<network_id>\d+)/$', consumers.NetworkHealthConsumer.as_asgi()),
    consumers.NetworkHealthConsumer
)

# Channel routing with tenant isolation
class TenantChannelRouter:
    """
    Channel router with tenant isolation
    """
    
    def __init__(self):
        self.routes = {
            'offer_updates': {
                'pattern': re_path(r'offers/(?P<tenant_id>\w+)/$', consumers.OfferUpdatesConsumer.as_asgi()),
                'consumer': consumers.OfferUpdatesConsumer
            },
            'network_health': {
                'pattern': re_path(r'health/(?P<tenant_id>\w+)/$', consumers.NetworkHealthConsumer.as_asgi()),
                'consumer': consumers.NetworkHealthConsumer
            },
            'conversion_updates': {
                'pattern': re_path(r'conversions/(?P<tenant_id>\w+)/$', consumers.ConversionUpdatesConsumer.as_asgi()),
                'consumer': consumers.ConversionUpdatesConsumer
            }
        }
    
    def route(self, scope):
        """Route WebSocket connection to appropriate consumer"""
        path = scope['path']
        
        # Extract tenant ID from path
        import re
        match = re.match(r'/ws/ad_networks/(\w+)/(?:\w+)/(?P<tenant_id>\w+)/', path)
        
        if match:
            route_type = match.group(1)
            tenant_id = match.group('tenant_id')
            
            if route_type in self.routes:
                # Add tenant to scope
                scope['tenant_id'] = tenant_id
                
                # Return consumer with tenant context
                return self.routes[route_type]['consumer']
        
        return None


# Create tenant channel router
tenant_channel_router = TenantChannelRouter()

# WebSocket URL patterns with tenant routing
websocket_urlpatterns = [
    URLRouter([
        # Offer updates with tenant
        re_path(
            r'ws/ad_networks/offers/(?P<tenant_id>\w+)/$',
            consumers.OfferUpdatesConsumer.as_asgi(),
            name='offer_updates_ws'
        ),
        
        # Network health with tenant
        re_path(
            r'ws/ad_networks/health/(?P<tenant_id>\w+)/$',
            consumers.NetworkHealthConsumer.as_asgi(),
            name='network_health_ws'
        ),
        
        # Conversion updates with tenant
        re_path(
            r'ws/ad_networks/conversions/(?P<tenant_id>\w+)/$',
            consumers.ConversionUpdatesConsumer.as_asgi(),
            name='conversion_updates_ws'
        ),
    ])
]

# ASGI application with tenant routing
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

# Channel layer configuration for Redis
if settings.CHANNEL_LAYERS:
    from channels_redis.core import RedisChannelLayer
    
    channel_layer = RedisChannelLayer(
        hosts=settings.CHANNEL_LAYERS['default']['CONFIG']['hosts']
    )

# Consumer groups for real-time updates
class ConsumerGroups:
    """
    Consumer groups for different types of updates
    """
    
    # Offer-related groups
    OFFER_UPDATES = "offer_updates_{tenant_id}"
    OFFER_CLICKS = "offer_clicks_{tenant_id}"
    OFFER_CONVERSIONS = "offer_conversions_{tenant_id}"
    
    # User-related groups
    USER_UPDATES = "user_updates_{user_id}_{tenant_id}"
    USER_NOTIFICATIONS = "user_notifications_{user_id}_{tenant_id}"
    
    # Network-related groups
    NETWORK_HEALTH = "network_health_{tenant_id}"
    NETWORK_STATS = "network_stats_{tenant_id}"
    
    # Admin-related groups
    ADMIN_DASHBOARD = "admin_dashboard_{tenant_id}"
    ADMIN_ALERTS = "admin_alerts_{tenant_id}"
    
    @staticmethod
    def get_group_name(group_type: str, **kwargs) -> str:
        """Get formatted group name"""
        return group_type.format(**kwargs)
    
    @staticmethod
    def join_user_groups(user_id: int, tenant_id: str):
        """Join user-specific groups"""
        return [
            ConsumerGroups.get_group_name(ConsumerGroups.USER_UPDATES, user_id=user_id, tenant_id=tenant_id),
            ConsumerGroups.get_group_name(ConsumerGroups.USER_NOTIFICATIONS, user_id=user_id, tenant_id=tenant_id)
        ]
    
    @staticmethod
    def join_offer_groups(offer_id: int, tenant_id: str):
        """Join offer-specific groups"""
        return [
            ConsumerGroups.get_group_name(ConsumerGroups.OFFER_UPDATES, tenant_id=tenant_id),
            ConsumerGroups.get_group_name(ConsumerGroups.OFFER_CLICKS, tenant_id=tenant_id),
            ConsumerGroups.get_group_name(ConsumerGroups.OFFER_CONVERSIONS, tenant_id=tenant_id)
        ]
    
    @staticmethod
    def join_network_groups(tenant_id: str):
        """Join network-specific groups"""
        return [
            ConsumerGroups.get_group_name(ConsumerGroups.NETWORK_HEALTH, tenant_id=tenant_id),
            ConsumerGroups.get_group_name(ConsumerGroups.NETWORK_STATS, tenant_id=tenant_id)
        ]
    
    @staticmethod
    def join_admin_groups(tenant_id: str):
        """Join admin-specific groups"""
        return [
            ConsumerGroups.get_group_name(ConsumerGroups.ADMIN_DASHBOARD, tenant_id=tenant_id),
            ConsumerGroups.get_group_name(ConsumerGroups.ADMIN_ALERTS, tenant_id=tenant_id)
        ]


# Message routing for different message types
class MessageRouter:
    """
    Router for different message types
    """
    
    def __init__(self):
        self.routes = {
            'offer_update': self._handle_offer_update,
            'conversion_update': self._handle_conversion_update,
            'network_health_update': self._handle_network_health_update,
            'user_notification': self._handle_user_notification,
            'admin_alert': self._handle_admin_alert
        }
    
    def route_message(self, message):
        """Route message to appropriate handler"""
        message_type = message.get('type')
        
        if message_type in self.routes:
            return self.routes[message_type](message)
        
        return None
    
    def _handle_offer_update(self, message):
        """Handle offer update message"""
        # Route to offer update handler
        pass
    
    def _handle_conversion_update(self, message):
        """Handle conversion update message"""
        # Route to conversion update handler
        pass
    
    def _handle_network_health_update(self, message):
        """Handle network health update message"""
        # Route to network health update handler
        pass
    
    def _handle_user_notification(self, message):
        """Handle user notification message"""
        # Route to user notification handler
        pass
    
    def _handle_admin_alert(self, message):
        """Handle admin alert message"""
        # Route to admin alert handler
        pass


# Create message router
message_router = MessageRouter()

# WebSocket authentication
class WebSocketAuthMiddleware:
    """
    Middleware for WebSocket authentication
    """
    
    def __init__(self, inner):
        self.inner = inner
    
    async def __call__(self, scope, receive, send):
        # Extract token from query parameters or headers
        token = None
        
        # Try query parameter
        if 'query_string' in scope:
            from urllib.parse import parse_qs
            query_params = parse_qs(scope['query_string'].decode())
            if 'token' in query_params:
                token = query_params['token'][0]
        
        # Try headers
        if not token and 'headers' in scope:
            for header, value in scope['headers']:
                if header.decode() == b'authorization':
                    auth_header = value.decode()
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]
        
        # Authenticate user
        if token:
            from channels.auth import AuthMiddlewareStack
            from channels.db import database_sync_to_async
            from django.contrib.auth import get_user_model
            from django.contrib.auth.models import AnonymousUser
            
            User = get_user_model()
            
            @database_sync_to_async
            def get_user(token):
                try:
                    # This would validate the token and return user
                    # For now, return None
                    return None
                except:
                    return AnonymousUser()
            
            user = await get_user(token)
            scope['user'] = user
        
        # Continue with inner application
        return await self.inner(scope, receive, send)


# Rate limiting for WebSocket connections
class WebSocketRateLimitMiddleware:
    """
    Middleware for WebSocket rate limiting
    """
    
    def __init__(self, inner):
        self.inner = inner
        self.connection_counts = {}
    
    async def __call__(self, scope, receive, send):
        # Get client identifier
        client_id = self._get_client_id(scope)
        
        # Check rate limit
        if self._is_rate_limited(client_id):
            await send({
                'type': 'error',
                'message': 'Rate limit exceeded'
            })
            return
        
        # Increment connection count
        self._increment_connection_count(client_id)
        
        try:
            return await self.inner(scope, receive, send)
        finally:
            self._decrement_connection_count(client_id)
    
    def _get_client_id(self, scope):
        """Get client identifier"""
        # Try user ID
        if 'user' in scope and scope['user'].is_authenticated:
            return f"user_{scope['user'].id}"
        
        # Try IP address
        if 'client' in scope and 'ip' in scope['client']:
            return f"ip_{scope['client']['ip']}"
        
        return "unknown"
    
    def _is_rate_limited(self, client_id):
        """Check if client is rate limited"""
        import time
        
        current_time = time.time()
        max_connections = 10  # Max 10 connections per client
        window = 60  # 1 minute window
        
        if client_id not in self.connection_counts:
            return False
        
        connections = self.connection_counts[client_id]
        recent_connections = [
            conn_time for conn_time in connections
            if current_time - conn_time < window
        ]
        
        return len(recent_connections) >= max_connections
    
    def _increment_connection_count(self, client_id):
        """Increment connection count"""
        import time
        
        if client_id not in self.connection_counts:
            self.connection_counts[client_id] = []
        
        self.connection_counts[client_id].append(time.time())
    
    def _decrement_connection_count(self, client_id):
        """Decrement connection count"""
        if client_id in self.connection_counts:
            self.connection_counts[client_id].pop()


# Middleware stack for WebSocket
websocket_middleware_stack = [
    WebSocketAuthMiddleware,
    WebSocketRateLimitMiddleware,
]

# Apply middleware to WebSocket routes
websocket_urlpatterns = [
    URLRouter([
        re_path(
            r'ws/ad_networks/offers/(?P<tenant_id>\w+)/$',
            consumers.OfferUpdatesConsumer.as_asgi(),
            name='offer_updates_ws'
        ),
        re_path(
            r'ws/ad_networks/health/(?P<tenant_id>\w+)/$',
            consumers.NetworkHealthConsumer.as_asgi(),
            name='network_health_ws'
        ),
        re_path(
            r'ws/ad_networks/conversions/(?P<tenant_id>\w+)/$',
            consumers.ConversionUpdatesConsumer.as_asgi(),
            name='conversion_updates_ws'
        ),
    ])
]

# Final ASGI application with all middleware
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

# Channel layer configuration
if settings.CHANNEL_LAYERS:
    from channels_redis.core import RedisChannelLayer
    
    channel_layer = RedisChannelLayer(
        hosts=settings.CHANNEL_LAYERS['default']['CONFIG']['hosts']
    )

# Export routing configuration
__all__ = [
    'application',
    'websocket_urlpatterns',
    'ConsumerGroups',
    'MessageRouter',
    'tenant_router',
    'tenant_channel_router'
]
