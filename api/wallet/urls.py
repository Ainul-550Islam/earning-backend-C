# wallet/urls.py (Fixed)
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from .api_views import CryptoPayoutView, EarningsBreakdownView

# Import ViewSets and Views from views.py
from . import views
from .views import (
    WalletViewSet,
    WalletTransactionViewSet,
    UserPaymentMethodViewSet,
    WithdrawalViewSet,
    WalletWebhookLogViewSet,
    WalletSummaryAPIView,
    BulkWalletOperationAPIView,
    # Task APIs
    ExpireBonusBalancesAPIView,
    ProcessWithdrawalsAPIView,
    CleanupLogsAPIView,
    GenerateReportAPIView,
    SyncPaymentsAPIView,
    # User Task APIs
    UserRequestWithdrawalAPIView,
    UserAddFundsAPIView,
)

# Import from api_views.py
from .api_views import (
    WalletBalanceView,
    TransactionHistoryView,
    AddMoneyView,
    WithdrawMoneyView,
    PaymentMethodsView,
    WithdrawalHistoryView,
    WalletStatisticsView
)

# Router setup
router = DefaultRouter()
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', WalletTransactionViewSet, basename='transaction')
router.register(r'payment-methods-crud', UserPaymentMethodViewSet, basename='paymentmethod-crud')
router.register(r'withdrawals-crud', WithdrawalViewSet, basename='withdrawal-crud')
router.register(r'webhooks', WalletWebhookLogViewSet, basename='webhook')

# Task URLs for Admin/Automation
task_urlpatterns = [
    path('expire-bonus/', ExpireBonusBalancesAPIView.as_view(), name='task-expire-bonus'),
    path('process-withdrawals/', ProcessWithdrawalsAPIView.as_view(), name='task-process-withdrawals'),
    path('cleanup-logs/', CleanupLogsAPIView.as_view(), name='task-cleanup-logs'),
    path('generate-report/', GenerateReportAPIView.as_view(), name='task-generate-report'),
    path('sync-payments/', SyncPaymentsAPIView.as_view(), name='task-sync-payments'),
]

# User task URLs
user_task_urlpatterns = [
    path('withdraw/request/', UserRequestWithdrawalAPIView.as_view(), name='user-withdraw-request'),
    path('funds/add/', UserAddFundsAPIView.as_view(), name='user-add-funds'),
]

# Main URL patterns
urlpatterns = [
    # Router URLs (ViewSets)
    path('', include(router.urls)),
    
    # Admin/Summary APIs
    path('transfer/', views.wallet_transfer, name='wallet-transfer'),
    path('mining/start/', views.mining_start, name='mining-start'),
    path('mining/stop/', views.mining_stop, name='mining-stop'),
    path('mining/status/', views.mining_status, name='mining-status'),
    path('summary/', WalletSummaryAPIView.as_view(), name='wallet-summary'),
    path('bulk-operations/', BulkWalletOperationAPIView.as_view(), name='bulk-operations'),
    
    # User APIs (from api_views.py)
    path('balance/', WalletBalanceView.as_view(), name='wallet-balance'),
    path('transactions/', TransactionHistoryView.as_view(), name='transaction-history'),
    path('add-money/', AddMoneyView.as_view(), name='add-money'),
    path('withdraw/', WithdrawMoneyView.as_view(), name='withdraw'),
    path('payment-methods/', PaymentMethodsView.as_view(), name='payment-methods'),
    path('withdrawals/<int:pk>/', WithdrawalHistoryView.as_view(), name='withdrawal-detail'),
    path('withdrawals/', WithdrawalHistoryView.as_view(), name='withdrawal-history'),
    path('statistics/', WalletStatisticsView.as_view(), name='wallet-statistics'),
    
#
    path('crypto-payout/', CryptoPayoutView.as_view(), name='crypto-payout'),
    path('earnings/breakdown/', EarningsBreakdownView.as_view(), name='earnings-breakdown'),
    # Task endpoints
    path('tasks/', include(task_urlpatterns)),
    
    # User endpoints
    path('user/', include(user_task_urlpatterns)),
    path('request-withdrawal/', UserRequestWithdrawalAPIView.as_view(), name='request-withdrawal'),
    
    # Webhook endpoints (no auth required)
    path('webhook/bkash/', WalletWebhookLogViewSet.as_view({'post': 'handle_webhook'}), name='bkash-webhook'),
    path('webhook/nagad/', WalletWebhookLogViewSet.as_view({'post': 'handle_webhook'}), name='nagad-webhook'),
    path('webhook/sslcommerz/', WalletWebhookLogViewSet.as_view({'post': 'handle_webhook'}), name='sslcommerz-webhook'),
]