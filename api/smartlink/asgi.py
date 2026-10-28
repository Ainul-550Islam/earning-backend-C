"""
SmartLink ASGI Configuration
Supports both HTTP (Django) and WebSocket (Django Channels) protocols.

WebSocket endpoints:
  ws://domain/ws/smartlink/<slug>/live/    → SmartLinkLiveConsumer
  ws://domain/ws/publisher/dashboard/     → PublisherDashboardConsumer

Install requirements:
  pip install channels channels-redis daphne

Add to settings.py:
  INSTALLED_APPS += ['channels']
  CHANNEL_LAYERS = {
      'default': {
          'BACKEND': 'channels_redis.core.RedisChannelLayer',
          'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
      }
  }
  ASGI_APPLICATION = 'smartlink.asgi.application'
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Load Django before importing channels consumers
django_asgi_app = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from channels.security.websocket import AllowedHostsOriginValidator
    from smartlink.websocket.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        # HTTP → standard Django
        'http': django_asgi_app,

        # WebSocket → channels consumers
        # AllowedHostsOriginValidator enforces ALLOWED_HOSTS for WS connections
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    })

except ImportError:
    # Channels not installed → fall back to plain ASGI (HTTP only)
    application = django_asgi_app
