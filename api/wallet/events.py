# api/wallet/events.py
"""
Domain Events — all wallet business events.
These are plain Python dataclasses used by the event bus.
Following the "Domain Events" pattern from cosmicpython.com.

Usage:
    from .events import WalletCredited
    event_bus.publish(WalletCredited(wallet_id=1, amount=500, txn_id="..."))
"""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional
from django.utils import timezone


@dataclass
class WalletEvent:
    """Base class for all wallet events."""
    occurred_at: datetime = field(default_factory=timezone.now)
    tenant_id: Optional[int] = None


# ── Core Wallet Events ────────────────────────────────────
@dataclass
class WalletCreated(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    currency: str = "BDT"


@dataclass
class WalletCredited(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    txn_type: str = ""
    txn_id: str = ""
    balance_after: Decimal = Decimal("0")
    description: str = ""


@dataclass
class WalletDebited(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    txn_type: str = ""
    txn_id: str = ""
    balance_after: Decimal = Decimal("0")


@dataclass
class WalletLocked(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    reason: str = ""
    locked_by_id: Optional[int] = None


@dataclass
class WalletUnlocked(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0


@dataclass
class BalanceFrozen(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class BalanceUnfrozen(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")


@dataclass
class TransactionReversed(WalletEvent):
    wallet_id: int = 0
    original_txn_id: str = ""
    reversal_txn_id: str = ""
    reason: str = ""


# ── Withdrawal Events ─────────────────────────────────────
@dataclass
class WithdrawalRequested(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    fee: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    gateway: str = ""
    account: str = ""


@dataclass
class WithdrawalApproved(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    approved_by_id: Optional[int] = None


@dataclass
class WithdrawalRejected(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class WithdrawalCompleted(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    gateway_ref: str = ""


@dataclass
class WithdrawalFailed(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    error: str = ""


@dataclass
class WithdrawalCancelled(WalletEvent):
    withdrawal_id: str = ""
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    reason: str = ""


# ── Earning Events ────────────────────────────────────────
@dataclass
class EarningAdded(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    source_type: str = ""
    source_id: str = ""
    country_code: str = ""


@dataclass
class BonusGranted(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    source: str = ""
    expires_at: Optional[datetime] = None


@dataclass
class BonusExpired(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0")
    bonus_id: str = ""


@dataclass
class StreakMilestone(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    streak_days: int = 0
    bonus_amount: Decimal = Decimal("0")


@dataclass
class ReferralCommissionPaid(WalletEvent):
    referrer_wallet_id: int = 0
    referrer_user_id: int = 0
    referred_user_id: int = 0
    commission: Decimal = Decimal("0")
    level: int = 1


# ── KYC / Security Events ─────────────────────────────────
@dataclass
class KYCSubmitted(WalletEvent):
    user_id: int = 0
    kyc_id: int = 0
    level: int = 1
    doc_type: str = ""


@dataclass
class KYCApproved(WalletEvent):
    user_id: int = 0
    kyc_id: int = 0
    level: int = 1
    new_daily_limit: Decimal = Decimal("0")


@dataclass
class KYCRejected(WalletEvent):
    user_id: int = 0
    kyc_id: int = 0
    reason: str = ""


@dataclass
class SecurityLockTriggered(WalletEvent):
    user_id: int = 0
    event_type: str = ""
    lock_hours: int = 24
    ip_address: str = ""


@dataclass
class FraudDetected(WalletEvent):
    user_id: int = 0
    wallet_id: int = 0
    txn_id: str = ""
    score: float = 0.0
    signals: list = field(default_factory=list)


@dataclass
class AMLFlagged(WalletEvent):
    user_id: int = 0
    wallet_id: int = 0
    flag_type: str = ""
    suspicious_amount: Decimal = Decimal("0")


# ── CPAlead / Publisher Events ────────────────────────────
@dataclass
class PublisherLevelUpgraded(WalletEvent):
    user_id: int = 0
    wallet_id: int = 0
    old_level: int = 0
    new_level: int = 0
    new_payout_freq: str = ""


@dataclass
class OfferConverted(WalletEvent):
    wallet_id: int = 0
    user_id: int = 0
    offer_id: int = 0
    offer_type: str = ""
    payout: Decimal = Decimal("0")
    click_id: str = ""
    country_code: str = ""


@dataclass
class DailyPayoutProcessed(WalletEvent):
    user_id: int = 0
    wallet_id: int = 0
    withdrawal_id: str = ""
    amount: Decimal = Decimal("0")
    gateway: str = ""


# ── Dispute / Refund Events ───────────────────────────────
@dataclass
class DisputeOpened(WalletEvent):
    case_id: str = ""
    user_id: int = 0
    wallet_id: int = 0
    disputed_amount: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class DisputeResolved(WalletEvent):
    case_id: str = ""
    user_id: int = 0
    outcome: str = ""
    refunded_amount: Decimal = Decimal("0")


@dataclass
class RefundIssued(WalletEvent):
    refund_id: str = ""
    user_id: int = 0
    wallet_id: int = 0
    amount: Decimal = Decimal("0")


# ── Transfer Events ───────────────────────────────────────
@dataclass
class TransferInitiated(WalletEvent):
    from_wallet_id: int = 0
    to_wallet_id: int = 0
    from_user_id: int = 0
    to_user_id: int = 0
    amount: Decimal = Decimal("0")


@dataclass
class TransferCompleted(WalletEvent):
    from_wallet_id: int = 0
    to_wallet_id: int = 0
    debit_txn_id: str = ""
    credit_txn_id: str = ""
    amount: Decimal = Decimal("0")
