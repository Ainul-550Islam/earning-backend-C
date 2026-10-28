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

# ── WalletWebhookLog (legacy model, still used by admin/views) ───────
try:
    from ..models_webhook import WalletWebhookLog
    __all__ = list(__all__) + ["WalletWebhookLog"]
except ImportError:
    pass

# ── CPALead & extended models (from models_cpalead_extra) ─────────────
try:
    from ..models_cpalead_extra import (
        PayoutSchedule, PointsLedger, PerformanceBonus, GeoRate,
        PublisherLevel, ReferralProgram, KYCVerification,
        VirtualAccount, SettlementBatch, InstantPayout,
        MassPayoutJob, MassPayoutItem, DisputeCase,
        WithdrawalWhitelist, SecurityEvent, RefundRequest,
        FraudScore, AMLFlag, EarningOffer, OfferConversion,
        WebhookEndpoint, TaxRecord,
        SavingsGoal,
    )
    __all__ = list(__all__) + [
        "PayoutSchedule", "PointsLedger", "PerformanceBonus", "GeoRate",
        "PublisherLevel", "ReferralProgram", "KYCVerification",
        "VirtualAccount", "SettlementBatch", "InstantPayout",
        "MassPayoutJob", "MassPayoutItem", "DisputeCase",
        "WithdrawalWhitelist", "SecurityEvent", "RefundRequest",
        "FraudScore", "AMLFlag", "EarningOffer", "OfferConversion",
        "WebhookEndpoint", "TaxRecord",
        "SavingsGoal",
    ]
except ImportError:
    pass

# ── Alias: UserWallet → Wallet (used by integration_system module) ────────
from .core import Wallet as UserWallet

# ── Alias: WalletHistory → BalanceHistory (used by tests/unit module) ────
from .balance import BalanceHistory as WalletHistory

# ── AIInsight model (from ai_insights.py → Model integration) ─────────────
try:
    from .ai_insight import AIInsight, AIInsightType
    __all__ = list(__all__) + ["AIInsight", "AIInsightType"]
except ImportError:
    pass


# --- Deterministic model registry -------------------------------------------
# Models in these modules were registered only as a side effect of URL/system-check
# imports, so processes without those imports (makemigrations --skip-checks, shell,
# workers) saw a smaller registry. Import them here so every process sees the same set.
from importlib import import_module as _import_module  # noqa: E402

for _mod in (
    "api.wallet.gamification",
    "api.wallet.push_notification_service",
    "api.wallet.revenue_sharing",
):
    _import_module(_mod)
del _import_module, _mod
