# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Signals Package
signals/__init__.py

FIX APPLIED:
    Previously this file only exported Signal() instances (custom signals).
    The 37 handler functions across 7 files existed but were NEVER connected
    to any Django model because connect_*_signals() was never called.

    Now: importing this package exposes all custom Signal objects (for use
    in business apps that want to fire them directly) AND records are kept
    about the connector. The actual wiring happens in connector.py which is
    imported by apps.py → ready().

Public custom signals (fire these from your business logic):
    Payment domain:
        payment_succeeded, payment_failed, payment_initiated,
        payment_cancelled, payment_refunded, payment_disputed

    Fraud domain:
        fraud_detected, fraud_flagged, fraud_cleared,
        fraud_investigation_started, fraud_investigation_completed

    KYC domain:
        kyc_submitted, kyc_verified, kyc_rejected,
        kyc_status_changed, kyc_document_uploaded, kyc_review_started

    Offer domain:
        offer_credited, offer_completed, offer_expired,
        offer_cancelled, offer_updated

    User domain:
        user_created, user_updated, user_profile_updated,
        user_status_changed, user_login, user_logout

    Wallet domain:
        wallet_transaction_created, wallet_balance_updated,
        wallet_transaction_failed

    Withdrawal domain:
        withdrawal_requested, withdrawal_approved, withdrawal_rejected,
        withdrawal_completed, withdrawal_failed
"""

# ── Wallet signals ────────────────────────────────────────────────────────────
from .wallet_signals import (
    wallet_transaction_created,
    wallet_balance_updated,
    wallet_transaction_failed,
)

# ── Withdrawal signals ────────────────────────────────────────────────────────
from .withdrawal_signals import (
    withdrawal_requested,
    withdrawal_approved,
    withdrawal_rejected,
    withdrawal_completed,
    withdrawal_failed,
)

# ── User signals ──────────────────────────────────────────────────────────────
from .user_signals import (
    user_created,
    user_updated,
    user_profile_updated,
    user_status_changed,
    user_login,
    user_logout,
)

# ── Offer signals ─────────────────────────────────────────────────────────────
from .offer_signals import (
    offer_credited,
    offer_completed,
    offer_expired,
    offer_cancelled,
    offer_updated,
)

# ── Fraud signals ─────────────────────────────────────────────────────────────
from .fraud_signals import (
    fraud_detected,
    fraud_flagged,
    fraud_cleared,
    fraud_investigation_started,
    fraud_investigation_completed,
)

# ── KYC signals ───────────────────────────────────────────────────────────────
from .kyc_signals import (
    kyc_submitted,
    kyc_verified,
    kyc_rejected,
    kyc_status_changed,
    kyc_document_uploaded,
    kyc_review_started,
)

# ── Payment signals ───────────────────────────────────────────────────────────
from .payment_signals import (
    payment_succeeded,
    payment_failed,
    payment_initiated,
    payment_cancelled,
    payment_refunded,
    payment_disputed,
)

__all__ = [
    # Wallet
    "wallet_transaction_created", "wallet_balance_updated", "wallet_transaction_failed",
    # Withdrawal
    "withdrawal_requested", "withdrawal_approved", "withdrawal_rejected",
    "withdrawal_completed", "withdrawal_failed",
    # User
    "user_created", "user_updated", "user_profile_updated",
    "user_status_changed", "user_login", "user_logout",
    # Offer
    "offer_credited", "offer_completed", "offer_expired",
    "offer_cancelled", "offer_updated",
    # Fraud
    "fraud_detected", "fraud_flagged", "fraud_cleared",
    "fraud_investigation_started", "fraud_investigation_completed",
    # KYC
    "kyc_submitted", "kyc_verified", "kyc_rejected",
    "kyc_status_changed", "kyc_document_uploaded", "kyc_review_started",
    # Payment
    "payment_succeeded", "payment_failed", "payment_initiated",
    "payment_cancelled", "payment_refunded", "payment_disputed",
]
