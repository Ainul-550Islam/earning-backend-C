# api/wallet/models.py
"""
COMPATIBILITY SHIM — Original models are now in models/ package.

Original models from your zip:
  Wallet, WalletTransaction, UserPaymentMethod,
  Withdrawal, WithdrawalRequest, WalletWebhookLog

All preserved and accessible via this shim.
New structured models in models/ package also exported here.
Any existing code using `from .models import Wallet` still works.
"""
from .models import (
    Wallet, WalletTransaction,
    WalletLedger, LedgerEntry, LedgerSnapshot,
    LedgerReconciliation, IdempotencyKey,
    WithdrawalMethod, WithdrawalRequest, WithdrawalLimit,
    WithdrawalFee, WithdrawalBatch, WithdrawalBlock,
    BalanceHistory, BalanceLock, BalanceAlert,
    BalanceReserve, BalanceBonus,
    EarningSource, EarningRecord, EarningSummary,
    EarningStreak, EarningCap,
    WalletInsight, WithdrawalInsight, EarningInsight, LiabilityReport,
    # Legacy aliases
    UserPaymentMethod, Withdrawal,
)
from .models_webhook import WalletWebhookLog
from .models_cpalead_extra import (
    PayoutSchedule, PointsLedger, PerformanceBonus, GeoRate,
    PublisherLevel, ReferralProgram, KYCVerification,
    VirtualAccount, SettlementBatch, InstantPayout,
    MassPayoutJob, MassPayoutItem, DisputeCase,
    WithdrawalWhitelist, SecurityEvent, RefundRequest,
    FraudScore, AMLFlag, EarningOffer, OfferConversion,
    WebhookEndpoint, TaxRecord,
)
