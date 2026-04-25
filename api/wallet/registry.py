# api/wallet/registry.py
"""
Service registry — centralized access to all wallet services and gateways.
Prevents circular imports and makes dependency injection easy.

Usage:
    from .registry import wallet_registry
    svc = wallet_registry.get("WalletService")
    gateway = wallet_registry.get_gateway("bkash")
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("wallet.registry")


class WalletRegistry:
    """Central registry for wallet services, gateways, and validators."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._gateways: Dict[str, Any] = {}
        self._validators: Dict[str, Any] = {}

    def register(self, name: str, service_class) -> None:
        self._services[name] = service_class
        logger.debug(f"Registered service: {name}")

    def register_gateway(self, name: str, gateway_class) -> None:
        self._gateways[name] = gateway_class
        logger.debug(f"Registered gateway: {name}")

    def get(self, name: str) -> Optional[Any]:
        return self._services.get(name)

    def get_gateway(self, name: str) -> Optional[Any]:
        return self._gateways.get(name)

    def all_gateways(self) -> dict:
        return dict(self._gateways)

    def _auto_register(self):
        """Auto-register all services and gateways."""
        # Core services
        try:
            from .services.core.WalletService import WalletService
            from .services.core.TransactionService import TransactionService
            from .services.core.BalanceService import BalanceService
            from .services.core.IdempotencyService import IdempotencyService
            from .services.withdrawal.WithdrawalService import WithdrawalService
            from .services.withdrawal.WithdrawalFeeService import WithdrawalFeeService
            from .services.earning.EarningService import EarningService
            from .services.earning.EarningCapService import EarningCapService
            from .services.cpalead.CPALeadService import CPALeadService
            from .services.WalletAnalyticsService import WalletAnalyticsService

            for name, cls in [
                ("WalletService", WalletService),
                ("TransactionService", TransactionService),
                ("BalanceService", BalanceService),
                ("IdempotencyService", IdempotencyService),
                ("WithdrawalService", WithdrawalService),
                ("WithdrawalFeeService", WithdrawalFeeService),
                ("EarningService", EarningService),
                ("EarningCapService", EarningCapService),
                ("CPALeadService", CPALeadService),
                ("WalletAnalyticsService", WalletAnalyticsService),
            ]:
                self.register(name, cls)
        except ImportError as e:
            logger.debug(f"Service auto-register skip: {e}")

        # Gateways
        gateways = [
            ("bkash",       "services.gateway.BkashService",       "BkashService"),
            ("nagad",       "services.gateway.NagadService",        "NagadService"),
            ("usdt",        "services.gateway.UsdtService",         "UsdtService"),
            ("rocket",      "services.gateway.RocketService",       "RocketService"),
            ("paypal",      "services.gateway.PayPalService",       "PayPalService"),
            ("stripe",      "services.gateway.StripeService",       "StripeService"),
            ("sslcommerz",  "services.gateway.SSLCommerzService",   "SSLCommerzService"),
        ]
        for gw_name, module_path, class_name in gateways:
            try:
                import importlib
                mod = importlib.import_module(f"api.wallet.{module_path}")
                cls = getattr(mod, class_name)
                self.register_gateway(gw_name, cls)
            except Exception:
                pass


# ── Singleton ─────────────────────────────────────────────────
wallet_registry = WalletRegistry()
