# api/payment_gateways/urls.py — WORLD #1 COMPLETE — 100% CPAlead+ parity
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    PaymentGatewayViewSet, GatewayTransactionViewSet, WithdrawalGatewayViewSet,
    DepositRequestViewSet, DepositCallbackViewSet, DepositRefundViewSet,
    GatewayCredentialViewSet, GatewayLimitViewSet, GatewayFeeRuleViewSet,
    GatewayHealthViewSet, GatewayHealthAPIView, GatewayStatementViewSet,
    ReconciliationViewSet, GatewayAnalyticsViewSet, PaymentAnalyticsViewSet,
    AdminPaymentViewSet, WebhookReceiverViewSet,
)
from .viewsets.PublisherEarningsViewSet import PublisherEarningsViewSet
from .attachment_upload_view import upload_attachment
from .endpoint import gateway_status_endpoint

app_name = 'payment_gateways'
router   = DefaultRouter()

# Core payment
router.register(r'gateways',        PaymentGatewayViewSet,    basename='gateway')
router.register(r'transactions',    GatewayTransactionViewSet,basename='transaction')
router.register(r'withdrawals',     WithdrawalGatewayViewSet, basename='withdrawal')
router.register(r'deposits',        DepositRequestViewSet,    basename='deposit')
router.register(r'deposit-callbacks',DepositCallbackViewSet,  basename='deposit-callback')
router.register(r'deposit-refunds', DepositRefundViewSet,     basename='deposit-refund')
router.register(r'credentials',     GatewayCredentialViewSet, basename='credential')
router.register(r'limits',          GatewayLimitViewSet,      basename='limit')
router.register(r'fee-rules',       GatewayFeeRuleViewSet,    basename='fee-rule')
router.register(r'health',          GatewayHealthViewSet,     basename='health')
router.register(r'statements',      GatewayStatementViewSet,  basename='statement')
router.register(r'reconciliation',  ReconciliationViewSet,    basename='reconciliation')
router.register(r'analytics',       GatewayAnalyticsViewSet,  basename='analytics')
router.register(r'payment-analytics',PaymentAnalyticsViewSet, basename='payment-analytics')
router.register(r'admin-overview',  AdminPaymentViewSet,      basename='admin-overview')
router.register(r'earnings',        PublisherEarningsViewSet, basename='earnings')

urlpatterns = [
    path('', include(router.urls)),
    path('status/', GatewayHealthAPIView.as_view(), name='public-status'),

    # Core sub-apps
    path('', include('api.payment_gateways.refunds.urls',       namespace='refunds')),
    path('', include('api.payment_gateways.fraud.urls',         namespace='fraud')),
    path('', include('api.payment_gateways.notifications.urls', namespace='notifications')),
    path('', include('api.payment_gateways.reports.urls',       namespace='reports')),
    path('', include('api.payment_gateways.schedules.urls',     namespace='schedules')),
    path('', include('api.payment_gateways.referral.urls',      namespace='referral')),

    # World #1 modules
    path('tracking/',      include('api.payment_gateways.tracking.urls',      namespace='tracking')),
    path('offers/',        include('api.payment_gateways.offers.urls',        namespace='offers')),
    path('rtb/',           include('api.payment_gateways.rtb.urls',           namespace='rtb')),
    path('network/',       include('api.payment_gateways.publisher.urls',     namespace='publisher')),

    # 100% CPAlead+ features
    path('locker/',        include('api.payment_gateways.locker.urls',        namespace='locker')),
    path('traffic/',       include('api.payment_gateways.blacklist.urls',     namespace='blacklist')),
    path('integrations/',  include('api.payment_gateways.integrations.urls',  namespace='integrations')),
    path('smartlink/',     include('api.payment_gateways.smartlink.urls',     namespace='smartlink')),
    path('bonuses/',       include('api.payment_gateways.bonuses.urls',       namespace='bonuses')),
    path('support/',       include('api.payment_gateways.support.urls',       namespace='support')),

    path('upload/',        upload_attachment,              name='upload'),
    path('live-stats/',    gateway_status_endpoint,         name='live-stats'),

    # Webhooks
    path('webhooks/', include('api.payment_gateways.webhooks.urls', namespace='webhooks')),
]
