# engagement/routing.py
"""
WebSocket routing configuration for engagement system.
Defines URL patterns for WebSocket consumers.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Main engagement WebSocket
    re_path(r'ws/engagement/$', consumers.EngagementConsumer.as_asgi()),
    
    # Leaderboard WebSocket
    re_path(r'ws/engagement/leaderboard/$', consumers.LeaderboardConsumer.as_asgi()),
    
    # Notifications WebSocket
    re_path(r'ws/engagement/notifications/$', consumers.NotificationConsumer.as_asgi()),
    
    # Social feed WebSocket
    re_path(r'ws/engagement/social/$', consumers.SocialFeedConsumer.as_asgi()),
    
    # Real-time analytics WebSocket
    re_path(r'ws/engagement/analytics/$', consumers.AnalyticsConsumer.as_asgi()),
]
