"""
WebSocket URL Routing for Offer Routing System

Registers all WebSocket consumers with Django Channels.
Include this in your project's asgi.py:

    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from api.offer_routing.websocket_routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""

from django.urls import re_path
from .consumers import (
    RoutingDashboardConsumer,
    CapMonitorConsumer,
    RoutingDecisionConsumer,
    PerformanceMetricsConsumer,
)

websocket_urlpatterns = [
    # Routing dashboard — real-time route stats per tenant
    re_path(
        r'ws/offer-routing/dashboard/$',
        RoutingDashboardConsumer.as_asgi(),
        name='ws-routing-dashboard',
    ),
    # Cap monitor — real-time cap usage alerts per tenant
    re_path(
        r'ws/offer-routing/caps/$',
        CapMonitorConsumer.as_asgi(),
        name='ws-cap-monitor',
    ),
    # Routing decision stream — live routing decisions as they happen
    re_path(
        r'ws/offer-routing/decisions/$',
        RoutingDecisionConsumer.as_asgi(),
        name='ws-routing-decisions',
    ),
    # Performance metrics — live performance KPIs
    re_path(
        r'ws/offer-routing/performance/$',
        PerformanceMetricsConsumer.as_asgi(),
        name='ws-performance-metrics',
    ),
]
