# api/payment_gateways/publisher/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PublisherProfileViewSet, AdvertiserProfileViewSet

app_name = 'publisher'
router   = DefaultRouter()
router.register(r'publishers',  PublisherProfileViewSet,  basename='publisher-profile')
router.register(r'advertisers', AdvertiserProfileViewSet, basename='advertiser-profile')

urlpatterns = [path('', include(router.urls))]
