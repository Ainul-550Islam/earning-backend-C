# api/wallet/dependencies.py
"""
Dependency injection for wallet services.
Uses simple factory pattern — no heavy DI framework needed.

Usage in views/viewsets:
    from .dependencies import get_wallet_service, get_withdrawal_service

    class MyView(APIView):
        def __init__(self):
            self.wallet_service = get_wallet_service()
            self.withdrawal_service = get_withdrawal_service()
"""
import logging
from functools import lru_cache

logger = logging.getLogger("wallet.dependencies")


@lru_cache(maxsize=None)
def get_wallet_service():
    from .services.core.WalletService import WalletService
    return WalletService


@lru_cache(maxsize=None)
def get_transaction_service():
    from .services.core.TransactionService import TransactionService
    return TransactionService


@lru_cache(maxsize=None)
def get_balance_service():
    from .services.core.BalanceService import BalanceService
    return BalanceService


@lru_cache(maxsize=None)
def get_idempotency_service():
    from .services.core.IdempotencyService import IdempotencyService
    return IdempotencyService


@lru_cache(maxsize=None)
def get_withdrawal_service():
    from .services.withdrawal.WithdrawalService import WithdrawalService
    return WithdrawalService


@lru_cache(maxsize=None)
def get_withdrawal_fee_service():
    from .services.withdrawal.WithdrawalFeeService import WithdrawalFeeService
    return WithdrawalFeeService


@lru_cache(maxsize=None)
def get_withdrawal_limit_service():
    from .services.withdrawal.WithdrawalLimitService import WithdrawalLimitService
    return WithdrawalLimitService


@lru_cache(maxsize=None)
def get_earning_service():
    from .services.earning.EarningService import EarningService
    return EarningService


@lru_cache(maxsize=None)
def get_cap_service():
    from .services.earning.EarningCapService import EarningCapService
    return EarningCapService


@lru_cache(maxsize=None)
def get_payout_service():
    from .services.earning.PayoutService import PayoutService
    return PayoutService


@lru_cache(maxsize=None)
def get_cpalead_service():
    from .services.cpalead.CPALeadService import CPALeadService
    return CPALeadService


@lru_cache(maxsize=None)
def get_analytics_service():
    from .services.WalletAnalyticsService import WalletAnalyticsService
    return WalletAnalyticsService


@lru_cache(maxsize=None)
def get_ledger_service():
    from .services.ledger.LedgerService import LedgerService
    return LedgerService


@lru_cache(maxsize=None)
def get_gateway(gateway_name: str):
    """Get gateway service by name."""
    gateways = {
        "bkash":     "services.gateway.BkashService.BkashService",
        "nagad":     "services.gateway.NagadService.NagadService",
        "usdt":      "services.gateway.UsdtService.UsdtService",
        "rocket":    "services.gateway.RocketService.RocketService",
        "paypal":    "services.gateway.PayPalService.PayPalService",
        "stripe":    "services.gateway.StripeService.StripeService",
        "sslcommerz":"services.gateway.SSLCommerzService.SSLCommerzService",
    }
    path = gateways.get(gateway_name.lower())
    if not path:
        raise ValueError(f"Unknown gateway: {gateway_name}")
    module_path, class_name = path.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(f"api.wallet.{module_path}")
    return getattr(mod, class_name)
