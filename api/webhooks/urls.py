# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
urls.py: URL routing for the api.webhooks module.

Route map:
    GET/POST   /webhooks/endpoints/
    GET/PATCH/DELETE /webhooks/endpoints/{id}/
    POST       /webhooks/endpoints/{id}/rotate-secret/
    POST       /webhooks/endpoints/{id}/test/
    PATCH      /webhooks/endpoints/{id}/pause/
    PATCH      /webhooks/endpoints/{id}/resume/

    GET/POST   /webhooks/endpoints/{endpoint_pk}/subscriptions/
    GET/PATCH/DELETE /webhooks/endpoints/{endpoint_pk}/subscriptions/{id}/

    GET        /webhooks/logs/
    GET        /webhooks/logs/{id}/
    POST       /webhooks/logs/{id}/retry/

    POST       /webhooks/emit/          (admin/staff only)
    GET        /webhooks/event-types/
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter
from rest_framework_nested import routers as nested_routers

from .views import (
    EventTypeListAPIView,
    WebhookDeliveryLogViewSet,
    WebhookEmitAPIView,
    WebhookEndpointViewSet,
    WebhookSubscriptionViewSet,
)

app_name = "webhooks"

# ── Top-level router ──────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r"endpoints", WebhookEndpointViewSet, basename="webhook-endpoint")
router.register(r"logs",      WebhookDeliveryLogViewSet, basename="webhook-log")

# ── Nested router: subscriptions under endpoints ──────────────────────────────
# Use NestedSimpleRouter to avoid re-registering the drf_format_suffix converter
endpoints_router = nested_routers.NestedSimpleRouter(
    router, r"endpoints", lookup="endpoint"
)
endpoints_router.register(
    r"subscriptions",
    WebhookSubscriptionViewSet,
    basename="webhook-subscription",
)

urlpatterns = [
    path("", include(router.urls)),
    path("", include(endpoints_router.urls)),
    path("emit/",        WebhookEmitAPIView.as_view(),    name="webhook-emit"),
    path("event-types/", EventTypeListAPIView.as_view(),  name="webhook-event-types"),
]
