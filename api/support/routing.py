# api/support/routing.py
from django.urls import re_path
try:
    from . import contumers
    support_websocket_patterns = [
        re_path(r'^ws/support/chat/(?P<session_id>[^/]+)/$', contumers.TicketChatConsumer.as_asgi()),
        re_path(r'^ws/support/agent/$', contumers.AgentDashboardConsumer.as_asgi()),
        re_path(r'^ws/support/notifications/$', contumers.SupportNotificationConsumer.as_asgi()),
    ]
except Exception:
    support_websocket_patterns = []