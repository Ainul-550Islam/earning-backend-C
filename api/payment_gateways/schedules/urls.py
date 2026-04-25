# api/payment_gateways/schedules/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentScheduleViewSet, ScheduledPayoutViewSet, EarlyPaymentViewSet

app_name = 'schedules'
router   = DefaultRouter()
router.register(r'schedules',        PaymentScheduleViewSet, basename='schedule')
router.register(r'scheduled-payouts',ScheduledPayoutViewSet, basename='scheduled-payout')
router.register(r'early-payments',   EarlyPaymentViewSet,    basename='early-payment')

urlpatterns = [path('', include(router.urls))]
