# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
urls.py: URL routing for api.webhooks

FIX APPLIED: Registered 11 previously floating ViewSets into URL routes.

Full Route Map:
    CORE
        GET/POST        /webhooks/endpoints/
        GET/PATCH/DELETE /webhooks/endpoints/{id}/
        POST            /webhooks/endpoints/{id}/rotate-secret/
        POST            /webhooks/endpoints/{id}/test/
        PATCH           /webhooks/endpoints/{id}/pause/
        PATCH           /webhooks/endpoints/{id}/resume/
        GET/POST        /webhooks/endpoints/{endpoint_pk}/subscriptions/
        GET/PATCH/DELETE /webhooks/endpoints/{endpoint_pk}/subscriptions/{id}/
        GET             /webhooks/logs/
        GET             /webhooks/logs/{id}/
        POST            /webhooks/logs/{id}/retry/
        POST            /webhooks/emit/
        GET             /webhooks/event-types/

    ADVANCED (newly wired)
        GET/POST/…      /webhooks/filters/
        GET/POST/…      /webhooks/templates/
        GET/POST/…      /webhooks/batches/
        POST            /webhooks/batches/{id}/process/
        GET/POST/…      /webhooks/secrets/
        POST            /webhooks/secrets/{id}/rotate/
        GET/POST/…      /webhooks/replay/
        POST            /webhooks/replay/create-batch/
        GET             /webhooks/replay/history/
        GET             /webhooks/replay/statistics/

    INBOUND (newly wired)
        GET/POST/…      /webhooks/inbound/
        POST            /webhooks/inbound/{id}/activate/
        POST            /webhooks/inbound/{id}/deactivate/
        GET/POST/…      /webhooks/inbound-logs/

    ANALYTICS & HEALTH (newly wired)
        GET/…           /webhooks/analytics/
        GET             /webhooks/analytics/{id}/health-summary/
        GET             /webhooks/analytics/{id}/performance-report/
        GET             /webhooks/analytics/{id}/event-stats/
        POST            /webhooks/analytics/{id}/export-csv/
        GET/…           /webhooks/health/
        POST            /webhooks/health/check-health/
        GET             /webhooks/health/batch-check/
        GET             /webhooks/health/{id}/trends/
        GET             /webhooks/health/{id}/alerts/

    ADMIN (staff only, newly wired)
        GET/…           /webhooks/admin/webhooks/
        POST            /webhooks/admin/webhooks/{id}/force-dispatch/
        POST            /webhooks/admin/webhooks/{id}/suspend/

    AGING
        GET             /webhooks/aging/endpoints/
        GET             /webhooks/aging/endpoints/{id}/
        POST            /webhooks/aging/endpoints/{id}/evaluate/
        GET             /webhooks/aging/logs/
        GET             /webhooks/aging/events/
        GET             /webhooks/aging/summary/
        GET/PUT         /webhooks/aging/policy/
        POST            /webhooks/aging/archive/  (staff)
        POST            /webhooks/aging/purge/    (staff)
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers as nested_routers

# ── Core views (from views.py) ────────────────────────────────────────────────
from .views import (
    EventTypeListAPIView,
    EventTypeValidateAPIView,
    EventTypeTrendAPIView,
    EventTypeDetailAPIView,
    WebhookDeliveryLogViewSet,
    WebhookEmitAPIView,
    WebhookEmitPreviewAPIView,
    WebhookEmitValidateAPIView,
    WebhookEndpointViewSet,
    WebhookSubscriptionViewSet,
)

# ── Advanced viewsets (from viewsets/) — previously floating ─────────────────
from .viewsets.WebhookFilterViewSet    import WebhookFilterViewSet
from .viewsets.WebhookTemplateViewSet  import WebhookTemplateViewSet
from .viewsets.WebhookBatchViewSet     import WebhookBatchViewSet
from .viewsets.WebhookSecretViewSet    import WebhookSecretViewSet
from .viewsets.WebhookReplayViewSet    import WebhookReplayViewSet
from .viewsets.InboundWebhookViewSet   import InboundWebhookViewSet
from .viewsets.InboundWebhookLogViewSet import InboundWebhookLogViewSet
from .viewsets.WebhookAnalyticsViewSet import WebhookAnalyticsViewSet
from .viewsets.WebhookHealthViewSet    import WebhookHealthViewSet
from .viewsets.AdminWebhookViewSet     import AdminWebhookViewSet
from .viewsets.WebhookRateLimitViewSet  import WebhookRateLimitViewSet, WebhookRetryAnalysisViewSet

