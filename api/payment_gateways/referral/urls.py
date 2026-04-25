# api/payment_gateways/referral/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReferralViewSet

app_name = 'referral'
router   = DefaultRouter()
router.register(r'referrals', ReferralViewSet, basename='referral')

urlpatterns = [path('', include(router.urls))]
