"""
routing.py – WebSocket routing configuration for postback module.

Defines WebSocket URL patterns and routing for Django Channels.
Handles real-time communication for postback monitoring and updates.
"""
from django.urls import re_path
from .consumers import PostbackLogConsumer, PostbackAnalyticsConsumer

websocket_urlpatterns = [
    # Postback log monitoring WebSocket
    re_path(r'ws/postback/logs/$', PostbackLogConsumer.as_asgi()),
    
    # Postback analytics WebSocket
    re_path(r'ws/postback/analytics/$', PostbackAnalyticsConsumer.as_asgi()),
]

# URL configuration for HTTP endpoints (to be included in main urls.py)
urlpatterns = [
    # These would be included in the main urls.py file
    # path('ws/postback/logs/', PostbackLogConsumer.as_asgi()),
    # path('ws/postback/analytics/', PostbackAnalyticsConsumer.as_asgi()),
]
