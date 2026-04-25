# api/payment_gateways/refunds/urls.py
# FILE 62 of 257

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RefundRequestViewSet, RefundPolicyViewSet

app_name = 'refunds'

router = DefaultRouter()
router.register(r'refunds',  RefundRequestViewSet, basename='refund')
router.register(r'policies', RefundPolicyViewSet,  basename='refund-policy')

urlpatterns = [
    path('', include(router.urls)),
]
