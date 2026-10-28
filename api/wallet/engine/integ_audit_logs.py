# api/wallet/engine/integ_audit_logs.py
"""
IntegAuditLog — engine-level audit logger.

Records every action the wallet engine performs with:
  - who triggered it (user/system)
  - what changed (before/after snapshot)
  - why (action code + description)
  - integrity proof (SHA-256 of the log entry itself)

This is separate from audit_log.py (which handles admin actions).
integ_audit_logs.py handles ENGINE actions: credits, debits,
gateway calls, fraud locks, circuit breaker state changes.
"""
import hashlib
import json
import logging
from decimal import Decimal
from typing import Optional

from django.utils import timezone

logger = logging.getLogger("wallet.engine.audit")

# ── Action constants ─────────────────────────────────────────────
class Action:
    CREDIT               = "credit"
    DEBIT                = "debit"
    INTEGRITY_CHECK_OK   = "integrity_check_ok"
    INTEGRITY_BREACH     = "integrity_breach"
    FRAUD_LOCK           = "fraud_lock"
    VELOCITY_BLOCK       = "velocity_block"
    CIRCUIT_OPEN         = "circuit_open"
    CIRCUIT_CLOSE        = "circuit_close"
    WITHDRAWAL_INITIATED = "withdrawal_initiated"
    WITHDRAWAL_COMPLETED = "withdrawal_completed"
    WITHDRAWAL_FAILED    = "withdrawal_failed"
    GATEWAY_CALL         = "gateway_call"
    GATEWAY_SUCCESS      = "gateway_success"
    GATEWAY_FAILURE      = "gateway_failure"
    DOUBLE_ENTRY_CHECK   = "double_entry_check"
    DOUBLE_ENTRY_MISMATCH = "double_entry_mismatch"
    REVERSAL             = "reversal"
    HASH_UPDATED         = "hash_updated"


def _entry_hash(entry: dict) -> str:
    """SHA-256 fingerprint of the audit entry (tamper-evidence for logs)."""
    canonical = json.dumps(entry, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _serialize(value) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return value


def log(
    action: str,
    wallet_id: Optional[int]   = None,
    user_id:   Optional[int]   = None,
    amount:    Optional[Decimal] = None,
    before:    Optional[dict]  = None,
    after:     Optional[dict]  = None,
    detail:    str             = "",
    txn_id:    str             = "",
    gateway:   str             = "",
    ip_address: str            = "",
    metadata:  Optional[dict]  = None,
) -> None:
    """
    Write one immutable audit entry.
    Writes to Python logger (always) + WalletEngineLog model (best-effort).
    """
    entry = {
        "action":     action,
        "wallet_id":  wallet_id,
        "user_id":    user_id,
        "amount":     _serialize(amount),
        "txn_id":     txn_id,
        "gateway":    gateway,
        "ip_address": ip_address,
        "detail":     detail,
        "before":     before or {},
        "after":      after  or {},
        "metadata":   metadata or {},
        "timestamp":  timezone.now().isoformat(),
    }
    entry["entry_hash"] = _entry_hash(entry)

    # 1. Always log to Python logger (survives DB failures)
    logger.info(
        f"ENGINE_AUDIT | action={action} wallet={wallet_id} user={user_id} "
        f"amount={amount} txn={txn_id} detail={detail}"
    )

    # 2. Best-effort DB write
    try:
        from ..models.audit import AuditLog
        AuditLog.objects.create(
            action=f"engine:{action}",
            performed_by_id=user_id,
            target_type="wallet",
            target_id=wallet_id,
            detail=detail or action,
            before_state=before or {},
            after_state=after  or {},
            ip_address=ip_address,
            metadata={
                **(metadata or {}),
                "txn_id":     txn_id,
                "gateway":    gateway,
                "amount":     _serialize(amount),
                "entry_hash": entry["entry_hash"],
            },
        )
    except Exception as e:
        logger.error(f"IntegAuditLog DB write failed: {e}")


# ── Convenience wrappers ─────────────────────────────────────────

def log_credit(wallet, amount: Decimal, txn_id: str, before_balance: Decimal,
               ip_address: str = "", metadata: dict = None) -> None:
    log(
        action=Action.CREDIT,
        wallet_id=wallet.pk,
        user_id=wallet.user_id,
        amount=amount,
        txn_id=txn_id,
        ip_address=ip_address,
        before={"balance": str(before_balance)},
        after={"balance":  str(wallet.current_balance)},
        metadata=metadata,
    )


def log_debit(wallet, amount: Decimal, txn_id: str, before_balance: Decimal,
              ip_address: str = "", metadata: dict = None) -> None:
    log(
        action=Action.DEBIT,
        wallet_id=wallet.pk,
        user_id=wallet.user_id,
        amount=amount,
        txn_id=txn_id,
        ip_address=ip_address,
        before={"balance": str(before_balance)},
        after={"balance":  str(wallet.current_balance)},
        metadata=metadata,
    )


def log_fraud_lock(wallet, reason: str, score: float = None) -> None:
    log(
        action=Action.FRAUD_LOCK,
        wallet_id=wallet.pk,
        user_id=wallet.user_id,
        detail=reason,
        metadata={"fraud_score": score},
    )


def log_gateway(action: str, gateway: str, wallet_id: int,
                detail: str = "", metadata: dict = None) -> None:
    log(
        action=action,
        wallet_id=wallet_id,
        gateway=gateway,
        detail=detail,
        metadata=metadata,
    )


def log_double_entry(ok: bool, total_credits: Decimal, total_debits: Decimal,
                     net: Decimal, detail: str = "") -> None:
    action = Action.DOUBLE_ENTRY_CHECK if ok else Action.DOUBLE_ENTRY_MISMATCH
    log(
        action=action,
        detail=detail or ("balanced" if ok else "MISMATCH DETECTED"),
        metadata={
            "total_credits": str(total_credits),
            "total_debits":  str(total_debits),
            "net":           str(net),
            "ok":            ok,
        },
    )
