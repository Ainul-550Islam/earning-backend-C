# api/payment_gateways/urls.py
# ✅ Bulletproof — all ViewSets registered

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    PaymentGatewayViewSet,
    PaymentGatewayMethodViewSet,
    GatewayTransactionViewSet,
    PayoutRequestViewSet,
    GatewayConfigViewSet,
    CurrencyViewSet,
    PaymentWebhookLogViewSet,
    user_active_gateways,
)

app_name = 'payment_gateways'

router = DefaultRouter()
router.register(r'gateways',     PaymentGatewayViewSet,       basename='gateway')
router.register(r'methods',      PaymentGatewayMethodViewSet, basename='payment-method')
router.register(r'transactions', GatewayTransactionViewSet,   basename='transaction')
router.register(r'payouts',      PayoutRequestViewSet,        basename='payout')
router.register(r'configs',      GatewayConfigViewSet,        basename='gateway-config')
router.register(r'currencies',   CurrencyViewSet,             basename='currency')
router.register(r'webhook-logs', PaymentWebhookLogViewSet,    basename='webhook-log')

urlpatterns = [
    path('', include(router.urls)),
    path('user/gateways/active/', user_active_gateways, name='user-gateways-active'),
    path('webhooks/', include('api.payment_gateways.webhooks.urls', namespace='webhooks')),
]