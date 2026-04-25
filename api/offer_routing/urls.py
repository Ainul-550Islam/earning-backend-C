"""
URL Configuration for Offer Routing System
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    OfferRouteViewSet, RouteConditionViewSet, GeoRouteRuleViewSet,
    DeviceRouteRuleViewSet, OfferScoreViewSet, OfferRoutingCapViewSet,
    RoutingABTestViewSet, FallbackRuleViewSet, PersonalizationConfigViewSet,
    RoutingDecisionViewSet, RoutingInsightViewSet, RoutePerformanceViewSet,
    PublicRoutingViewSet, AdminRoutingViewSet
)

# Create API router
router = DefaultRouter()
router.register(r'routes', OfferRouteViewSet, basename='route')
router.register(r'conditions', RouteConditionViewSet, basename='condition')
router.register(r'geo-rules', GeoRouteRuleViewSet, basename='geo-rule')
router.register(r'device-rules', DeviceRouteRuleViewSet, basename='device-rule')
router.register(r'scores', OfferScoreViewSet, basename='score')
router.register(r'caps', OfferRoutingCapViewSet, basename='cap')
router.register(r'ab-tests', RoutingABTestViewSet, basename='ab-test')
router.register(r'fallbacks', FallbackRuleViewSet, basename='fallback')
router.register(r'personalization', PersonalizationConfigViewSet, basename='personalization')
router.register(r'decisions', RoutingDecisionViewSet, basename='decision')
router.register(r'insights', RoutingInsightViewSet, basename='insight')
router.register(r'performance', RoutePerformanceViewSet, basename='performance')

app_name = 'offer_routing'

urlpatterns = [
    # Admin API endpoints
    path('admin/', AdminRoutingViewSet.as_view({'get': 'list'}), name='admin-routing'),
    
    # Public routing endpoint (for mobile apps)
    path('route/', PublicRoutingViewSet.as_view({'get': 'route'}), name='public-routing'),
    
    # API router
    path('api/v1/', include(router.urls)),
    
    # Health check
    path('health/', lambda r: JsonResponse({'status': 'healthy'}), name='health'),
]
