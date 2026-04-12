"""
Messaging WebSocket URL Routing — All 4 consumer routes.
Include in your project's asgi.py:

    from messaging.routing import websocket_urlpatterns
    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""
from django.urls import re_path
from .consumers import ChatConsumer, SupportConsumer, PresenceConsumer, CallConsumer

websocket_urlpatterns = [
    # Chat room — peer-to-peer and group chats
    re_path(r"^ws/messaging/chat/(?P<chat_id>[0-9a-f\-]+)/$",
            ChatConsumer.as_asgi(), name="ws-chat"),

    # Support thread — affiliate ↔ agent
    re_path(r"^ws/messaging/support/(?P<thread_id>[0-9a-f\-]+)/$",
            SupportConsumer.as_asgi(), name="ws-support"),

    # Presence — online/away/offline tracking (one per user)
    re_path(r"^ws/messaging/presence/$",
            PresenceConsumer.as_asgi(), name="ws-presence"),

    # WebRTC call room — signaling only (offer/answer/ICE)
    re_path(r"^ws/messaging/call/(?P<room_id>[a-f0-9]+)/$",
            CallConsumer.as_asgi(), name="ws-call"),
]
