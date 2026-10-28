# api_finance/urls.py
"""URL routing for the Finance app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WalletViewSet,
    TransactionViewSet,
    PayoutRequestViewSet,
    AdminWalletViewSet,
    AdminTransactionViewSet,
    AdminPayoutRequestViewSet,
    ReconciliationViewSet,
)

app_name = 'api_finance'

router = DefaultRouter()

# ── User-facing ───────────────────────────────────────────────────────────────
router.register(r'wallet',           WalletViewSet,       basename='wallet')
router.register(r'transactions',     TransactionViewSet,  basename='transaction')
router.register(r'payout-requests',  PayoutRequestViewSet, basename='payout-request')

# ── Admin ─────────────────────────────────────────────────────────────────────
router.register(r'admin/wallets',         AdminWalletViewSet,        basename='admin-wallet')
router.register(r'admin/transactions',    AdminTransactionViewSet,   basename='admin-transaction')
router.register(r'admin/payout-requests', AdminPayoutRequestViewSet, basename='admin-payout-request')
router.register(r'admin/reconciliations', ReconciliationViewSet,     basename='reconciliation')

urlpatterns = [
    path('', include(router.urls)),
]
