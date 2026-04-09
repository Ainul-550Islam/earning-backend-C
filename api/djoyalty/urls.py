# api/djoyalty/urls.py
"""
Djoyalty URL configuration।
API versioning + health checks + all endpoints।
"""
from django.urls import path, include
from .routers import get_djoyalty_router
from .health import HealthCheckView, LivenessCheckView, ReadinessCheckView, PingView

# Use the router with all ViewSets pre-registered
router = get_djoyalty_router()

urlpatterns = [
    # ==================== HEALTH CHECKS ====================
    path('health/', HealthCheckView.as_view(), name='djoyalty-health'),
    path('health/live/', LivenessCheckView.as_view(), name='djoyalty-liveness'),
    path('health/ready/', ReadinessCheckView.as_view(), name='djoyalty-readiness'),
    path('ping/', PingView.as_view(), name='djoyalty-ping'),

    # ==================== API ROUTES ====================
    path('', include(router.urls)),
]

# Optional: OpenAPI schema URLs (requires drf-spectacular)
try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    urlpatterns += [
        path('schema/', SpectacularAPIView.as_view(), name='djoyalty-schema'),
        path('docs/', SpectacularSwaggerView.as_view(url_name='djoyalty-schema'), name='djoyalty-swagger'),
        path('redoc/', SpectacularRedocView.as_view(url_name='djoyalty-schema'), name='djoyalty-redoc'),
    ]
except ImportError:
    pass
