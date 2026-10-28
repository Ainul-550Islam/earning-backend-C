# api/support/types.py
"""
TypedDict definitions and type aliases for support system.
Use these in function signatures for better IDE support and type checking.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict


# ── Ticket Types ──────────────────────────────────────────────
class TicketCreateData(TypedDict, total=False):
    subject:     str
    description: str
    category:    str
    priority:    str
    channel:     str
    screenshot:  Any


class TicketStats(TypedDict):
    total:        int
    open:         int
    in_progress:  int
    waiting_user: int
    resolved:     int
    closed:       int
    urgent:       int
    escalated:    int
    today:        int
    unanswered:   int
    sla_breached: int


class SLAStatus(TypedDict):
    breached:         bool
    fr_due:           Optional[str]
    res_due:          Optional[str]
    fr_overdue_hours: float
    res_overdue_hours:float


# ── Dispute Types ─────────────────────────────────────────────
class DisputeCreateData(TypedDict, total=False):
    offer_id:        str
    offer_name:      str
    expected_amount: Any
    click_id:        str
    description:     str


class DisputeVerificationResult(TypedDict):
    status:        str
    confidence:    float
    auto_approved: bool
    message:       str
    details:       List[str]


# ── Integration Types ─────────────────────────────────────────
class WalletBalance(TypedDict):
    available:    float
    current:      float
    frozen:       float
    total_earned: float
    is_locked:    bool
    currency:     str


class FraudRisk(TypedDict):
    score:         int
    is_high_risk:  bool
    is_critical:   bool
    is_flagged:    bool
    fraud_attempts:int
    warnings:      List[str]


class KYCStatus(TypedDict):
    status:      str
    is_verified: bool


# ── Use Case Result Types ─────────────────────────────────────
class UseCaseResult(TypedDict, total=False):
    success: bool
    error:   Optional[str]
    data:    Any


class TicketCreateResult(TypedDict):
    success: bool
    ticket:  Optional[Any]
    error:   Optional[str]


class DisputeSubmitResult(TypedDict):
    success: bool
    dispute: Optional[Any]
    ticket:  Optional[Any]
    error:   Optional[str]


# ── Agent Types ───────────────────────────────────────────────
class AgentWorkload(TypedDict):
    open:         int
    in_progress:  int
    waiting:      int
    total_active: int
    urgent:       int
    escalated:    int


# ── Report Types ──────────────────────────────────────────────
class CSATReport(TypedDict):
    total:        int
    avg_score:    float
    promoters:    int
    passives:     int
    detractors:   int
    nps:          float
    distribution: Dict[int, Dict[str, Any]]


# ── Aliases ───────────────────────────────────────────────────
JSON         = Dict[str, Any]
TicketID     = str
SessionID    = str
AgentID      = int
UserID       = int
TenantID     = int