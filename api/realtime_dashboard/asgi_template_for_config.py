"""
ASGI entry point for Real-time Dashboard Backend.

This file belongs at the PROJECT root (alongside settings.py / manage.py),
not inside the app package. It is included here as a ready-to-use template.

Copy it to your project root, adjust the DJANGO_SETTINGS_MODULE path, and
point your ASGI server (Daphne, Uvicorn, Hypercorn) at it:

    daphne -b 0.0.0.0 -p 8000 asgi:application
    uvicorn asgi:application --host 0.0.0.0 --port 8000

For Kubernetes / Docker, set the environment variable:
    DJANGO_SETTINGS_MODULE=config.settings

Production channel layer (Redis) - add to settings.py:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [('redis', 6379)],
                'capacity': 1500,
                'expiry': 10,
            },
        }
    }
"""
import os

from django.core.asgi import get_asgi_application

# Must be set before importing channels or the app.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Load Django app registry first (required by channels AuthMiddlewareStack).
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from api.realtime_dashboard.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    # Standard HTTP requests - handled by Django
    'http': django_asgi_app,

    # WebSocket connections - routed through realtime_dashboard.routing
    # AllowedHostsOriginValidator rejects WS connections from Origins not
    # in settings.ALLOWED_HOSTS (CSRF equivalent for WebSocket).
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
