"""
URL configuration for Real-time Dashboard Backend.

Mount in config/urls.py as:
    path('api/', include('api.realtime_dashboard.urls')),

This gives:
    /api/widgets/
    /api/widget-configurations/
    /api/metrics/
    /api/layouts/
    /api/dashboards/
    /api/connections/
    /api/health/
    /api/schema/                 (raw OpenAPI 3 schema, YAML)
    /api/schema/swagger-ui/      (interactive Swagger UI)
    /api/schema/redoc/           (ReDoc reference viewer)

WebSocket URLs (in config/asgi.py via routing.py):
    ws/dashboard/<id>/
    ws/metric/<id>/
    ws/events/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from .viewsets.dashboard_widget_viewset import DashboardWidgetViewSet
from .viewsets.widget_configuration_viewset import WidgetConfigurationViewSet
from .viewsets.real_time_metric_viewset import RealTimeMetricViewSet
from .viewsets.dashboard_layout_viewset import DashboardLayoutViewSet
from .viewsets.user_dashboard_viewset import UserDashboardViewSet
from .viewsets.websocket_connection_viewset import WebSocketConnectionViewSet
from .views import health_check

router = DefaultRouter()
router.register(r'widgets', DashboardWidgetViewSet, basename='dashboardwidget')
router.register(r'widget-configurations', WidgetConfigurationViewSet, basename='widgetconfiguration')
router.register(r'metrics', RealTimeMetricViewSet, basename='realtimemetric')
router.register(r'layouts', DashboardLayoutViewSet, basename='dashboardlayout')
router.register(r'dashboards', UserDashboardViewSet, basename='userdashboard')
router.register(r'connections', WebSocketConnectionViewSet, basename='websocketconnection')

# NOTE: no 'api/' prefix here — the prefix comes from config/urls.py mount point.
# FIXED: previously had path('api/', include(router.urls)) which caused
# double prefix /api/api/widgets/ when mounted as path('api/', include(...))
urlpatterns = [
    path('', include(router.urls)),
    path('health/', health_check, name='health-check'),
    # ADDED (v1.4.0): OpenAPI 3 schema + docs UIs, see SPECTACULAR_SETTINGS
    # in settings.py for title/description/versioning.
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
