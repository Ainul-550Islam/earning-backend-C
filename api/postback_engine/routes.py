"""
routes.py – URL routing for Postback Engine.
"""
from django.urls import path, include

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
from rest_framework.routers import DefaultRouter

# Router for ViewSet-based views
router = DefaultRouter()
router.register(r"networks", AdNetworkConfigViewSet, basename="network-config")

app_name = "postback_engine"

urlpatterns = [
    # ── Public Postback Endpoints (called by CPA networks) ──────────────────
    path(
        "postback/<str:network_key>/",
        PostbackReceiveView.as_view(),
        name="postback-receive",
    ),
    path(
        "postback/<str:network_key>/pixel/",
        ImpressionTrackView.as_view(),
        name="impression-track",
    ),

    # ── Click Tracking ───────────────────────────────────────────────────────
    path(
        "click/track/",
        ClickTrackView.as_view(),
        name="click-track",
    ),

    # ── Admin / Management Endpoints ─────────────────────────────────────────
    path("logs/", PostbackLogListView.as_view(), name="postback-log-list"),
    path("logs/<uuid:pk>/", PostbackLogDetailView.as_view(), name="postback-log-detail"),
    path("logs/<uuid:pk>/replay/", ReplayPostbackView.as_view(), name="postback-replay"),

    path("conversions/", ConversionListView.as_view(), name="conversion-list"),
    path("conversions/<uuid:pk>/", ConversionDetailView.as_view(), name="conversion-detail"),

    path("clicks/", ClickLogListView.as_view(), name="click-log-list"),

    # ── Analytics ─────────────────────────────────────────────────────────────
    path("stats/network/<uuid:network_id>/", NetworkStatsView.as_view(), name="network-stats"),
    path("stats/hourly/", HourlyStatsView.as_view(), name="hourly-stats"),

    # ── Testing ───────────────────────────────────────────────────────────────
    path("test/postback/<str:network_key>/", TestPostbackView.as_view(), name="test-postback"),

    # ── Health ────────────────────────────────────────────────────────────────
    path("health/", HealthCheckView.as_view(), name="health-check"),

    # ── ViewSet Routes ────────────────────────────────────────────────────────
    path("", include(router.urls)),
]
