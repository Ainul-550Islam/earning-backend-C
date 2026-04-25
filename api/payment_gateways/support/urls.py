# api/payment_gateways/support/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupportTicketViewSet

app_name = 'support'
router   = DefaultRouter()
router.register(r'tickets', SupportTicketViewSet, basename='ticket')

urlpatterns = [path('', include(router.urls))]
