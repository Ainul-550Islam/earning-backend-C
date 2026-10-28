"""
payout_queue/urls.py  ← v8 PRODUCTION UPDATE

CHANGES v8:
  ① health_check endpoint now imported from views.py (was inline lambda in urls.py).
    The new views.py health_check is a full multi-component check
    (DB + Redis + Celery + queue stats + encryption key) instead of a simple DB ping.

All original URL patterns preserved unchanged.
"""
from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    PayoutBatchViewSet,
    PayoutItemViewSet,
    BulkProcessLogViewSet,
    WithdrawalPriorityViewSet,
)
# v8: full health check imported from views (was basic inline in v7)
from .views import health_check, my_payout_timeline

router = DefaultRouter()
router.register(r"batches",    PayoutBatchViewSet,          basename="payoutbatch")
router.register(r"items",      PayoutItemViewSet,           basename="payoutitem")
router.register(r"logs",       BulkProcessLogViewSet,       basename="bulkprocesslog")
router.register(r"priorities", WithdrawalPriorityViewSet,   basename="withdrawalpriority")

urlpatterns = [
    # ── Viewset routes (all 32 endpoints) ─────────────────────────────────
    path("", include(router.urls)),

    # ── User-facing views ──────────────────────────────────────────────────
    # GET /payout-queue/my-timeline/
    # Returns the authenticated user's own payout history (paginated).
    path("my-timeline/", my_payout_timeline, name="payout-my-timeline"),

    # ── v8: Health check ───────────────────────────────────────────────────
    # GET /payout-queue/health/
    # Multi-component liveness/readiness probe: DB, Redis, Celery, queue stats.
    # No auth required — suitable for Kubernetes probes and load balancers.
    path("health/", health_check, name="payout-health"),
]
