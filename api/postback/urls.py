"""urls.py – URL routing for the postback module."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    DuplicateLeadCheckViewSet,
    NetworkPostbackConfigViewSet,
    PostbackLogViewSet,
)
from .views import PostbackDashboardView, PostbackRetryView
from .webhooks import PostbackWebhookView

app_name = "postback"

router = DefaultRouter()
router.register(r"networks", NetworkPostbackConfigViewSet, basename="network")
router.register(r"logs", PostbackLogViewSet, basename="log")
router.register(r"duplicates", DuplicateLeadCheckViewSet, basename="duplicate")

urlpatterns = [
    # ── Router ────────────────────────────────────────────────────────────────
    path("", include(router.urls)),

    # ── Webhook Ingestion (public – security handled inside the view) ─────────
    path("receive/<str:network_key>/", PostbackWebhookView.as_view(), name="webhook"),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("admin/dashboard/", PostbackDashboardView.as_view(), name="dashboard"),
    path("admin/logs/<uuid:pk>/retry/", PostbackRetryView.as_view(), name="retry-log"),
]

# ── URL Summary ───────────────────────────────────────────────────────────────
# GET/POST  /api/postback/receive/{network_key}/          → webhook ingestion
#
# GET       /api/postback/networks/                       → list networks
# POST      /api/postback/networks/                       → create network
# GET       /api/postback/networks/{id}/                  → network detail
# PUT/PATCH /api/postback/networks/{id}/                  → update network
# DELETE    /api/postback/networks/{id}/                  → delete network
# POST      /api/postback/networks/{id}/activate/         → activate
# POST      /api/postback/networks/{id}/deactivate/       → deactivate
# GET/POST  /api/postback/networks/{id}/validators/       → list/create validators
# GET       /api/postback/networks/{id}/stats/            → per-network stats
#
# GET       /api/postback/logs/                           → list logs (filterable)
# GET       /api/postback/logs/{id}/                      → log detail (with raw_payload)
# POST      /api/postback/logs/{id}/retry/                → re-queue failed log
#
# GET       /api/postback/duplicates/                     → dedup table
# DELETE    /api/postback/duplicates/{id}/                → clear a dedup entry
#
# GET       /api/postback/admin/dashboard/                → 24h stats summary
# POST      /api/postback/admin/logs/{id}/retry/          → admin retry