# FIX: Public inbound receiver — connects PayloadParser + SignatureVerifier
from .inbound_receiver import InboundWebhookReceiverView

# ── Aging viewsets ────────────────────────────────────────────────────────────
from .viewsets.WebhookAgingViewSet import (
    WebhookAgingArchiveAPIView,
    WebhookAgingEventViewSet,
    WebhookAgingPolicyAPIView,
    WebhookAgingPurgeAPIView,
    WebhookAgingSummaryAPIView,
    WebhookDeliveryAgingViewSet,
    WebhookEndpointAgingViewSet,
)

app_name = "webhooks"

# ─────────────────────────────────────────────────────────────────────────────
#  ROUTERS
# ─────────────────────────────────────────────────────────────────────────────

# Top-level core router
router = SimpleRouter()
router.register(r"endpoints", WebhookEndpointViewSet, basename="webhook-endpoint")
router.register(r"logs",      WebhookDeliveryLogViewSet, basename="webhook-log")

# Advanced feature routers (previously missing)
router.register(r"filters",      WebhookFilterViewSet,    basename="webhook-filter")
router.register(r"templates",    WebhookTemplateViewSet,  basename="webhook-template")
router.register(r"batches",      WebhookBatchViewSet,     basename="webhook-batch")
router.register(r"secrets",      WebhookSecretViewSet,    basename="webhook-secret")
router.register(r"replay",       WebhookReplayViewSet,    basename="webhook-replay")
router.register(r"inbound",      InboundWebhookViewSet,   basename="webhook-inbound")
router.register(r"inbound-logs", InboundWebhookLogViewSet, basename="webhook-inbound-log")
router.register(r"analytics",    WebhookAnalyticsViewSet, basename="webhook-analytics")
router.register(r"health",       WebhookHealthViewSet,    basename="webhook-health")
router.register(r"admin/webhooks", AdminWebhookViewSet,   basename="webhook-admin")
router.register(r"rate-limits",    WebhookRateLimitViewSet,     basename="webhook-rate-limit")
router.register(r"retry-analysis", WebhookRetryAnalysisViewSet, basename="webhook-retry-analysis")

# Aging router
aging_router = SimpleRouter()
aging_router.register(r"endpoints", WebhookEndpointAgingViewSet, basename="aging-endpoint")
aging_router.register(r"logs",      WebhookDeliveryAgingViewSet, basename="aging-log")
aging_router.register(r"events",    WebhookAgingEventViewSet,    basename="aging-event")

# Nested: subscriptions under endpoints
endpoints_router = nested_routers.NestedSimpleRouter(
    router, r"endpoints", lookup="endpoint"
)
endpoints_router.register(
    r"subscriptions",
    WebhookSubscriptionViewSet,
    basename="webhook-subscription",
)

# ─────────────────────────────────────────────────────────────────────────────
#  URL PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

urlpatterns = [
    # ── Core ──────────────────────────────────────────────────────────────────
    path("", include(router.urls)),
    path("", include(endpoints_router.urls)),
    path("emit/",             WebhookEmitAPIView.as_view(),          name="webhook-emit"),
    path("emit/preview/",     WebhookEmitPreviewAPIView.as_view(),   name="webhook-emit-preview"),
    path("emit/validate/",    WebhookEmitValidateAPIView.as_view(),  name="webhook-emit-validate"),
    path("event-types/",          EventTypeListAPIView.as_view(),     name="webhook-event-types"),
    path("event-types/validate/", EventTypeValidateAPIView.as_view(), name="webhook-event-type-validate"),
    path("event-types/trends/",   EventTypeTrendAPIView.as_view(),    name="webhook-event-type-trends"),
    path("event-types/<str:event_type>/details/", EventTypeDetailAPIView.as_view(), name="webhook-event-type-detail"),

    # ── Public inbound receiver (bKash / Nagad / Stripe / PayPal) ───────────────
    # FIX: PayloadParser and SignatureVerifier were floating; this route wires them.
    path("receive/<str:source>/", InboundWebhookReceiverView.as_view(), name="inbound-receive"),

    # ── Aging ─────────────────────────────────────────────────────────────────
    path("aging/",         include(aging_router.urls)),
    path("aging/summary/", WebhookAgingSummaryAPIView.as_view(), name="aging-summary"),
    path("aging/policy/",  WebhookAgingPolicyAPIView.as_view(),  name="aging-policy"),
    path("aging/archive/", WebhookAgingArchiveAPIView.as_view(), name="aging-archive"),
    path("aging/purge/",   WebhookAgingPurgeAPIView.as_view(),   name="aging-purge"),
]
