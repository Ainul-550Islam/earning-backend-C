"""Webhooks Signals Configuration

This module contains the signal configuration for all webhook-related events.
"""

from .wallet_signals import (
    wallet_transaction_created,
    wallet_balance_updated,
    wallet_transaction_failed
)

from .withdrawal_signals import (
    withdrawal_requested,
    withdrawal_approved,
    withdrawal_rejected,
    withdrawal_completed,
    withdrawal_failed
)

from .user_signals import (
    user_created,
    user_updated,
    user_profile_updated,
    user_status_changed,
    user_login,
    user_logout
)

from .offer_signals import (
    offer_credited,
    offer_completed,
    offer_expired,
    offer_cancelled,
    offer_updated
)

from .fraud_signals import (
    fraud_detected,
    fraud_flagged,
    fraud_cleared,
    fraud_investigation_started,
    fraud_investigation_completed
)

from .kyc_signals import (
    kyc_submitted,
    kyc_verified,
    kyc_rejected,
    kyc_status_changed,
    kyc_document_uploaded,
    kyc_review_started
)

from .payment_signals import (
    payment_succeeded,
    payment_failed,
    payment_initiated,
    payment_cancelled,
    payment_refunded,
    payment_disputed
)

__all__ = [
    # Wallet signals
    'wallet_transaction_created',
    'wallet_balance_updated',
    'wallet_transaction_failed',
    
    # Withdrawal signals
    'withdrawal_requested',
    'withdrawal_approved',
    'withdrawal_rejected',
    'withdrawal_completed',
    'withdrawal_failed',
    
    # User signals
    'user_created',
    'user_updated',
    'user_profile_updated',
    'user_status_changed',
    'user_login',
    'user_logout',
    
    # Offer signals
    'offer_credited',
    'offer_completed',
    'offer_expired',
    'offer_cancelled',
    'offer_updated',
    
    # Fraud signals
    'fraud_detected',
    'fraud_flagged',
    'fraud_cleared',
    'fraud_investigation_started',
    'fraud_investigation_completed',
    
    # KYC signals
    'kyc_submitted',
    'kyc_verified',
    'kyc_rejected',
    'kyc_status_changed',
    'kyc_document_uploaded',
    'kyc_review_started',
    
    # Payment signals
    'payment_succeeded',
    'payment_failed',
    'payment_initiated',
    'payment_cancelled',
    'payment_refunded',
    'payment_disputed',
]
