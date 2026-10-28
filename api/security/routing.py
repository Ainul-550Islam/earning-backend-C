"""
Security WebSocket Routing Configuration
Django Channels routing for real-time security monitoring
"""

from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from .consumers import (
    SecurityMonitorConsumer,
    ThreatDetectionConsumer,
    AuditLogConsumer,
    IncidentAlertConsumer,
    UserSessionConsumer
)

# WebSocket URL patterns
websocket_urlpatterns = [
    # Real-time security monitoring
    re_path(r'^ws/security/monitor/$', SecurityMonitorConsumer.as_asgi()),
    
    # Threat detection alerts
    re_path(r'^ws/security/threats/$', ThreatDetectionConsumer.as_asgi()),
    
    # Audit log streaming
    re_path(r'^ws/security/audit/$', AuditLogConsumer.as_asgi()),
    
    # Security incident alerts
    re_path(r'^ws/security/incidents/$', IncidentAlertConsumer.as_asgi()),
    
    # User session monitoring
    re_path(r'^ws/security/sessions/$', UserSessionConsumer.as_asgi()),
]

# Application protocol routing
application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})

# Export routing configuration
__all__ = [
    'websocket_urlpatterns',
    'application'
]