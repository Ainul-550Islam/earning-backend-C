# api/payment_gateways/notifications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InAppNotificationViewSet, DeviceTokenViewSet

app_name = 'notifications'
router   = DefaultRouter()
router.register(r'notifications', InAppNotificationViewSet, basename='notification')
router.register(r'device-tokens', DeviceTokenViewSet,       basename='device-token')

urlpatterns = [path('', include(router.urls))]
