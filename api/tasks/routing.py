"""
api/tasks/routing.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django Channels WebSocket URL routing for the task system.

Add to asgi.py:
    from api.tasks.routing import websocket_urlpatterns
    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""

from django.urls import re_path
from api.tasks.consumers import (
    TaskLiveConsumer,
    LeaderboardConsumer,
    TaskMonitorConsumer,
    NotificationConsumer,
)

websocket_urlpatterns = [
    # Live task events for authenticated user
    re_path(r'ws/tasks/live/$',            TaskLiveConsumer.as_asgi()),
    # Real-time leaderboard (public)
    re_path(r'ws/tasks/leaderboard/$',     LeaderboardConsumer.as_asgi()),
    # Admin: Celery task monitor (staff only)
    re_path(r'ws/tasks/monitor/$',         TaskMonitorConsumer.as_asgi()),
    # Real-time in-app notifications
    re_path(r'ws/tasks/notifications/$',   NotificationConsumer.as_asgi()),
]
