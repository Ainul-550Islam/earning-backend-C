# api/wallet/core_services/__init__.py
"""
Core Services — atomic, integrity-protected business logic.

Usage:
    from api.wallet.core_services.wallet_manager import WalletManager

    result = WalletManager.credit(wallet, amount=Decimal("100"), category="offer")
    result = WalletManager.debit(wallet, amount=Decimal("50"), category="withdrawal")
"""
from .wallet_manager import WalletManager, ENGINE_VERSION, ENGINE_HEADER

__all__ = ["WalletManager", "ENGINE_VERSION", "ENGINE_HEADER"]
