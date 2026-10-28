# api/wallet/adapters/contracts.py
"""
Adapter Contracts — Pure dataclass DTOs.

These are the ONLY data structures that cross module boundaries.
No Django model instances. No ORM objects.
Just plain Python dataclasses that any module can import safely.

Rule: No imports from Django models in this file.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List
from datetime import datetime


# ════════════════════════════════════════════════════════════════
# INBOUND — data other modules send TO wallet
# ════════════════════════════════════════════════════════════════

@dataclass
class ConversionCreditRequest:
    """
    Sent by postback_engine / offerwall when a CPA conversion is confirmed.
    Wallet credits the user and returns ConversionCreditResult.
    """
    user_id:     int
    amount:      Decimal
    points:      int             = 0
    source:      str             = "postback_engine"   # "postback_engine" | "offerwall" | "tasks"
    ref_id:      str             = ""                   # conversion.id / offer_id
    description: str             = ""
    offer_id:    str             = ""
    network_name: str            = ""
    country_code: str            = ""
    ip_address:  str             = ""
    idempotency_key: str         = ""


@dataclass
class ConversionCreditResult:
    """Returned to the calling module after a successful credit."""
    success:      bool
    txn_id:       str             = ""
    amount_credited: Decimal      = Decimal("0")
    new_balance:  Decimal         = Decimal("0")
    error:        str             = ""


@dataclass
class ReversalRequest:
    """Sent by postback_engine when a conversion is reversed/charged back."""
    user_id:     int
    amount:      Decimal
    points:      int             = 0
    ref_id:      str             = ""
    description: str             = "Conversion reversal"
    idempotency_key: str         = ""


@dataclass
class ReversalResult:
    success:     bool
    txn_id:      str             = ""
    amount_debited: Decimal      = Decimal("0")
    error:       str             = ""


@dataclass
class WalletCreationRequest:
    """Sent by users module when a new user registers."""
    user_id:     int
    currency:    str             = "BDT"
    tenant_id:   Optional[int]  = None


@dataclass
class WalletCreationResult:
    success:     bool
    wallet_id:   Optional[int]  = None
    error:       str             = ""


# ════════════════════════════════════════════════════════════════
# OUTBOUND — data wallet requests FROM other modules
# ════════════════════════════════════════════════════════════════

@dataclass
class UserLevelInfo:
    """
    What wallet needs from users.UserLevel.
    Used to determine tier multipliers and fee discounts.
    """
    user_id:               int
    level_type:            str             = "bronze"   # bronze/silver/gold/platinum/diamond
    current_level:         int             = 1
    task_reward_bonus:     float           = 1.0        # multiplier
    withdrawal_fee_discount: float         = 0.0        # percentage
    experience_points:     int             = 0
    found:                 bool            = True


@dataclass
class UserRiskInfo:
    """
    What wallet needs from fraud_detection.UserRiskProfile.
    Used for fraud checks before large withdrawals.
    """
    user_id:               int
    overall_risk_score:    int             = 0      # 0-100
    is_flagged:            bool           = False
    is_restricted:         bool           = False
    monitoring_level:      str             = "normal"
    payment_risk_score:    int             = 0
    found:                 bool            = True


@dataclass
class UserStatsInfo:
    """
    What wallet needs from users.UserStatistics.
    Used for earning cap checks and reporting.
    """
    user_id:               int
    total_tasks_completed: int             = 0
    tasks_completed_today: int             = 0
    daily_earning_limit_used: Decimal      = Decimal("0")
    current_streak:        int             = 0
    total_earned:          Decimal         = Decimal("0")
    found:                 bool            = True


@dataclass
class TaskCompletionInfo:
    """A single task completion record from api/tasks."""
    task_id:     str
    user_id:     int
    amount:      Decimal
    completed_at: Optional[datetime]       = None
    status:      str                       = "approved"


@dataclass
class WalletBalanceResponse:
    """Standard wallet balance response for external consumers."""
    user_id:          int
    wallet_id:        int
    current_balance:  Decimal
    available_balance: Decimal
    bonus_balance:    Decimal
    currency:         str
    is_locked:        bool
    found:            bool               = True


@dataclass
class TransactionRecord:
    """Single transaction DTO for external consumers."""
    txn_id:      str
    amount:      Decimal
    txn_type:    str
    status:      str
    description: str
    created_at:  Optional[datetime]       = None
    reference_id: str                     = ""
