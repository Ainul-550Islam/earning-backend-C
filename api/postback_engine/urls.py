"""
urls.py – URL routing for Postback Engine.

Include this in your project's main urls.py:

    from django.urls import path, include

    urlpatterns = [
        path("api/postback_engine/", include("api.postback_engine.urls")),
    ]

All postback endpoints live under:
    /api/postback_engine/postback/{network_key}/
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    PostbackReceiveView,
    ClickTrackView,
    ImpressionTrackView,
    PostbackLogListView,
    PostbackLogDetailView,
    ConversionListView,
    ConversionDetailView,
    ClickLogListView,
    AdNetworkConfigViewSet,
    NetworkStatsView,
    HourlyStatsView,
    ReplayPostbackView,
    TestPostbackView,
    HealthCheckView,
)

# ── DRF Router (ViewSet-based endpoints) ──────────────────────────────────────
router = DefaultRouter()
router.register(r"networks", AdNetworkConfigViewSet, basename="network-config")

app_name = "postback_engine"

urlpatterns = [

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC POSTBACK ENDPOINTS
    # Called directly by CPA networks (CPALead, AdGate, AppLovin, etc.)
    # No authentication required — secured by HMAC signature + IP whitelist
    # ══════════════════════════════════════════════════════════════════════════

    # Main postback receiver — GET & POST
    # CPALead  : /api/postback_engine/postback/cpalead/?sub1={sub1}&amount={amount}&oid={oid}&sid={sid}
    # AdGate   : /api/postback_engine/postback/adgate/?user_id={uid}&reward={reward}&offer_id={oid}
    # AppLovin : /api/postback_engine/postback/applovin/?idfa={idfa}&amount={amount}&event_id={eid}
    path(
        "postback/<str:network_key>/",
        PostbackReceiveView.as_view(),
        name="postback-receive",
    ),

    # 1×1 Impression tracking pixel
    # /api/postback_engine/postback/cpalead/pixel/?offer_id=123&placement=sidebar
    path(
        "postback/<str:network_key>/pixel/",
        ImpressionTrackView.as_view(),
        name="impression-track",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # CLICK TRACKING
    # Called by our frontend when user clicks an offer
    # ══════════════════════════════════════════════════════════════════════════

    # Generate click_id and redirect to offer URL
    # GET /api/postback_engine/click/track/?network=cpalead&offer_id=offer123
    path(
        "click/track/",
        ClickTrackView.as_view(),
        name="click-track",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN — POSTBACK LOGS
    # Requires IsAdminUser
    # ══════════════════════════════════════════════════════════════════════════

    # List all postback raw logs (filterable by network, status)
    path("logs/", PostbackLogListView.as_view(), name="postback-log-list"),

    # Detail of a single raw log
    path("logs/<uuid:pk>/", PostbackLogDetailView.as_view(), name="postback-log-detail"),

    # Replay (re-process) a failed/rejected postback
    path("logs/<uuid:pk>/replay/", ReplayPostbackView.as_view(), name="postback-replay"),

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN — CONVERSIONS
    # ══════════════════════════════════════════════════════════════════════════

    path("conversions/", ConversionListView.as_view(), name="conversion-list"),
    path("conversions/<uuid:pk>/", ConversionDetailView.as_view(), name="conversion-detail"),

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN — CLICKS
    # ══════════════════════════════════════════════════════════════════════════

    path("clicks/", ClickLogListView.as_view(), name="click-log-list"),

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN — ANALYTICS & STATS
    # ══════════════════════════════════════════════════════════════════════════

    # Per-network daily stats
    # GET /api/postback_engine/stats/network/{uuid}/?date=2024-01-15
    path(
        "stats/network/<uuid:network_id>/",
        NetworkStatsView.as_view(),
        name="network-stats",
    ),

    # Hourly stats series (last 7 days by default)
    path("stats/hourly/", HourlyStatsView.as_view(), name="hourly-stats"),

    # ══════════════════════════════════════════════════════════════════════════
    # TESTING
    # Requires is_test_mode=True on the network config
    # ══════════════════════════════════════════════════════════════════════════

    # Fire a synthetic test postback against a network in test mode
    # POST /api/postback_engine/test/postback/cpalead/
    path(
        "test/postback/<str:network_key>/",
        TestPostbackView.as_view(),
        name="test-postback",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # HEALTH CHECK
    # Public — used by load balancers and monitoring
    # ══════════════════════════════════════════════════════════════════════════

    # GET /api/postback_engine/health/
    path("health/", HealthCheckView.as_view(), name="health-check"),

    # ══════════════════════════════════════════════════════════════════════════
    # NETWORK CONFIG CRUD (DRF Router)
    # GET/POST  /api/postback_engine/networks/
    # GET/PUT/PATCH/DELETE /api/postback_engine/networks/{id}/
    # ══════════════════════════════════════════════════════════════════════════
    path("", include(router.urls)),
]