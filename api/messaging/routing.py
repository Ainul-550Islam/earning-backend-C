"""
Messaging WebSocket Routing — URL patterns for Channels consumers.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://host/ws/chat/<chat_id>/
    re_path(
        r"^ws/chat/(?P<chat_id>[0-9a-f-]{36})/$",
        consumers.ChatConsumer.as_asgi(),
        name="ws_chat",
    ),
    # ws://host/ws/support/<thread_id>/
    re_path(
        r"^ws/support/(?P<thread_id>[0-9a-f-]{36})/$",
        consumers.SupportConsumer.as_asgi(),
        name="ws_support",
    ),
]
