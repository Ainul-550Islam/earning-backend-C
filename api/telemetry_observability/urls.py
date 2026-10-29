"""
URL configuration for Telemetry Observability — sub-app edition.

Include this in your main project's urls.py:

    from django.urls import path, include

    urlpatterns = [
        # All telemetry endpoints under /telemetry/
        path('telemetry/', include('api.telemetry_observability.urls')),

        # Or mount at root (ping and readiness are then at /ping/ /readiness/)
        path('', include('api.telemetry_observability.urls')),
    ]

Endpoints after include with prefix 'telemetry/':
  GET  telemetry/ping/                      — liveness probe (no auth)
  GET  telemetry/readiness/                 — readiness probe (no auth)
  *    telemetry/api/v1/telemetry/metrics/  — metrics CRUD + viewset
  *    telemetry/api/v1/telemetry/logs/
  *    telemetry/api/v1/telemetry/traces/
  *    telemetry/api/v1/telemetry/alerts/
  *    telemetry/api/v1/telemetry/health/
  *    telemetry/api/v1/telemetry/dashboards/
  *    telemetry/api/v1/telemetry/analytics/

NOTE: /admin/, /api/token/, /api/token/refresh/ are NOT included here.
      They are handled by your main project's urls.py.
"""
from django.urls        import path, include
from rest_framework.routers import DefaultRouter

from .views.ping_view      import PingView, ReadinessView

from .viewsets.metric_viewset    import MetricViewSet
from .viewsets.log_viewset       import LogViewSet
from .viewsets.trace_viewset     import TraceViewSet
from .viewsets.alert_viewset     import AlertViewSet
from .viewsets.health_viewset    import HealthViewSet
from .viewsets.dashboard_viewset import DashboardViewSet
from .viewsets.analytics_viewset import AnalyticsViewSet

# ── DRF Router ────────────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r'metrics',    MetricViewSet,    basename='telemetry-metricevent')
router.register(r'logs',       LogViewSet,       basename='telemetry-logentry')
router.register(r'traces',     TraceViewSet,     basename='telemetry-tracespan')
router.register(r'alerts',     AlertViewSet,     basename='telemetry-alert')
router.register(r'health',     HealthViewSet,    basename='telemetry-healthstatus')
router.register(r'dashboards', DashboardViewSet, basename='telemetry-dashboardwidget')
router.register(r'analytics',  AnalyticsViewSet, basename='telemetry-analytics')

# ── URL patterns ──────────────────────────────────────────────────────────────
urlpatterns = [

    # Liveness & readiness probes (no auth — used by Docker / k8s)
    path('ping/',      PingView.as_view(),      name='telemetry-ping'),
    path('readiness/', ReadinessView.as_view(), name='telemetry-readiness'),

    # ViewSet routes (list/retrieve/create/update/destroy + custom actions)
    path('api/v1/telemetry/', include(router.urls)),
]
