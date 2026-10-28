# api/referral/routing.py
# Django Channels WebSocket URL routing
# Include in config/routing.py:
#   from api.referral.routing import websocket_urlpatterns
# ============================================================

try:
    from django.urls import re_path
    from api.referral.consumers import (
        ReferralLeaderboardConsumer,
        ReferralStatsConsumer,
        WEBSOCKET_AVAILABLE,
    )

    if WEBSOCKET_AVAILABLE:
        websocket_urlpatterns = [
            re_path(
                r'^ws/referral/leaderboard/$',
                ReferralLeaderboardConsumer.as_asgi(),
                name='ws-referral-leaderboard',
            ),
            re_path(
                r'^ws/referral/stats/$',
                ReferralStatsConsumer.as_asgi(),
                name='ws-referral-stats',
            ),
        ]
    else:
        websocket_urlpatterns = []

except ImportError:
    websocket_urlpatterns = []