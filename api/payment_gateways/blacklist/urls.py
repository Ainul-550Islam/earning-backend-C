# api/payment_gateways/blacklist/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrafficBlacklistViewSet, OfferQualityViewSet

app_name = 'blacklist'
router   = DefaultRouter()
router.register(r'blacklist', TrafficBlacklistViewSet, basename='blacklist')
router.register(r'quality',   OfferQualityViewSet,     basename='quality')

urlpatterns = [path('', include(router.urls))]
