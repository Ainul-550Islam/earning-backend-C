# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/urls.py  — NEW FILE
# Included by master urls.py under: path("integration/", include(...))
# =============================================================================
from django.urls import path
from .views import (
    # Bridge
    IntegrationBridgeStatusView, IntegrationBridgeSyncView, IntegrationBridgeHealthView,
    # Auth Bridge
    AuthBridgeVerifyView, AuthBridgeRefreshView, AuthBridgeStatusView,
    # Data Bridge
    DataBridgeSyncView, DataBridgeFetchView, DataBridgeValidateView,
    # Event Bus
    EventBusPublishView, EventBusSubscriptionsView, EventBusStatsView,
    # Circuit Breaker
    CircuitBreakerStatusView, CircuitBreakerResetView,
    # Message Queue
    MessageQueueStatsView, MessageQueueEnqueueView, MessageQueuePurgeView,
    # Performance
    IntegrationPerformanceView,
    # Sync Manager
    SyncManagerStatusView, SyncManagerTriggerView,
    # Webhooks
    WebhookListView, WebhookRegisterView, WebhookDeliverView,
    # Versioning
    IntegrationVersionView,
    # Audit Logs
    IntegrationAuditLogView,
    # Registry
    IntegrationRegistryView, IntegrationRegistryAdapterView,
    # Fallback
    FallbackStatusView, FallbackTriggerView,
)

app_name = "integration"

urlpatterns = [
    # ── Bridge ────────────────────────────────────────────────────────────────
    path("bridge/status/",  IntegrationBridgeStatusView.as_view(),  name="bridge-status"),
    path("bridge/sync/",    IntegrationBridgeSyncView.as_view(),    name="bridge-sync"),
    path("bridge/health/",  IntegrationBridgeHealthView.as_view(),  name="bridge-health"),

    # ── Auth Bridge ───────────────────────────────────────────────────────────
    path("auth/verify/",    AuthBridgeVerifyView.as_view(),  name="auth-verify"),
    path("auth/refresh/",   AuthBridgeRefreshView.as_view(), name="auth-refresh"),
    path("auth/status/",    AuthBridgeStatusView.as_view(),  name="auth-status"),

    # ── Data Bridge ───────────────────────────────────────────────────────────
    path("data/sync/",      DataBridgeSyncView.as_view(),     name="data-sync"),
    path("data/fetch/",     DataBridgeFetchView.as_view(),    name="data-fetch"),
    path("data/validate/",  DataBridgeValidateView.as_view(), name="data-validate"),

    # ── Event Bus ─────────────────────────────────────────────────────────────
    path("events/publish/",       EventBusPublishView.as_view(),       name="events-publish"),
    path("events/subscriptions/", EventBusSubscriptionsView.as_view(), name="events-subscriptions"),
    path("events/stats/",         EventBusStatsView.as_view(),         name="events-stats"),

    # ── Circuit Breaker ───────────────────────────────────────────────────────
    path("circuit-breaker/status/", CircuitBreakerStatusView.as_view(), name="circuit-breaker-status"),
    path("circuit-breaker/reset/",  CircuitBreakerResetView.as_view(),  name="circuit-breaker-reset"),

    # ── Message Queue ─────────────────────────────────────────────────────────
    path("queue/stats/",   MessageQueueStatsView.as_view(),   name="queue-stats"),
    path("queue/enqueue/", MessageQueueEnqueueView.as_view(), name="queue-enqueue"),
    path("queue/purge/",   MessageQueuePurgeView.as_view(),   name="queue-purge"),

    # ── Performance ───────────────────────────────────────────────────────────
    path("performance/",   IntegrationPerformanceView.as_view(), name="performance"),

    # ── Sync Manager ──────────────────────────────────────────────────────────
    path("sync/status/",  SyncManagerStatusView.as_view(),  name="sync-status"),
    path("sync/trigger/", SyncManagerTriggerView.as_view(), name="sync-trigger"),

    # ── Webhooks ──────────────────────────────────────────────────────────────
    path("webhooks/",           WebhookListView.as_view(),     name="webhooks-list"),
    path("webhooks/register/",  WebhookRegisterView.as_view(), name="webhooks-register"),
    path("webhooks/deliver/",   WebhookDeliverView.as_view(),  name="webhooks-deliver"),

    # ── Version / Audit / Registry / Fallback ────────────────────────────────
    path("version/",                              IntegrationVersionView.as_view(),          name="version"),
    path("audit-logs/",                           IntegrationAuditLogView.as_view(),         name="audit-logs"),
    path("registry/",                             IntegrationRegistryView.as_view(),         name="registry"),
    path("registry/<str:adapter_name>/",          IntegrationRegistryAdapterView.as_view(),  name="registry-adapter"),
    path("fallback/status/",                      FallbackStatusView.as_view(),              name="fallback-status"),
    path("fallback/trigger/",                     FallbackTriggerView.as_view(),             name="fallback-trigger"),
]
