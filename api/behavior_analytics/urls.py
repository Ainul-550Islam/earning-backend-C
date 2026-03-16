# =============================================================================
# behavior_analytics/urls.py
# =============================================================================
"""
URL configuration for the behavior_analytics application.

Mount under project urls.py:
    path("api/analytics/", include("api.behavior_analytics.urls")),

All endpoints:
    GET  /api/analytics/paths/                         → UserPath list
    POST /api/analytics/paths/                         → create path
    GET  /api/analytics/paths/<id>/                    → retrieve path
    POST /api/analytics/paths/<id>/close/              → close session
    POST /api/analytics/paths/<id>/add_nodes/          → append nodes
    GET  /api/analytics/clicks/                        → list clicks
    POST /api/analytics/clicks/                        → record click
    POST /api/analytics/clicks/bulk/                   → bulk insert
    GET  /api/analytics/clicks/top_elements/           → top elements
    GET  /api/analytics/stay-times/                    → list
    POST /api/analytics/stay-times/                    → record
    GET  /api/analytics/stay-times/stats/              → aggregate stats
    GET  /api/analytics/engagement-scores/             → list
    POST /api/analytics/engagement-scores/recalculate/ → recalculate
    GET  /api/analytics/engagement-scores/summary/     → summary
    GET  /api/analytics/dashboard/                     → behaviour dashboard
    POST /api/analytics/engagement/recalculate/        → my score
    GET  /api/analytics/sessions/<session_id>/         → session lookup
    GET  /api/analytics/admin/stats/                   → global stats (staff)
    POST /api/analytics/events/                        → SDK event webhook
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalyticsEventWebhookView,
    GlobalAnalyticsStatsView,
    RecalculateMyEngagementView,
    SessionPathDetailView,
    UserBehaviourDashboardView,
)
from .viewsets import (
    ClickMetricViewSet,
    EngagementScoreViewSet,
    StayTimeViewSet,
    UserPathViewSet,
)

app_name = "behavior_analytics"

router = DefaultRouter(trailing_slash=True)
router.register(r"paths",             UserPathViewSet,        basename="userpath")
router.register(r"clicks",            ClickMetricViewSet,     basename="clickmetric")
router.register(r"stay-times",        StayTimeViewSet,        basename="staytime")
router.register(r"engagement-scores", EngagementScoreViewSet, basename="engagementscore")

urlpatterns = [
    path("", include(router.urls)),

    path("dashboard/",
         UserBehaviourDashboardView.as_view(),
         name="user-dashboard"),

    path("engagement/recalculate/",
         RecalculateMyEngagementView.as_view(),
         name="recalculate-engagement"),

    path("sessions/<str:session_id>/",
         SessionPathDetailView.as_view(),
         name="session-detail"),

    path("admin/stats/",
         GlobalAnalyticsStatsView.as_view(),
         name="admin-stats"),

    path("events/",
         AnalyticsEventWebhookView.as_view(),
         name="events-webhook"),
]
