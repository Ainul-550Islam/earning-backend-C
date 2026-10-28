"""
Payout Queue Exceptions — Domain-specific exception hierarchy.
"""

class PayoutQueueError(Exception):
    """Base exception for all payout queue errors."""

class PayoutBatchNotFoundError(PayoutQueueError):
    """Raised when a PayoutBatch lookup fails."""

class PayoutBatchStateError(PayoutQueueError):
    """Raised when a batch state transition is not permitted."""

class PayoutBatchLockedError(PayoutQueueError):
    """Raised when a batch is already being processed (concurrent lock)."""

class PayoutBatchLimitError(PayoutQueueError):
    """Raised when concurrent batch limit is exceeded."""

class PayoutItemNotFoundError(PayoutQueueError):
    """Raised when a payout item lookup fails."""

class PayoutItemStateError(PayoutQueueError):
    """Raised when a payout item state transition is not permitted."""

class InvalidPayoutAmountError(PayoutQueueError):
    """Raised when a payout amount is outside the allowed range."""

class InsufficientFundsError(PayoutQueueError):
    """Raised when the payout source account has insufficient funds."""

class GatewayError(PayoutQueueError):
    """Raised when a payment gateway returns an error response."""

class GatewayTimeoutError(GatewayError):
    """Raised when a gateway request times out."""

class GatewayAuthError(GatewayError):
    """Raised on gateway authentication failure."""

class InvalidAccountNumberError(PayoutQueueError):
    """Raised when a recipient account number fails validation."""

class DuplicatePayoutError(PayoutQueueError):
    """Raised when a duplicate payout is detected (same user + amount + reference)."""

class WithdrawalPriorityNotFoundError(PayoutQueueError):
    """Raised when a WithdrawalPriority lookup fails."""

class BulkProcessLogNotFoundError(PayoutQueueError):
    """Raised when a BulkProcessLog lookup fails."""

class UserNotFoundError(PayoutQueueError):
    """Raised when a User lookup by pk fails."""

class FeeCalculationError(PayoutQueueError):
    """Raised when fee calculation fails."""

class RetryExhaustedError(PayoutQueueError):
    """
    DEPRECATED — never raised by payout_queue internals.

    Originally intended to be raised from PayoutItem.mark_failed() when
    retry_count exceeds MAX_RETRY_ATTEMPTS. In v3 this was replaced with
    a structured CRITICAL log in models.py (picked up by Sentry/PagerDuty)
    to avoid raising an exception mid-batch-processing.

    Kept for backward-compatibility only. Do not use in new code.
    """
