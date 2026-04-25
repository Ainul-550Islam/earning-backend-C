# api/wallet/enums.py
"""Re-export all choices as enums for backwards compatibility."""
from .choices import (
    TransactionType, TransactionStatus, WithdrawalStatus,
    GatewayType, UserTier, BalanceType, EarningSourceType,
    WithdrawalBlockReason, LedgerEntryType, FeeType,
    AlertType, PayoutFrequency, FraudRiskLevel, AMLFlagType,
    KYCStatus, DisputeStatus,
)

__all__ = [
    "TransactionType", "TransactionStatus", "WithdrawalStatus",
    "GatewayType", "UserTier", "BalanceType", "EarningSourceType",
    "WithdrawalBlockReason", "LedgerEntryType", "FeeType",
    "AlertType", "PayoutFrequency", "FraudRiskLevel", "AMLFlagType",
    "KYCStatus", "DisputeStatus",
]
