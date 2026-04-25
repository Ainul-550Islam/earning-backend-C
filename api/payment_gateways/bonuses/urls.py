# api/payment_gateways/bonuses/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PerformanceTierViewSet, PublisherBonusViewSet

app_name = 'bonuses'
router   = DefaultRouter()
router.register(r'tiers',   PerformanceTierViewSet, basename='tier')
router.register(r'bonuses', PublisherBonusViewSet,  basename='bonus')

urlpatterns = [path('', include(router.urls))]
