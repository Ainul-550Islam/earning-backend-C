"""
WebSocket URL routing for Telemetry Observability.

WIRING — paste into your project's asgi.py:

    # asgi.py
    import os
    from django.core.asgi import get_asgi_application
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

    from .routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })

Also add to INSTALLED_APPS:
    'channels',
    'telemetry_observability',

And set the channel layer in settings.py:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
"""
from django.urls import re_path

from .consumers import (
    MetricStreamConsumer,
    LogStreamConsumer,
    AlertStreamConsumer,
    HealthStreamConsumer,
    TraceStreamConsumer,
)

websocket_urlpatterns = [
    re_path(r'^ws/telemetry/metrics/$',  MetricStreamConsumer.as_asgi()),
    re_path(r'^ws/telemetry/logs/$',     LogStreamConsumer.as_asgi()),
    re_path(r'^ws/telemetry/alerts/$',   AlertStreamConsumer.as_asgi()),
    re_path(r'^ws/telemetry/health/$',   HealthStreamConsumer.as_asgi()),
    re_path(r'^ws/telemetry/traces/$',   TraceStreamConsumer.as_asgi()),
]
