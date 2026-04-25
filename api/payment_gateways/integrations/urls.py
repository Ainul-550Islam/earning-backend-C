# api/payment_gateways/integrations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrackerIntegrationViewSet

app_name = 'integrations'
router   = DefaultRouter()
router.register(r'tracker-integrations', TrackerIntegrationViewSet,
                basename='tracker-integration')

urlpatterns = [path('', include(router.urls))]
