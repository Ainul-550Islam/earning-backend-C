# api/support/consumers/routing.py  — WORLD #1 COMPLETE
"""
WebSocket URL routing for support consumers.

Add to your main routing.py:
    from api.support.consumers.routing import support_websocket_patterns
    application = ProtocolTypeRouter({
        "websocket": AuthMiddlewareStack(URLRouter(support_websocket_patterns)),
    })

Or include in asgi.py:
    from api.support.consumers.routing import support_websocket_patterns
"""
try:
    from django.urls import re_path
    from api.support.consumers.ChatConsumer         import ChatConsumer
    from api.support.consumers.AgentConsumer        import AgentConsumer
    from api.support.consumers.NotificationConsumer import NotificationConsumer
    from api.support.consumers.TypingConsumer       import TypingConsumer

    support_websocket_patterns = [
        re_path(r"^ws/support/chat/(?P<session_id>[\w-]+)/$",  ChatConsumer.as_asgi()),
        re_path(r"^ws/support/agent/$",                          AgentConsumer.as_asgi()),
        re_path(r"^ws/support/notifications/$",                  NotificationConsumer.as_asgi()),
        re_path(r"^ws/support/typing/(?P<session_id>[\w-]+)/$", TypingConsumer.as_asgi()),
    ]
except Exception:
    support_websocket_patterns = []