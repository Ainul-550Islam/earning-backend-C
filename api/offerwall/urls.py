"""
Offerwall URL configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'offerwall'

from .views import (
    OfferViewSet,
    OfferConversionViewSet,
    OfferCategoryViewSet,
    OfferProviderViewSet,
    OfferClickViewSet,
    OfferWallViewSet,
)

from .webhooks.TapjoyWebhook import TapjoyWebhookView
from .webhooks.AdGemWebhook import AdGemWebhookView
from .webhooks.OfferwallWebhook import OfferwallWebhookView

router = DefaultRouter()
router.register(r'offers',      OfferViewSet,           basename='offer')
router.register(r'conversions', OfferConversionViewSet, basename='conversion')
router.register(r'categories',  OfferCategoryViewSet,   basename='category')
router.register(r'providers',   OfferProviderViewSet,   basename='provider')
router.register(r'clicks',      OfferClickViewSet,      basename='click')
router.register(r'walls',       OfferWallViewSet,       basename='wall')

webhook_patterns = [
    path('tapjoy/',    TapjoyWebhookView.as_view(),    name='tapjoy-webhook'),
    path('adgem/',     AdGemWebhookView.as_view(),     name='adgem-webhook'),
    path('offertoro/', OfferwallWebhookView.as_view(), name='offertoro-webhook'),
]

urlpatterns = [
    # Custom list-level actions before router (avoid /{pk}/ conflict)
    path('offers/stats/',             OfferViewSet.as_view({'get': 'stats'}),                  name='offer-stats'),
    path('offers/featured/',          OfferViewSet.as_view({'get': 'featured'}),               name='offer-featured'),
    path('offers/trending/',          OfferViewSet.as_view({'get': 'trending'}),               name='offer-trending'),
    path('offers/recommended/',       OfferViewSet.as_view({'get': 'recommended'}),            name='offer-recommended'),
    path('conversions/stats/',        OfferConversionViewSet.as_view({'get': 'stats'}),        name='conversion-stats'),
    path('clicks/stats/',             OfferClickViewSet.as_view({'get': 'stats'}),             name='click-stats'),

    # Router URLs — handles /{pk}/, /{pk}/sync/, /{pk}/stats/ via @action decorators
    path('', include(router.urls)),

    # Webhooks
    path('webhooks/', include(webhook_patterns)),
]