# api/cms/routing.py
"""
Django Channels WebSocket URL routing for CMS.

FIX (audit): consumers_new/RealTimeOfferConsumer.py was fully implemented but
never registered here, meaning all WebSocket real-time offer connections silently
failed with a 404.  Both RealTimeOfferConsumer (user-facing) and
AdminRealTimeOfferConsumer (staff dashboard) are now wired up.
"""
from django.urls import re_path
from . import consumers

# ── consumers_new — RealTimeOffer WebSocket consumers ────────────────────────
try:
    from .consumers_new.RealTimeOfferConsumer import (
        RealTimeOfferConsumer,
        AdminRealTimeOfferConsumer,
    )
    _realtime_consumers_available = True
except ImportError:
    _realtime_consumers_available = False
    import logging
    logging.getLogger(__name__).warning(
        "[CMS routing] RealTimeOfferConsumer not available — "
        "check consumers_new/RealTimeOfferConsumer.py"
    )

# ── Base WebSocket URL patterns ───────────────────────────────────────────────
websocket_urlpatterns = [
    # ── Original consumers (all preserved) ───────────────────────────────────
    re_path(r'^ws/cms/notifications/$',  consumers.CMSNotificationConsumer.as_asgi()),
    re_path(r'^ws/cms/offers/$',         consumers.CMSOfferFeedConsumer.as_asgi()),
    re_path(r'^ws/cms/leaderboard/$',    consumers.CMSLeaderboardConsumer.as_asgi()),
    re_path(r'^ws/cms/surveys/$',        consumers.SurveyConsumer.as_asgi()),
    re_path(r'^ws/cms/rewards/$',        consumers.RewardConsumer.as_asgi()),
    re_path(r'^ws/cms/tasks/$',          consumers.TaskConsumer.as_asgi()),
]

# ── NEW: RealTimeOffer consumers — only added when module is available ─────────
if _realtime_consumers_available:
    websocket_urlpatterns += [
        # User-facing real-time offer feed
        # Auth: only authenticated users; closed immediately on connect if anonymous
        re_path(r'^ws/cms/realtime-offers/$',        RealTimeOfferConsumer.as_asgi()),
        # Admin/staff real-time offer management dashboard
        # Auth: requires request.user.is_staff — consumer enforces this on connect
        re_path(r'^ws/cms/admin/realtime-offers/$',  AdminRealTimeOfferConsumer.as_asgi()),
    ]
