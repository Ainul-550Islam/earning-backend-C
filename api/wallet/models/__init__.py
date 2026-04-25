# api/wallet/models/__init__.py
"""
All 35 wallet models — import from here.

Original models (Wallet, WalletTransaction, UserPaymentMethod,
Withdrawal, WithdrawalRequest, WalletWebhookLog) are fully
preserved and available here.
"""
from .core import Wallet, WalletTransaction
from .ledger import (
    WalletLedger, LedgerEntry, LedgerSnapshot,
    LedgerReconciliation, IdempotencyKey,
)
from .withdrawal import (
    WithdrawalMethod, WithdrawalRequest, WithdrawalLimit,
    WithdrawalFee, WithdrawalBatch, WithdrawalBlock,
)
from .balance import (
    BalanceHistory, BalanceLock, BalanceAlert,
    BalanceReserve, BalanceBonus,
)
from .earning import (
    EarningSource, EarningRecord, EarningSummary,
    EarningStreak, EarningCap,
)
from .analytics import (
    WalletInsight, WithdrawalInsight, EarningInsight, LiabilityReport,
)

# Legacy aliases (original models.py used these names)
UserPaymentMethod = WithdrawalMethod   # same concept
Withdrawal        = WithdrawalRequest  # unified

__all__ = [
    "Wallet", "WalletTransaction",
    "WalletLedger", "LedgerEntry", "LedgerSnapshot", "LedgerReconciliation", "IdempotencyKey",
    "WithdrawalMethod", "WithdrawalRequest", "WithdrawalLimit",
    "WithdrawalFee", "WithdrawalBatch", "WithdrawalBlock",
    "BalanceHistory", "BalanceLock", "BalanceAlert", "BalanceReserve", "BalanceBonus",
    "EarningSource", "EarningRecord", "EarningSummary", "EarningStreak", "EarningCap",
    "WalletInsight", "WithdrawalInsight", "EarningInsight", "LiabilityReport",
    # Legacy
    "UserPaymentMethod", "Withdrawal",
]

# ── New feature models ─────────────────────────────────────
try:
    from .notification import WalletNotification, NotificationPreference
    from .config import WalletConfigModel, GatewayConfig
    from .audit import AuditLog
    from .statement import AccountStatement, StatementLine
except ImportError:
    pass
from ..models_webhook import WalletWebhookLog
