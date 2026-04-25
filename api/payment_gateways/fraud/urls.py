# api/payment_gateways/fraud/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FraudAlertViewSet

app_name = 'fraud'
router   = DefaultRouter()
router.register(r'alerts', FraudAlertViewSet, basename='fraud-alert')

urlpatterns = [path('', include(router.urls))]
