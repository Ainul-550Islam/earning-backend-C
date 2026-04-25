# earning_backend/api/notifications/routing.py
"""
Django Channels WebSocket URL routing for the notification system.

Add to your asgi.py:
    from api.notifications.routing import websocket_urlpatterns
"""

try:
    from django.urls import re_path
    from .consumers import NotificationConsumer

    websocket_urlpatterns = [
        re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
        re_path(r'^ws/notifications/(?P<user_id>\d+)/$', NotificationConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
