# api/rate_limit/routing.py
"""WebSocket URL routing for rate_limit module."""
try:
    from channels.routing import URLRouter
    from django.urls import re_path
    from api.rate_limit.consumers import (
        RateLimitConsumer, RateLimitMonitorConsumer, RateLimitAnalyticsConsumer
    )

    websocket_urlpatterns = [
        re_path(r'^ws/rate-limit/$', RateLimitConsumer.as_asgi()),
        re_path(r'^ws/rate-limit/events/$', RateLimitConsumer.as_asgi()),
        re_path(r'^ws/rate-limit/monitor/$', RateLimitMonitorConsumer.as_asgi()),
        re_path(r'^ws/rate-limit/analytics/$', RateLimitAnalyticsConsumer.as_asgi()),
        re_path(r'^ws/rate_limit/$', RateLimitConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
