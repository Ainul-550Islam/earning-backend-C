"""
WebSocket routing for Real-time Dashboard Backend.

NEW FILE: this app defines three Django Channels consumers
(DashboardConsumer, MetricConsumer, EventConsumer) in `consumers/`, but no
routing module existed anywhere in the codebase to map WebSocket URL paths
to them - they were completely unreachable from the network.

This module is the equivalent of `urls.py` for the WebSocket protocol. It
must be included in the project-level ASGI application, e.g. in `asgi.py`:

    import os
    from django.core.asgi import get_asgi_application

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django_asgi_app = get_asgi_application()

    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from api.realtime_dashboard.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })

URL <-> consumer <-> group name mapping (must stay in sync with
consumers/*.py and websocket_manager.py, which publishes to these same
group names):

    ws/dashboard/<dashboard_id>/   -> DashboardConsumer -> group 'dashboard_<id>'
    ws/metric/<metric_id>/         -> MetricConsumer     -> group 'metric_<id>'
    ws/events/                     -> EventConsumer      -> group 'events'
"""
from django.urls import re_path

from .consumers.dashboard_consumer import DashboardConsumer
from .consumers.metric_consumer import MetricConsumer
from .consumers.event_consumer import EventConsumer


websocket_urlpatterns = [
    re_path(r'^ws/dashboard/(?P<dashboard_id>\d+)/$', DashboardConsumer.as_asgi()),
    re_path(r'^ws/metric/(?P<metric_id>\d+)/$', MetricConsumer.as_asgi()),
    re_path(r'^ws/events/$', EventConsumer.as_asgi()),
]
